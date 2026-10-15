"""CP-ORCH-07: real dispatcher to task delegation fail-closed regression."""
import tempfile
import unittest
from pathlib import Path

from atlas.capability_dispatch import CapabilityDispatcher
from atlas.delegation_bridge import DelegationBridge
from atlas.self_work import SelfWorkRuntime, SelfWorkState
from atlas.task_capability_executor import TaskCapabilityExecutor

OBJECTIVE = "Inspecionar os documentos do projeto com aprovacao humana"

def signed_report(bridge, task_id, state, **kwargs):
    import hashlib, hmac, json, secrets
    from datetime import datetime, timezone
    key = bytes(range(32))
    (bridge.root / "worker-report.key").write_bytes(key)
    payload = {
        "task_id": task_id, "state": state,
        "model": str(kwargs.pop("model", "")),
        "reason": str(kwargs.pop("reason", "")),
        "session_id": str(kwargs.pop("session_id", "")),
        "nonce": secrets.token_hex(16),
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    assert not kwargs
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    payload["signature"] = hmac.new(key, raw, hashlib.sha256).hexdigest()
    return bridge.write_result(payload)



class UnwritableBridge:
    def propose(self, item, *, source_origin=None):
        raise OSError("simulated disk failure")
    def read_result(self, task_id):
        return None

class OrchestratedTaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runtime = SelfWorkRuntime()

    def dispatcher(self, bridge):
        executor = TaskCapabilityExecutor(self.runtime, delegation_bridge=bridge)
        denied = lambda *args: {"status": "DENIED"}
        return CapabilityDispatcher(denied, denied, task_executor=executor)

    def test_failed_proposal_does_not_claim_created_or_begin_work(self):
        dispatch = self.dispatcher(UnwritableBridge())
        result = dispatch("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        self.assertEqual(result["status"], "DELEGATION_BLOCKED")
        self.assertEqual(result["delegation"]["state"], "blocked")
        self.assertIsNotNone(result["item_id"])
        self.assertEqual(self.runtime.current.state, SelfWorkState.CANDIDATE)
        state = dispatch("task_status", {})
        self.assertEqual(state["item_id"], result["item_id"])
        self.assertEqual(state["status"], "CANDIDATE")

    def test_success_requires_external_approval(self):
        bridge = DelegationBridge(Path(self.tmp.name))
        dispatch = self.dispatcher(bridge)
        created = dispatch("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        self.assertEqual(created["status"], "CREATED")
        self.assertEqual(created["delegation"]["state"], "awaiting_approval")
        self.assertEqual(self.runtime.current.state, SelfWorkState.WORKING)
        proposals = bridge.list_pending()
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["task_id"], created["item_id"])
        self.assertFalse((bridge.results / (created["item_id"] + ".json")).exists())

    def test_external_completion_is_visible_for_same_task(self):
        bridge = DelegationBridge(Path(self.tmp.name))
        dispatch = self.dispatcher(bridge)
        created = dispatch("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        signed_report(bridge, created["item_id"], "completed", session_id="verified-session", model="free")
        result = dispatch("task_status", {})
        self.assertEqual(result["delegation"]["state"], "completed")
        self.assertEqual(result["delegation"]["task_id"], created["item_id"])

    def test_no_bridge_preserves_local_only_workflow(self):
        dispatch = self.dispatcher(None)
        result = dispatch("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        self.assertEqual(result["status"], "CREATED")
        self.assertNotIn("delegation", result)
        self.assertEqual(self.runtime.current.state, SelfWorkState.WORKING)

    def test_failed_proposal_cannot_be_retried_as_new_task_silently(self):
        dispatch = self.dispatcher(UnwritableBridge())
        first = dispatch("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        second = dispatch("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        self.assertEqual(first["status"], "DELEGATION_BLOCKED")
        self.assertEqual(second["status"], "ERROR")
        self.assertEqual(self.runtime.current.item_id, first["item_id"])
        cancelled = dispatch("task_abandon", {"reason": "manual_reconciliation"})
        self.assertEqual(cancelled["item_id"], first["item_id"])
        self.assertEqual(cancelled["status"], "RECONCILIATION_REQUIRED")
        self.assertEqual(self.runtime.current.state, SelfWorkState.CANDIDATE)

    def test_proposal_written_then_io_error_never_acknowledges_success(self):
        class AmbiguousBridge(DelegationBridge):
            def propose(self, item, *, source_origin=None):
                super().propose(item, source_origin=source_origin)
                raise OSError("acknowledgement lost after write")
        bridge = AmbiguousBridge(Path(self.tmp.name))
        dispatch = self.dispatcher(bridge)
        result = dispatch("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        self.assertEqual(result["status"], "DELEGATION_BLOCKED")
        self.assertEqual(self.runtime.current.state, SelfWorkState.CANDIDATE)
        self.assertEqual(len(bridge.list_pending()), 0)
        stored = next(bridge.outbox.glob("*.json"))
        self.assertEqual(__import__("json").loads(stored.read_text())["state"], "blocked")

    def test_unverified_external_task_cannot_be_completed_locally(self):
        bridge = DelegationBridge(Path(self.tmp.name))
        dispatch = self.dispatcher(bridge)
        created = dispatch("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        self.assertEqual(created["status"], "CREATED")
        result = dispatch("task_complete", {"reason": "manual_done"})
        self.assertEqual(result["status"], "DELEGATION_BLOCKED")
        self.assertEqual(self.runtime.current.state, SelfWorkState.WORKING)

    def test_blocked_candidate_cannot_be_completed(self):
        dispatch = self.dispatcher(UnwritableBridge())
        first = dispatch("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        self.assertEqual(first["status"], "DELEGATION_BLOCKED")
        result = dispatch("task_complete", {"reason": "premature"})
        self.assertEqual(result["status"], "DELEGATION_BLOCKED")
        self.assertEqual(self.runtime.current.state, SelfWorkState.CANDIDATE)

    def test_unexpected_bridge_error_is_classified_as_blocked(self):
        class CrashBridge:
            def propose(self, item, *, source_origin=None):
                raise RuntimeError("unexpected bridge fault")
        dispatch = self.dispatcher(CrashBridge())
        result = dispatch("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        self.assertEqual(result["status"], "DELEGATION_BLOCKED")
        self.assertEqual(self.runtime.current.state, SelfWorkState.CANDIDATE)

    def test_failed_local_activation_invalidates_persisted_proposal(self):
        class FailingRuntime(SelfWorkRuntime):
            def activate(self, *, now):
                raise RuntimeError("local activation failed")
        self.runtime = FailingRuntime()
        bridge = DelegationBridge(Path(self.tmp.name))
        dispatch = self.dispatcher(bridge)
        result = dispatch("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        self.assertEqual(result["status"], "DELEGATION_BLOCKED")
        self.assertEqual(len(bridge.list_pending()), 0)
        self.assertEqual(self.runtime.current.state, SelfWorkState.CANDIDATE)

    def test_abandon_invalidates_external_proposal(self):
        bridge = DelegationBridge(Path(self.tmp.name))
        dispatch = self.dispatcher(bridge)
        created = dispatch("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        self.assertEqual(len(bridge.list_pending()), 1)
        cancelled = dispatch("task_abandon", {"reason": "cancelado_pelo_operador"})
        self.assertEqual(cancelled["status"], "ABANDONED")
        self.assertEqual(len(bridge.list_pending()), 0)
        self.assertIsNone(self.runtime.current)

    def test_abandon_refuses_when_external_invalidation_fails(self):
        class RejectInvalidationBridge(DelegationBridge):
            def block_proposal(self, task_id, reason="local_abandoned"):
                raise OSError("outbox unavailable")
        bridge = RejectInvalidationBridge(Path(self.tmp.name))
        dispatch = self.dispatcher(bridge)
        created = dispatch("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        result = dispatch("task_abandon", {"reason": "operator_cancel"})
        self.assertEqual(result["status"], "RECONCILIATION_REQUIRED")
        self.assertEqual(self.runtime.current.item_id, created["item_id"])

    def test_inflight_execution_cannot_be_abandoned_silently(self):
        bridge = DelegationBridge(Path(self.tmp.name))
        dispatch = self.dispatcher(bridge)
        created = dispatch("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        signed_report(bridge, created["item_id"], "running")
        result = dispatch("task_abandon", {"reason": "operator_cancel"})
        self.assertEqual(result["status"], "RECONCILIATION_REQUIRED")
        self.assertEqual(len(bridge.list_pending()), 1)
        self.assertEqual(self.runtime.current.item_id, created["item_id"])

    def test_blocked_proposal_cannot_start_execution(self):
        from types import SimpleNamespace
        bridge = DelegationBridge(Path(self.tmp.name))
        item = SimpleNamespace(item_id=str(__import__("uuid").uuid4()), area="sandbox",
               objective=OBJECTIVE, created_at="2026-10-14T00:00:00+00:00")
        bridge.propose(item)
        self.assertTrue(bridge.block_proposal(item.item_id))
        with self.assertRaises(ValueError):
            bridge.write_result({"task_id": item.item_id, "state": "running"})

    def test_orphan_result_never_counts_as_external_evidence(self):
        import json, uuid
        bridge = DelegationBridge(Path(self.tmp.name))
        task_id = str(uuid.uuid4())
        bridge.results.mkdir(parents=True, exist_ok=True)
        (bridge.results / (task_id + ".json")).write_text(json.dumps({
           "task_id": task_id, "state": "completed", "session_id":"fake"}))
        self.assertIsNone(bridge.read_result(task_id))

    def test_discord_origin_preserved_only_for_trusted_envelope(self):
        from types import SimpleNamespace
        bridge = DelegationBridge(Path(self.tmp.name))
        runtime = SelfWorkRuntime()
        task = TaskCapabilityExecutor(runtime, delegation_bridge=bridge)
        task.set_source_origin(SimpleNamespace(channel="discord",
            actor_id="123456789", reply_target="987654321",
            client_message_id="discord:1234567890"))
        created = task("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        self.assertEqual(created["status"], "CREATED")
        self.assertEqual(bridge.list_pending()[0]["source_origin"]["reply_target"], "987654321")

    def test_untrusted_discord_origin_dropped(self):
        from types import SimpleNamespace
        bridge = DelegationBridge(Path(self.tmp.name))
        runtime = SelfWorkRuntime()
        task = TaskCapabilityExecutor(runtime, delegation_bridge=bridge)
        task.set_source_origin(SimpleNamespace(channel="discord",actor_id="../attack",
            reply_target="not-a-channel",client_message_id="discord:5"))
        created = task("task_create", {"objective": OBJECTIVE, "area": "sandbox"})
        self.assertEqual(created["status"], "CREATED")
        self.assertNotIn("source_origin", bridge.list_pending()[0])

if __name__ == "__main__":
    unittest.main()
