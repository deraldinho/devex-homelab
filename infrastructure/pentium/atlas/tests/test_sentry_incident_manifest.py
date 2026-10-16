"""TDD: health-only signed incident manifest, no writable SQLite executor."""
from __future__ import annotations
import os
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from infrastructure.pentium.atlas.failure_memory import FailureMemory
from infrastructure.pentium.atlas.health_supervisor import SupervisorSnapshot, EvaluatedComponentHealth
from infrastructure.pentium.atlas.health_supervisor_model import ComponentHealthState as State
from infrastructure.pentium.atlas.sentry_receipt_v2 import Ed25519ReceiptSigner, ReceiptV2Error
from infrastructure.pentium.atlas.sentry_incident_manifest import (
    SignedIncidentPublisher,ReadOnlyIncidentManifest,ManifestSecurityError
)
START=datetime(2026,10,16,14,tzinfo=timezone.utc)

class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.store=FailureMemory(self.root/"fails.sqlite")
        self.key=Ed25519PrivateKey.generate()
        self.signer=Ed25519ReceiptSigner("health_probe","health-k1",self.key)
        self.publisher=SignedIncidentPublisher(self.root/"open-index.json",self.signer)
        self.now=START+timedelta(seconds=25)
        self.reader=ReadOnlyIncidentManifest(self.root/"open-index.json",
            self.key.public_key(),key_id="health-k1",
            owner_uid=os.geteuid() if os.name=="posix" else None,
            clock=lambda:self.now)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def open(self):
        ts=START.isoformat()
        comp=EvaluatedComponentHealth("atlas-dashboard.service","pentium","running",
            State.FAILED,ts,("broken",),("health:failure",),True)
        return self.store.observe_snapshot(SupervisorSnapshot(ts,State.FAILED,(comp,)))

    def test_signed_health_index_provides_open_incidents_without_sqlite_write(self):
        self.open()
        self.publisher.publish(self.store,(START+timedelta(seconds=10)).isoformat())
        rows=self.reader.open_incidents()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["component"],"atlas-dashboard.service")
        self.assertEqual(rows[0]["state"],"open")
        self.assertFalse(hasattr(self.reader,"observe_snapshot"))

    def test_tampered_manifest_cannot_publish_fake_open_incident(self):
        self.open()
        self.publisher.publish(self.store,(START+timedelta(seconds=10)).isoformat())
        file=self.root/"open-index.json"
        payload=file.read_text(encoding="utf-8")
        file.write_text(payload.replace("atlas-dashboard.service","other.service"),encoding="utf-8")
        with self.assertRaises(ManifestSecurityError):
            self.reader.open_incidents()

    def test_manifest_stale_is_fail_closed_even_with_valid_signature(self):
        self.open()
        self.publisher.publish(self.store,START.isoformat())
        self.now=START+timedelta(minutes=5)
        with self.assertRaises(ManifestSecurityError):
            self.reader.open_incidents()

    def test_invalid_key_and_wrong_role_fail_closed(self):
        self.open()
        self.publisher.publish(self.store,START.isoformat())
        other=ReadOnlyIncidentManifest(self.root/"open-index.json",
            Ed25519PrivateKey.generate().public_key(),key_id="health-k1",
            clock=lambda:START+timedelta(seconds=10),
            owner_uid=os.geteuid() if os.name=="posix" else None)
        with self.assertRaises(ManifestSecurityError):
            other.open_incidents()
        with self.assertRaises(ReceiptV2Error):
            Ed25519ReceiptSigner("executor","exec-k1",Ed25519PrivateKey.generate()).sign_blob(b"hello")

    def test_empty_projection_revokes_old_incidents(self):
        self.open()
        self.publisher.publish(self.store,(START+timedelta(seconds=10)).isoformat())
        healthy=State.HEALTHY
        for secs in (12,18):
            ts=(START+timedelta(seconds=secs)).isoformat()
            row=EvaluatedComponentHealth("atlas-dashboard.service","pentium","running",
                healthy,ts,(),("health:pass"+str(secs),),True)
            self.store.observe_snapshot(SupervisorSnapshot(ts,healthy,(row,)))
        self.publisher.publish(self.store,(START+timedelta(seconds=21)).isoformat())
        self.assertEqual(self.reader.open_incidents(),())

    def test_signed_manifest_requires_absolute_path(self):
        with self.assertRaises(ManifestSecurityError):
            SignedIncidentPublisher(Path("relative-index.json"),self.signer)


if __name__=="__main__":unittest.main()
