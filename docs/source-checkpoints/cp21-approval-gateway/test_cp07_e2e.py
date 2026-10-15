"""CP-ORCH-07 end-to-end approval, execution and callback using isolated fake launcher.

Runs REAL Atlas dispatcher, delegation bridge, approval record, worker state machine,
Git approval snapshot and terminal idempotence. The OpenCode inference is simulated.
"""
import json
import hashlib
import hmac
import secrets
from datetime import datetime, timezone
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "flow04"))
sys.path.insert(1, str(ROOT.parent / "CP-FLOW-01"))

from atlas.capability_dispatch import CapabilityDispatcher
from atlas.delegation_bridge import DelegationBridge, _receipt_body
from atlas.self_work import SelfWorkRuntime
from atlas.task_capability_executor import TaskCapabilityExecutor
import atlas_flow_worker as worker


class AtlasE2E(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.repo = self.root / "sandbox-repo"
        self.repo.mkdir()
        self._git("init", "-b", "main")
        (self.repo / "README.md").write_text("sandbox repo for Atlas E2E\n", encoding="utf-8")
        self._git("add", "README.md")
        self._git("-c", "user.name=Atlas Test", "-c", "user.email=atlas@example.invalid", "commit", "-m", "sandbox")
        self.bridge = DelegationBridge(self.root / "delegation")
        self.key = bytes(range(32))
        self.bridge.root.mkdir(parents=True, exist_ok=True)
        (self.bridge.root / "worker-report.key").write_bytes(self.key)
        self.runtime = SelfWorkRuntime(ttl_s=300)
        self.executor = TaskCapabilityExecutor(self.runtime, delegation_bridge=self.bridge)
        denied = lambda *args: {"status": "DENIED"}
        self.dispatcher = CapabilityDispatcher(denied, denied, task_executor=self.executor)
        self.objective = "Realizar verificacao segura da delegacao com testes automatizados"
        self.patches = [
            patch.object(worker, "STATE", self.root / "worker-state"),
            patch.object(worker, "APPROVALS", self.root / "worker-state" / "approvals"),
            patch.object(worker, "pending", self.bridge.list_pending),
            patch.object(worker, "repos", return_value={"sandbox": self.repo}),
            patch.object(worker, "send_status", self.write_result),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def _git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, timeout=10)

    def write_result(self, task_id, state, *, model="", reason="", session_id=""):
        packet = {"task_id": task_id, "state": state, "model": model,
                  "reason": reason, "session_id": session_id,
                  "nonce": secrets.token_hex(16),
                  "sent_at": datetime.now(timezone.utc).isoformat()}
        packet["signature"] = hmac.new(self.key, _receipt_body(packet), hashlib.sha256).hexdigest()
        return self.bridge.write_result(packet)

    def test_full_approval_execution_result_and_exactly_once(self):
        from unittest.mock import Mock
        created = self.dispatcher("task_create", {"objective": self.objective, "area": "sandbox"})
        self.assertEqual(created["status"], "CREATED")
        task_id = created["item_id"]
        self.assertEqual(self.bridge.list_pending()[0]["task_id"], task_id)
        self.assertFalse((worker.APPROVALS / (task_id + ".json")).exists())
        with patch.object(worker, "execute_one") as launch:
            self.assertEqual(worker.once()["attempted"], 0)
            launch.assert_not_called()
        # Explicit operator-equivalent approval action; never inferred from the proposal.
        approval = worker.approve(task_id, "sandbox")
        self.assertEqual(approval["approved_by"], "local_x99_operator")
        self.assertEqual(approval["objective_sha256"], worker.sha(self.objective))
        baseline = worker.baseline_for(self.bridge.list_pending()[0])
        self.assertTrue(worker.quality.valid(baseline))
        fake = Mock(return_value=SimpleNamespace(
            stdout=json.dumps({"status": "completed", "model": "free-model",
                                  "session_id": "cp07-synthetic-session", "cost": 0}),
            returncode=0))
        with patch.object(worker.quality, "review", return_value={"passed": True, "reason":"quality_checks_passed"}):
            with patch.object(worker.quality, "preflight", return_value=(True, "baseline_unchanged")):
                with patch.object(worker.subprocess, "run", wraps=subprocess.run) as real_sub:
                    # Redirect ONLY the fake agent-launch command, preserve other subprocess semantics.
                    def route(command, **kwargs):
                        if isinstance(command, list) and "run_atlas_build_agent.py" in str(command[1]):
                            return fake(command, **kwargs)
                        return subprocess.run(command, **kwargs)
                    real_sub.side_effect = route
                    self.assertEqual(worker.once()["attempted"], 1)
        self.assertEqual(fake.call_count, 1)
        result = self.dispatcher("task_status", {})
        self.assertEqual(result["delegation"]["task_id"], task_id)
        self.assertEqual(result["delegation"]["state"], "completed")
        self.assertEqual(result["delegation"]["session_id"], "cp07-synthetic-session")
        self.assertEqual(worker.once()["attempted"], 0)
        self.assertEqual(fake.call_count, 1)
        terminal = json.loads((worker.STATE / "jobs" / task_id / "terminal.json").read_text())
        self.assertEqual(terminal["state"], "completed")

    def test_modification_after_approval_invalidates_authorization(self):
        created = self.dispatcher("task_create", {"objective": self.objective, "area": "sandbox"})
        worker.approve(created["item_id"], "sandbox")
        altered = dict(self.bridge.list_pending()[0], objective="Alteracao maliciosa do objetivo")
        self.assertIsNone(worker.get_approval(altered))
        (self.repo / "README.md").write_text("drift\n")
        with patch.object(worker, "execute_one") as launch:
            # Approval's SHA remains bound to objective, but execution preflight must stop drift.
            candidate = self.bridge.list_pending()[0]
            authorized, why = worker.quality.preflight(
                self.repo, worker.baseline_for(candidate),
                title="ATLAS-DELEGATION-" + candidate["task_id"],
                objective=candidate["objective"])
            self.assertFalse(authorized, why)
            launch.assert_not_called()

if __name__ == "__main__":
    unittest.main()
