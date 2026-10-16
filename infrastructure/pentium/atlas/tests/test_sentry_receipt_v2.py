"""CP-SENTRY-P3: two independent Ed25519 signers, real executor/probe integration."""
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from infrastructure.pentium.atlas.failure_memory import FailureMemory
from infrastructure.pentium.atlas.health_supervisor import (
    AtlasHealthSupervisor, HealthSnapshotPublisher, EvaluatedComponentHealth, SupervisorSnapshot,
)
from infrastructure.pentium.atlas.health_supervisor_daemon import HealthSupervisorOwner, ServiceProbeBundle
from infrastructure.pentium.atlas.health_supervisor_model import ComponentHealthState as S
from infrastructure.pentium.atlas.health_probes import ProbeResult
from infrastructure.pentium.atlas.multi_host_executor import MultiHostCapabilityExecutor
from infrastructure.pentium.atlas.sentry_receipt_v2 import (
    Ed25519ReceiptSigner, SignedReceiptSpool, ExecutorReceiptSink,
    HealthReceiptSink, Ed25519RecoveryVerifier, learn_from_ed25519_recovery,
    ReceiptV2Error, build_executor_receipt_sink, build_health_receipt_sink,
    load_signer_from_file,
)

START=datetime(2026,10,16,14,tzinfo=timezone.utc)


class Probe:
    def __init__(self):
        self.state=S.FAILED
    def probe(self):
        return ProbeResult(self.state==S.HEALTHY,self.state,START.isoformat(),
                           "real_test_probe",("probe:actual",),{})


class FakeLocal:
    def __init__(self): self.calls=0
    def __call__(self, cap, args, plan, action):
        self.calls+=1


class E2ETests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.memory=FailureMemory(self.root/"sentry.db")
        self.action_key=Ed25519PrivateKey.generate()
        self.health_key=Ed25519PrivateKey.generate()
        self.action_signer=Ed25519ReceiptSigner("executor","executor-k1",self.action_key)
        self.health_signer=Ed25519ReceiptSigner("health_probe","probe-k1",self.health_key)
        self.action_spool=SignedReceiptSpool(self.root/"action.jsonl")
        self.probe_spool=SignedReceiptSpool(self.root/"probe.jsonl")
        self.verifier=Ed25519RecoveryVerifier(
            {"executor":{"executor-k1":self.action_key.public_key()},
             "health_probe":{"probe-k1":self.health_key.public_key()}},
            trusted_host="pentium",clock=lambda: START+timedelta(minutes=5))
        self.times=iter(START+timedelta(seconds=n) for n in (0,20,40,60,80,100,120,140))
        self.probe=Probe()
        self.owner=HealthSupervisorOwner(
            AtlasHealthSupervisor(),
            HealthSnapshotPublisher(self.root/"health.json",self.root/"health-events.jsonl"),
            (ServiceProbeBundle("atlas-dashboard.service","pentium","running",True,
                                self.probe,self.probe),),
            poll_interval_s=15,now=lambda:next(self.times),
            failure_memory=self.memory,
            recovery_receipt_sink=HealthReceiptSink(
                self.health_signer,self.action_spool,self.probe_spool,self.verifier,
                self.memory))
        self.executor_receipts=ExecutorReceiptSink(
            self.action_signer,self.action_spool,self.memory,now=lambda: START+timedelta(seconds=12))
        self.local=FakeLocal()
        self.executor=MultiHostCapabilityExecutor(
            self.local,None,None,verifier=lambda *_:True,
            on_command_succeeded=self.executor_receipts,
        )

    def tearDown(self):
        self.owner.close()
        self.temp.cleanup()

    def test_real_flow_only_after_two_independent_health_cycles(self):
        failed=self.owner.run_once()
        self.assertEqual(failed.state,S.FAILED)
        incident=self.memory.open_incidents()[0]
        self.assertEqual(self.action_spool.read(),())
        self.executor("restart_service",{"host":"pentium","service":"atlas-dashboard.service"})
        actions=self.action_spool.read()
        self.assertEqual(len(actions),1)
        self.assertNotIn("private_key",str(actions))
        self.probe.state=S.HEALTHY
        self.owner.run_once()
        self.assertEqual(len(self.probe_spool.read()),1)
        self.assertEqual(self.memory.get_incident(incident["incident_id"])["state"],"open")
        self.owner.run_once()
        self.assertEqual(len(self.probe_spool.read()),2)
        self.assertEqual(self.memory.get_incident(incident["incident_id"])["state"],"recovered")
        result=learn_from_ed25519_recovery(
            self.memory,incident_id=incident["incident_id"],
            cause="service_unresponsive",correction="verify service health before restarting",
            receipts=(actions[0],*self.probe_spool.read()),verifier=self.verifier)
        self.assertEqual(result["status"],"stored")
        self.assertEqual(self.memory.stats()["lessons"],1)
        again=learn_from_ed25519_recovery(
            self.memory,incident_id=incident["incident_id"],
            cause="service_unresponsive",correction="verify service health before restarting",
            receipts=(actions[0],*self.probe_spool.read()),verifier=self.verifier)
        self.assertEqual(again["status"],"already_stored")

    def test_no_action_does_not_make_probe_receipt(self):
        self.owner.run_once()
        self.probe.state=S.HEALTHY
        self.owner.run_once()
        self.owner.run_once()
        self.assertEqual(self.probe_spool.read(),())
        self.assertEqual(self.memory.stats()["lessons"],0)

    def test_action_signer_never_runs_if_execution_fails(self):
        self.owner.run_once()
        def fail_exec(*_): raise RuntimeError("service failed")
        executor=MultiHostCapabilityExecutor(fail_exec,None,None,
                    verifier=lambda *_:True,on_command_succeeded=self.executor_receipts)
        with self.assertRaises(RuntimeError):
            executor("restart_service",{"host":"pentium","service":"atlas-dashboard.service"})
        self.assertEqual(self.action_spool.read(),())

    def test_incorrect_target_cannot_claim_incident(self):
        self.owner.run_once()
        self.executor("restart_service",{"host":"pentium","service":"other.service"})
        self.assertEqual(self.action_spool.read(),())

    def test_wrong_producer_pubkey_denies_authenticated_learning(self):
        self.owner.run_once()
        self.executor("restart_service",{"host":"pentium","service":"atlas-dashboard.service"})
        self.probe.state=S.HEALTHY
        self.owner.run_once();self.owner.run_once()
        receipts=(self.action_spool.read()[0],*self.probe_spool.read())
        invalid=Ed25519RecoveryVerifier(
            {"executor":{"executor-k1":Ed25519PrivateKey.generate().public_key()},
             "health_probe":{"probe-k1":self.health_key.public_key()}},
            trusted_host="pentium",clock=lambda: START+timedelta(minutes=5))
        with self.assertRaises(ReceiptV2Error):
            learn_from_ed25519_recovery(self.memory,incident_id=receipts[0]["incident_id"],
                    cause="timeout",correction="inspect",
                    receipts=receipts,verifier=invalid)
        self.assertEqual(self.memory.stats()["lessons"],0)

    def test_probe_receipts_are_not_reused_for_another_action(self):
        self.owner.run_once()
        self.executor("restart_service",{"host":"pentium","service":"atlas-dashboard.service"})
        self.probe.state=S.HEALTHY
        self.owner.run_once();self.owner.run_once()
        first=self.probe_spool.read()
        # A completed incident cannot sign another action under its identity.
        self.executor("restart_service",{"host":"pentium","service":"atlas-dashboard.service"})
        self.assertEqual(len(self.action_spool.read()),1)
        self.assertEqual(len(self.probe_spool.read()),2)
        forged=(dict(self.action_spool.read()[0],action_id="another-action"),*first)
        with self.assertRaises(ReceiptV2Error):
            self.verifier.verify(self.memory.get_incident(forged[0]["incident_id"]),forged)

    def test_tampered_spool_json_cannot_authenticate(self):
        self.owner.run_once()
        self.executor("restart_service",{"host":"pentium","service":"atlas-dashboard.service"})
        signed=dict(self.action_spool.read()[0])
        signed["status"]="failed"
        with self.assertRaises(ReceiptV2Error):
            self.verifier.verify_action(signed)

    def test_signer_role_and_keys_do_not_cross(self):
        with self.assertRaises(ValueError):
            Ed25519ReceiptSigner("health_probe","probe-k1",self.action_key,expected_role="executor")
        with self.assertRaises(ValueError):
            Ed25519RecoveryVerifier({
              "executor":{"e":self.action_key.public_key()},
              "health_probe":{"h":self.action_key.public_key()}},trusted_host="pentium")

    def test_spool_blocks_symlink(self):
        link=self.root/"alias.jsonl"
        try:
            link.symlink_to(self.root/"action.jsonl")
        except OSError:
            self.skipTest("Windows symlink privilege unavailable")
        with self.assertRaises(ReceiptV2Error):
            SignedReceiptSpool(link).append({"anything":"malicious"})


class FactoryTests(unittest.TestCase):
    def test_key_files_runtime_env_and_role_isolation(self):
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PrivateFormat, PublicFormat, NoEncryption,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            act=Ed25519PrivateKey.generate()
            health=Ed25519PrivateKey.generate()
            act_path=root/"action-key.pem"
            health_path=root/"health-key.pem"
            pub_path=root/"action-public.pem"
            act_path.write_bytes(act.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()))
            health_path.write_bytes(health.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()))
            pub_path.write_bytes(act.public_key().public_bytes(Encoding.PEM,PublicFormat.SubjectPublicKeyInfo))
            env={
                "ATLAS_SENTRY_V2_EXECUTOR_ENABLED":"1",
                "ATLAS_SENTRY_V2_HEALTH_ENABLED":"1",
                "ATLAS_SENTRY_V2_EXECUTOR_PRIVATE_KEY_FILE":str(act_path),
                "ATLAS_SENTRY_V2_HEALTH_PRIVATE_KEY_FILE":str(health_path),
                "ATLAS_SENTRY_V2_EXECUTOR_PUBLIC_KEY_FILE":str(pub_path),
                "ATLAS_SENTRY_V2_EXECUTOR_KEY_ID":"executor-k1",
                "ATLAS_SENTRY_V2_HEALTH_KEY_ID":"health-k1",
            }
            if os.name!="nt":
                act_path.chmod(0o600);health_path.chmod(0o600)
            memory=FailureMemory(root/"memory.db")
            try:
                self.assertIsNone(build_executor_receipt_sink(root,memory,environ={}))
                self.assertIsNone(build_health_receipt_sink(root,memory,environ={}))
                execution=build_executor_receipt_sink(root,memory,environ=env)
                probing=build_health_receipt_sink(root,memory,environ=env)
                self.assertEqual(execution.signer.role,"executor")
                self.assertEqual(probing.signer.role,"health_probe")
                self.assertNotEqual(execution.signer.public_key().public_bytes(
                    Encoding.Raw,PublicFormat.Raw),probing.signer.public_key().public_bytes(
                    Encoding.Raw,PublicFormat.Raw))
                with self.assertRaises(ReceiptV2Error):
                    build_executor_receipt_sink(root,None,environ=env)
                with self.assertRaises(ReceiptV2Error):
                    build_health_receipt_sink(root,None,environ=env)
                broken=dict(env)
                broken["ATLAS_SENTRY_V2_EXECUTOR_PRIVATE_KEY_FILE"]=str(pub_path)
                with self.assertRaises((ReceiptV2Error,ValueError)):
                    build_executor_receipt_sink(root,memory,environ=broken)
            finally:memory.close()

    def test_bad_signer_path_denied(self):
        with self.assertRaises(ReceiptV2Error):
            load_signer_from_file(Path("relative.pem"),role="executor",key_id="key1")


if __name__=="__main__":unittest.main()
