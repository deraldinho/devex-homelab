"""HMAC-v1 worker receipt contract: real independent canonicalization on both sides."""
import json, sys, tempfile, unittest, uuid
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/"CP-FLOW-01"))
sys.path.insert(0,str(ROOT/"worker_candidate"))
sys.path.insert(0,str(ROOT))
from atlas.delegation_bridge import DelegationBridge
from atlas.self_work import SelfWorkRuntime
from atlas.task_capability_executor import TaskCapabilityExecutor
import atlas_flow_worker as w

class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.bridge=DelegationBridge(self.root)
        self.task_id=str(uuid.uuid4())
        self.item=SimpleNamespace(item_id=self.task_id,area="sandbox",
            objective="Verificar recibos autenticados da operacao de Atlas",
            created_at=datetime.now(timezone.utc).isoformat())
        self.bridge.propose(self.item)
        self.key=bytes(range(32))

    def signed(self, **kwargs):
        payload={"task_id":self.task_id,"state":"completed","model":"free-model",
            "reason":"quality_checks_passed","session_id":"test-session",
            "nonce":"a"*32,"sent_at":datetime.now(timezone.utc).isoformat()}
        payload.update(kwargs)
        payload["signature"]=w.sign_report_payload(payload,self.key)
        return payload

    def test_valid_signature_cross_runtime(self):
        (self.root/"worker-report.key").write_bytes(self.key)
        packet=self.signed()
        self.bridge.write_result(packet)
        verified=self.bridge.read_verified_result(self.task_id)
        self.assertIsNotNone(verified)
        self.assertEqual(verified["session_id"],"test-session")

    def test_invalid_signature_is_rejected_on_write(self):
        (self.root/"worker-report.key").write_bytes(self.key)
        packet=self.signed()
        packet["model"]="forged-provider"
        with self.assertRaisesRegex(ValueError,"unauthenticated"):
            self.bridge.write_result(packet)
        self.assertIsNone(self.bridge.read_verified_result(self.task_id))

    def test_no_signing_key_never_authenticates_legacy_result(self):
        with self.assertRaisesRegex(ValueError,"key required"):
            self.bridge.write_result({"task_id":self.task_id,"state":"completed",
                                      "session_id":"fake-legacy"})
        self.bridge.results.mkdir(parents=True, exist_ok=True)
        (self.bridge.results/(self.task_id+".json")).write_text(json.dumps({
            "task_id":self.task_id,"state":"completed","session_id":"historical-only"}))
        self.assertIsNotNone(self.bridge.read_result(self.task_id))
        self.assertIsNone(self.bridge.read_verified_result(self.task_id))

    def test_unsigned_completed_rejected_when_key_configured(self):
        (self.root/"worker-report.key").write_bytes(self.key)
        with self.assertRaisesRegex(ValueError,"unauthenticated"):
            self.bridge.write_result({"task_id":self.task_id,"state":"completed",
                                      "session_id":"fake-session"})

    def test_atlas_completion_requires_authentic_worker_receipt(self):
        runtime=SelfWorkRuntime()
        executor=TaskCapabilityExecutor(runtime,delegation_bridge=self.bridge)
        self.bridge.outbox.joinpath(self.task_id+".json").unlink()
        created=executor("task_create",{"objective":self.item.objective,"area":"sandbox"})
        self.assertEqual(created["status"],"CREATED")
        self.assertEqual(executor("task_complete",{"reason":"operator_request"})["status"],"DELEGATION_BLOCKED")
        (self.root/"worker-report.key").write_bytes(self.key)
        packet=self.signed(task_id=created["item_id"])
        self.bridge.write_result(packet)
        self.assertEqual(executor("task_complete",{"reason":"operator_request"})["status"],"COMPLETED")

    def test_oversized_signed_field_rejected_without_truncation(self):
        (self.root/"worker-report.key").write_bytes(self.key)
        payload=self.signed(session_id="s"*250)
        with self.assertRaisesRegex(ValueError,"oversized"):
            self.bridge.write_result(payload)
        self.assertIsNone(self.bridge.read_result(self.task_id))

    def test_stale_receipt_cannot_be_replayed(self):
        (self.root/"worker-report.key").write_bytes(self.key)
        payload=self.signed(sent_at="2020-01-01T00:00:00+00:00")
        with self.assertRaisesRegex(ValueError,"timestamp"):
            self.bridge.write_result(payload)

    def test_authenticated_nonterminal_replay_is_idempotent_and_old_timestamp_denied(self):
        from datetime import timedelta
        (self.root/"worker-report.key").write_bytes(self.key)
        timestamp=datetime.now(timezone.utc)
        running=self.signed(state="running",session_id="",sent_at=timestamp.isoformat())
        first=self.bridge.write_result(running)
        replay=self.bridge.write_result(running)
        self.assertEqual(first,replay)
        stale=self.signed(state="pending",session_id="",nonce="b"*32,
                         sent_at=(timestamp-timedelta(seconds=2)).isoformat())
        with self.assertRaisesRegex(ValueError,"out-of-order"):
            self.bridge.write_result(stale)

    def test_missing_key_and_forged_completed_never_complete_local_task(self):
        runtime=SelfWorkRuntime()
        executor=TaskCapabilityExecutor(runtime,delegation_bridge=self.bridge)
        (self.bridge.outbox/(self.task_id+".json")).unlink()
        created=executor("task_create",{"objective":self.item.objective,"area":"sandbox"})
        self.assertEqual(created["status"],"CREATED")
        with self.assertRaisesRegex(ValueError,"key required"):
            self.bridge.write_result({"task_id":created["item_id"],"state":"completed",
                                      "session_id":"forged-unsig-session"})
        self.assertIsNone(self.bridge.read_verified_result(created["item_id"]))
        self.assertEqual(executor("task_complete",{"reason":"operator_request"})["status"],"DELEGATION_BLOCKED")
        self.assertIsNotNone(runtime.current)

if __name__=="__main__":
    unittest.main()
