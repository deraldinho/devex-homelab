"""P4 canary: typed executor + signed read-only index + independent health probes."""
import json
import os
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from infrastructure.pentium.atlas.failure_memory import FailureMemory
from infrastructure.pentium.atlas.health_probes import ProbeResult
from infrastructure.pentium.atlas.health_supervisor import AtlasHealthSupervisor,HealthSnapshotPublisher
from infrastructure.pentium.atlas.health_supervisor_daemon import HealthSupervisorOwner,ServiceProbeBundle
from infrastructure.pentium.atlas.health_supervisor_model import ComponentHealthState as State
from infrastructure.pentium.atlas.multi_host_executor import MultiHostCapabilityExecutor
from infrastructure.pentium.atlas.sentry_receipt_v2 import (
    Ed25519ReceiptSigner,Ed25519RecoveryVerifier,ExecutorReceiptSink,
    HealthReceiptSink,learn_from_ed25519_recovery,
)
from infrastructure.pentium.atlas.sentry_receipt_relay import (
    RotatingReceiptJournal,ReceiptRelay,RelaySecurityError,
)
from infrastructure.pentium.atlas.sentry_incident_manifest import (
    SignedIncidentPublisher,ReadOnlyIncidentManifest,ManifestSecurityError,
)

T=datetime(2026,10,16,14,tzinfo=timezone.utc)


class Probe:
    def __init__(self): self.state=State.FAILED
    def probe(self):
        return ProbeResult(self.state==State.HEALTHY,self.state,T.isoformat(),
            "fixture",("probe:source",),{})


class RelayAdapter:
    def __init__(self,relay): self.relay=relay
    def append(self,receipt):return self.relay.accept(receipt,peer_uid=1042)


class P4Canary(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.memory=FailureMemory(self.root/"recovery.sqlite3")
        self.exec_key=Ed25519PrivateKey.generate()
        self.health_key=Ed25519PrivateKey.generate()
        self.exec_signer=Ed25519ReceiptSigner("executor","executor-v1",self.exec_key)
        self.health_signer=Ed25519ReceiptSigner("health_probe","health-v1",self.health_key)
        self.verifier=Ed25519RecoveryVerifier({
            "executor":{"executor-v1":self.exec_key.public_key()},
            "health_probe":{"health-v1":self.health_key.public_key()}},
            trusted_host="pentium",clock=lambda:T+timedelta(seconds=90))
        self.action_journal=RotatingReceiptJournal(self.root/"actions.jsonl",
                                                  max_records=2,max_archives=2)
        self.probe_journal=RotatingReceiptJournal(self.root/"probes.jsonl")
        relay=ReceiptRelay(self.action_journal,self.verifier,allowed_uid=1042,
                           clock=lambda:T+timedelta(seconds=20))
        self.signed_index=SignedIncidentPublisher(
            self.root/"incidents.json",self.health_signer)
        self.read_index=ReadOnlyIncidentManifest(
            self.root/"incidents.json",self.health_key.public_key(),
            key_id="health-v1",owner_uid=os.geteuid() if os.name=="posix" else None,
            clock=lambda:T+timedelta(seconds=20))
        self.executed=[]
        self.receipt_sink=ExecutorReceiptSink(
            self.exec_signer,RelayAdapter(relay),self.read_index,
            now=lambda:T+timedelta(seconds=20))
        def local(cap,args,plan,action): self.executed.append(cap)
        self.executor=MultiHostCapabilityExecutor(
            local,None,None,verifier=lambda *_:True,
            on_command_succeeded=self.receipt_sink)
        self.health_sink=HealthReceiptSink(
            self.health_signer,self.action_journal,self.probe_journal,
            self.verifier,self.memory)
        self.health_sink.incident_publisher=self.signed_index
        self.ticks=iter(T+timedelta(seconds=i) for i in (0,30,60,90))
        self.probe=Probe()
        self.owner=HealthSupervisorOwner(
            AtlasHealthSupervisor(),
            HealthSnapshotPublisher(self.root/"health.json",self.root/"history.jsonl"),
            (ServiceProbeBundle(
                "atlas-dashboard.service","pentium","running",True,
                self.probe,self.probe
            ),),
            poll_interval_s=15,now=lambda:next(self.ticks),
            failure_memory=self.memory,recovery_receipt_sink=self.health_sink)

    def tearDown(self):
        self.owner.close()
        self.tmp.cleanup()

    def test_all_boundaries_and_two_probes_before_learning(self):
        self.owner.run_once()
        opened=self.memory.open_incidents()[0]["incident_id"]
        # Separate executor can inspect only a signed projection, not SQLite.
        self.assertFalse(hasattr(self.read_index,"_db"))
        self.assertEqual(self.read_index.open_incidents()[0]["incident_id"],opened)
        self.executor("restart_service",{
            "host":"pentium","service":"atlas-dashboard.service"})
        self.assertEqual(len(self.executed),1)
        self.assertEqual(len(self.action_journal.read()),1)
        self.probe.state=State.HEALTHY
        self.owner.run_once()
        self.assertEqual(len(self.probe_journal.read()),1)
        self.assertEqual(self.memory.stats()["recovered_incidents"],0)
        self.owner.run_once()
        self.assertEqual(self.memory.stats()["recovered_incidents"],1)
        self.read_index.clock=lambda:T+timedelta(seconds=70)
        self.assertEqual(self.read_index.open_incidents(),())
        receipts=(self.action_journal.read()[0],*self.probe_journal.read())
        self.assertEqual(len(receipts),3)
        lesson=learn_from_ed25519_recovery(
            self.memory,incident_id=opened,
            cause="service_unhealthy",correction="inspect health probes",
            receipts=receipts,verifier=self.verifier)
        self.assertEqual(lesson["status"],"stored")
        self.assertEqual(self.memory.stats()["lessons"],1)
        self.assertEqual(
            learn_from_ed25519_recovery(
                self.memory,incident_id=opened,
                cause="service_unhealthy",correction="inspect health probes",
                receipts=receipts,verifier=self.verifier)["status"],
            "already_stored",
        )

    def test_unsigned_projection_change_does_not_emit_action_proof(self):
        self.owner.run_once()
        index=self.root/"incidents.json"
        index.write_text(index.read_text().replace("atlas-dashboard.service","spoof.service"))
        self.executor("restart_service",{"host":"pentium","service":"spoof.service"})
        self.assertEqual(self.action_journal.read(),())
        self.assertEqual(self.executor.last_receipt_error,"ManifestSecurityError")

    def test_missing_relay_delivery_keeps_policy_result_but_no_lesson(self):
        self.owner.run_once()
        # Relay refusing peer credentials cannot be bypassed by executor.
        self.receipt_sink.spool=RelayAdapter(
            ReceiptRelay(self.action_journal,self.verifier,allowed_uid=404,
                         clock=lambda:T+timedelta(seconds=20)))
        result=self.executor("restart_service",{
            "host":"pentium","service":"atlas-dashboard.service"})
        self.assertEqual(result["status"],"success")
        self.assertEqual(self.executor.last_receipt_error,"RelaySecurityError")
        self.assertEqual(self.action_journal.read(),())
        self.probe.state=State.HEALTHY
        self.owner.run_once();self.owner.run_once()
        self.assertEqual(self.memory.stats()["lessons"],0)
        self.assertEqual(self.probe_journal.read(),())


if __name__=="__main__":unittest.main()
