"""P4 read-only executor factory and Linux-only relay configuration gates."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
from infrastructure.pentium.atlas.failure_memory import FailureMemory
from infrastructure.pentium.atlas.sentry_receipt_v2 import (
    Ed25519RecoveryVerifier,Ed25519ReceiptSigner,
    build_executor_receipt_sink,build_health_receipt_sink,ReceiptV2Error,
    load_public_key_ring,
)
from infrastructure.pentium.atlas.sentry_incident_manifest import (
    ReadOnlyIncidentManifest, SignedIncidentPublisher,
)
from infrastructure.pentium.atlas.sentry_receipt_relay import (
    RotatingReceiptJournal,ReceiptRelay,RelaySecurityError,
)
from tools.atlas_sentry_v2_relay import build_relay

BASE=datetime(2026,10,16,14,tzinfo=timezone.utc)


def save_key(root,name,key):
    private=root/(name+".pem")
    public=root/(name+".pub")
    private.write_bytes(key.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()))
    public.write_bytes(key.public_key().public_bytes(Encoding.PEM,PublicFormat.SubjectPublicKeyInfo))
    if os.name=="posix":private.chmod(0o600)
    return str(private),str(public)


class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.action=Ed25519PrivateKey.generate()
        self.health=Ed25519PrivateKey.generate()
        self.action_priv,self.action_pub=save_key(self.root,"action",self.action)
        self.health_priv,self.health_pub=save_key(self.root,"health",self.health)
        self.index=self.root/"open.json"
        self.env={
            "ATLAS_SENTRY_V2_TRANSPORT":"unix",
            "ATLAS_SENTRY_V2_EXECUTOR_ENABLED":"1",
            "ATLAS_SENTRY_V2_HEALTH_ENABLED":"1",
            "ATLAS_SENTRY_V2_EXECUTOR_PRIVATE_KEY_FILE":self.action_priv,
            "ATLAS_SENTRY_V2_EXECUTOR_PUBLIC_KEY_FILE":self.action_pub,
            "ATLAS_SENTRY_V2_EXECUTOR_KEY_ID":"executor-k1",
            "ATLAS_SENTRY_V2_HEALTH_PRIVATE_KEY_FILE":self.health_priv,
            "ATLAS_SENTRY_V2_HEALTH_PUBLIC_KEY_FILE":self.health_pub,
            "ATLAS_SENTRY_V2_HEALTH_KEY_ID":"health-k1",
            "ATLAS_SENTRY_V2_HEALTH_UID":str(os.geteuid()) if os.name=="posix" else "1000",
            "ATLAS_SENTRY_V2_RELAY_GROUP_GID":str(os.getegid()) if os.name=="posix" else "1000",
            "ATLAS_SENTRY_V2_INCIDENT_MANIFEST_FILE":str(self.index),
            "ATLAS_SENTRY_V2_RELAY_SOCKET":str(self.root/"relay.sock"),
            "ATLAS_SENTRY_V2_RELAY_ACTION_JOURNAL":str(self.root/"actions.jsonl"),
            "ATLAS_SENTRY_V2_HEALTH_PROBE_JOURNAL":str(self.root/"probes.jsonl"),
        }

    def tearDown(self):self.temp.cleanup()

    def test_executor_does_not_require_or_open_failure_memory_in_unix_mode(self):
        sink=build_executor_receipt_sink(self.root,None,environ=self.env)
        self.assertIsInstance(sink.memory,ReadOnlyIncidentManifest)
        self.assertFalse((self.root/"failure-memory.sqlite3").exists())
        self.assertEqual(sink.signer.role,"executor")
        self.assertEqual(str(sink.spool.path),self.env["ATLAS_SENTRY_V2_RELAY_SOCKET"])

    def test_health_unix_sink_uses_rotating_journals_and_signed_manifest(self):
        store=FailureMemory(self.root/"health.sqlite3")
        try:
            sink=build_health_receipt_sink(self.root,store,environ=self.env)
            self.assertIsInstance(sink.actions,RotatingReceiptJournal)
            self.assertIsInstance(sink.probes,RotatingReceiptJournal)
            self.assertIsInstance(sink.incident_publisher,SignedIncidentPublisher)
            sink.publish_manifest(BASE.isoformat())
            self.assertEqual(len(self.index.read_bytes())>0,True)
        finally:store.close()

    def test_relay_disabled_by_default_and_require_linux_credentials(self):
        with self.assertRaises(RuntimeError):
            build_relay({})
        if os.name!="posix":
            with self.assertRaises(RuntimeError):
                build_relay({
                    **self.env,
                    "ATLAS_SENTRY_V2_RELAY_ENABLED":"1",
                    "ATLAS_SENTRY_V2_RELAY_ALLOWED_UID":"1000",
                })

    def test_key_rotation_keeps_prior_valid_signatures_until_key_revoked(self):
        old=Ed25519PrivateKey.generate()
        new=Ed25519PrivateKey.generate()
        health=self.health
        signed=Ed25519ReceiptSigner("executor","old",old).sign(
            incident_id="incident1",component="atlas-dashboard.service",
            host="pentium",action_id="action1",event_at=BASE.isoformat(),
            operation="restart_service",status="success",authorized=True,
            evidence_ref="execution:old")
        def policy(keys):
            return Ed25519RecoveryVerifier({
                "executor":keys,
                "health_probe":{"health":health.public_key()}},
                trusted_host="pentium",clock=lambda:BASE+timedelta(minutes=1))
        self.assertEqual(policy({"old":old.public_key(),"new":new.public_key()}).verify_action(signed)["key_id"],"old")
        with self.assertRaises(ReceiptV2Error):
            policy({"new":new.public_key()}).verify_action(signed)

    def test_signed_keyring_rotation_and_revocation(self):
        import json
        second=Ed25519PrivateKey.generate()
        second_priv,second_pub=save_key(self.root,"second",second)
        trust=self.root/"trust.json"
        trust.write_text(json.dumps({
            "version":1,
            "executor":{"executor-k1":self.action_pub,"executor-k2":second_pub},
            "health_probe":{"health-k1":self.health_pub}
        }),encoding="utf-8")
        if os.name=="posix":trust.chmod(0o600)
        loaded=load_public_key_ring(trust)
        self.assertEqual(set(loaded["executor"]),{"executor-k1","executor-k2"})
        bad=self.root/"bad.json"
        bad.write_text(json.dumps({
            "version":1,"executor":{"same":self.action_pub},
            "health_probe":{"same":self.action_pub}
        }))
        if os.name=="posix":bad.chmod(0o600)
        with self.assertRaises(ValueError):
            load_public_key_ring(bad)
        self.env["ATLAS_SENTRY_V2_TRUST_KEYRING_FILE"]=str(trust)
        memory=FailureMemory(self.root/"ring-memory.db")
        try:
            sink=build_health_receipt_sink(self.root,memory,environ=self.env)
            self.assertIn("executor-k2",sink.verifier.keys["executor"])
            altered=dict(self.env)
            altered["ATLAS_SENTRY_V2_HEALTH_KEY_ID"]="revoked"
            with self.assertRaises(ReceiptV2Error):
                build_health_receipt_sink(self.root,memory,environ=altered)
        finally:memory.close()

    def test_corrupt_or_missing_manifest_fails_closed_even_with_action_key(self):
        signer=build_executor_receipt_sink(self.root,None,environ=self.env)
        with self.assertRaises(ReceiptV2Error):
            signer.memory.open_incidents()


if __name__=="__main__":unittest.main()
