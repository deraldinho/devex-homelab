"""P4 secure credential-bound Unix relay and bounded/retained receipt journal."""
from __future__ import annotations

import base64
import json
import os
import socket
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from infrastructure.pentium.atlas.sentry_receipt_v2 import (
    Ed25519ReceiptSigner, Ed25519RecoveryVerifier, ReceiptV2Error,
)
from infrastructure.pentium.atlas.sentry_receipt_relay import (
    RotatingReceiptJournal, ReceiptRelay, UnixReceiptClient,
    RelaySecurityError,
)

BASE=datetime(2026,10,16,14,0,0,tzinfo=timezone.utc)


def action(sign,*,minute=0,component="atlas-dashboard.service",receipt_id=None):
    value=sign.sign(
        incident_id="12345678-abcd",component=component,host="pentium",
        action_id="action1",event_at=(BASE+timedelta(minutes=minute)).isoformat(),
        operation="restart_service",status="success",authorized=True,
        evidence_ref="execution:real",
    )
    if receipt_id:
        value["receipt_id"]=receipt_id
    return value


class P4Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir=Path(self.temp.name)
        key=Ed25519PrivateKey.generate()
        other=Ed25519PrivateKey.generate()
        self.signer=Ed25519ReceiptSigner("executor","k1",key)
        self.verifier=Ed25519RecoveryVerifier(
            {"executor":{"k1":key.public_key()},
             "health_probe":{"h1":other.public_key()}},
            trusted_host="pentium",clock=lambda:BASE+timedelta(minutes=2))
        self.journal=RotatingReceiptJournal(self.dir/"actions.jsonl",
                                             max_records=2,max_archives=3)
        self.relay=ReceiptRelay(self.journal,self.verifier,allowed_uid=1234,
                                clock=lambda:BASE+timedelta(minutes=2))

    def test_synthesized_action_from_executor_is_accepted_once(self):
        signed=action(self.signer)
        self.assertEqual(self.relay.accept(signed,peer_uid=1234),"stored")
        self.assertEqual(self.relay.accept(signed,peer_uid=1234),"duplicate")
        self.assertEqual(self.journal.read(),(signed,))

    def test_foreign_uid_invalid_signature_and_different_host_fail_closed(self):
        signed=action(self.signer)
        with self.assertRaises(RelaySecurityError):
            self.relay.accept(signed,peer_uid=7)
        self.assertEqual(self.journal.read(),())
        bad=dict(signed,status="failed")
        with self.assertRaises(RelaySecurityError):
            self.relay.accept(bad,peer_uid=1234)
        other=action(self.signer,component="other.service")
        other["host"]="core"
        with self.assertRaises(RelaySecurityError):
            self.relay.accept(other,peer_uid=1234)

    def test_missing_authenticated_handshake_and_stale_or_future_refused(self):
        signed=action(self.signer)
        for uid in (None,-1,True,"1234"):
            with self.subTest(uid=uid):
                with self.assertRaises(RelaySecurityError):
                    self.relay.accept(signed,peer_uid=uid)
        for value in (action(self.signer,minute=-30),
                      action(self.signer,minute=30)):
            with self.assertRaises(RelaySecurityError):
                self.relay.accept(value,peer_uid=1234)

    def test_persistent_replay_defence_survives_archive_rotation(self):
        items=[action(self.signer) for _ in range(5)]
        for item in items:
            self.assertEqual(self.relay.accept(item,peer_uid=1234),"stored")
        self.assertEqual(len(self.journal.read()),5)
        self.assertEqual(self.relay.accept(items[0],peer_uid=1234),"duplicate")
        self.assertEqual(len(self.journal.read()),5)
        self.assertLessEqual((self.dir/"actions.jsonl").stat().st_size,4096)

    def test_retention_full_fails_closed_without_overwriting_fresh_proof(self):
        strict=RotatingReceiptJournal(self.dir/"short.jsonl",
                                      max_records=1,max_archives=1)
        gate=ReceiptRelay(strict,self.verifier,allowed_uid=1234,
                          clock=lambda:BASE+timedelta(minutes=2))
        gate.accept(action(self.signer),peer_uid=1234)
        gate.accept(action(self.signer),peer_uid=1234)
        with self.assertRaises(RelaySecurityError):
            gate.accept(action(self.signer),peer_uid=1234)
        self.assertEqual(len(strict.read()),2)

    def test_expired_archive_pruned_but_active_proof_is_preserved(self):
        vault=RotatingReceiptJournal(self.dir/"rotated.jsonl",
                                     max_records=1,max_archives=1)
        a=action(self.signer)
        b=action(self.signer)
        c=action(self.signer)
        self.assertEqual(vault.append(a,now=BASE),"stored")
        self.assertEqual(vault.append(b,now=BASE+timedelta(seconds=1)),"stored")
        self.assertEqual(len(vault.read()),2)
        later=BASE+timedelta(hours=49)
        self.assertEqual(vault.append(c,now=later),"stored")
        self.assertEqual(tuple(x["receipt_id"] for x in vault.read()),
                         (b["receipt_id"],c["receipt_id"]))

    def test_restart_does_not_allow_replay(self):
        signed=action(self.signer)
        self.relay.accept(signed,peer_uid=1234)
        fresh=ReceiptRelay(RotatingReceiptJournal(self.dir/"actions.jsonl",
                            max_records=2,max_archives=3),
                           self.verifier,allowed_uid=1234,
                           clock=lambda:BASE+timedelta(minutes=3))
        self.assertEqual(fresh.accept(signed,peer_uid=1234),"duplicate")

    def test_corrupt_journal_blocks_append_instead_of_erasing_history(self):
        self.journal.path.write_text("{broken",encoding="utf-8")
        with self.assertRaises(RelaySecurityError):
            self.relay.accept(action(self.signer),peer_uid=1234)
        self.assertEqual(self.journal.path.read_text(),"{broken")

    def test_symlink_journal_refused(self):
        link=self.dir/"alias.jsonl"
        try:
            link.symlink_to(self.journal.path)
        except OSError:
            self.skipTest("Windows symlink permission unavailable")
        with self.assertRaises(RelaySecurityError):
            RotatingReceiptJournal(link).append(action(self.signer))

    def test_oversized_payload_and_non_dict_rejected(self):
        for item in ("arbitrary text",{},dict(action(self.signer),garbage="x"*4000)):
            with self.assertRaises(RelaySecurityError):
                self.relay.accept(item,peer_uid=1234)

    def test_unix_client_refuses_non_absolute_socket_path(self):
        with self.assertRaises(ValueError):
            UnixReceiptClient(Path("relative.sock"))

    @unittest.skipUnless(os.name=="posix" and hasattr(socket,"SO_PEERCRED"),
                         "SO_PEERCRED requires Linux")
    def test_real_unix_socket_uses_kernel_peer_credentials(self):
        import threading
        from infrastructure.pentium.atlas.sentry_receipt_relay import ReceiptRelayServer
        sock_path=self.dir/"relay.sock"
        owner=ReceiptRelay(self.journal,self.verifier,allowed_uid=os.getuid(),
                           clock=lambda:BASE+timedelta(minutes=2))
        server=ReceiptRelayServer(sock_path,owner,group_id=os.getgid(),
                                  socket_mode=0o600)
        with server:
            th=threading.Thread(target=server.serve_one,daemon=True)
            th.start()
            client=UnixReceiptClient(sock_path,timeout_s=2)
            client.append(action(self.signer))
            th.join(timeout=3)
            self.assertFalse(th.is_alive())
            self.assertEqual(len(self.journal.read()),1)
            server.publish_status(self.dir/"relay-status.json")
            stats=json.loads((self.dir/"relay-status.json").read_text())
            self.assertEqual(stats,{"schema_version":1,
                                    "accepted":1,"duplicates":0,"denied":0})

    @unittest.skipUnless(os.name=="posix" and hasattr(socket,"SO_PEERCRED"),
                         "SO_PEERCRED requires Linux")
    def test_kernel_peer_uid_mismatch_rejects_real_socket_client(self):
        import threading
        from infrastructure.pentium.atlas.sentry_receipt_relay import ReceiptRelayServer
        other=ReceiptRelay(self.journal,self.verifier,allowed_uid=os.getuid()+1,
                           clock=lambda:BASE+timedelta(minutes=2))
        with ReceiptRelayServer(
            self.dir/"deny.sock",other,group_id=os.getgid(),socket_mode=0o600
        ) as server:
            th=threading.Thread(target=server.serve_one,daemon=True)
            th.start()
            with self.assertRaises(RelaySecurityError):
                UnixReceiptClient(self.dir/"deny.sock").append(action(self.signer))
            th.join(timeout=3)
            self.assertFalse(th.is_alive())
            self.assertEqual(self.journal.read(),())
            self.assertEqual(server.denied,1)


if __name__=="__main__":unittest.main()
