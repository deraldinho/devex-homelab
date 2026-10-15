"""Deterministic CP-ORCH-07 watchdog unit gates: no scheduler side effects."""
import unittest
import tempfile
from pathlib import Path
from atlas_worker_watchdog import Observation, decision, MAX_HEARTBEAT_AGE_S, unresolved_approvals


def o(task="Ready", n=0, age=500, approved=0, attempted=0):
    return Observation(task, n, age, approved, attempted)


class RecoveryPolicyTests(unittest.TestCase):
    def test_healthy(self):
        self.assertEqual(decision(o("Running", 1, 15)), "HEALTHY")
    def test_stale_worker_alive_never_restarts(self):
        self.assertEqual(decision(o("Running", 1, 500)), "BLOCKED_STALE_LIVE_WORKER")
    def test_duplicate_detected(self):
        self.assertEqual(decision(o("Running", 2, 15)), "BLOCKED_MULTIPLE_WORKERS")
    def test_running_without_process_never_restarts(self):
        self.assertEqual(decision(o("Running", 0)), "BLOCKED_STARTING_OR_INCONSISTENT")
    def test_pending_approved_never_autorestarts(self):
        self.assertEqual(decision(o("Ready", 0, 500, 1)), "BLOCKED_RECONCILE_APPROVED_WORK")
    def test_already_attempted_never_autorestarts(self):
        self.assertEqual(decision(o("Ready", 0, 500, 0, 1)), "BLOCKED_RECONCILE_APPROVED_WORK")
    def test_task_disabled_never_restarts(self):
        self.assertEqual(decision(o("Disabled", 0)), "BLOCKED_TASK_NOT_READY")
    def test_recent_heartbeat_never_restarts(self):
        self.assertEqual(decision(o("Ready", 0, 5)), "NO_ACTION_RECENT_HEARTBEAT")
    def test_old_heartbeat_safe_restart_only_if_no_work(self):
        self.assertEqual(decision(o()), "SAFE_TO_RESTART")
    def test_boundary_heartbeat(self):
        self.assertEqual(decision(o(age=MAX_HEARTBEAT_AGE_S)), "NO_ACTION_RECENT_HEARTBEAT")


    def test_unresolved_approvals_block_recovery_despite_zero_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approvals = root / "approvals"
            approvals.mkdir()
            (approvals / "5f8b8a94-5aed-4b01-bb28-3b0c89e4f49f.json").write_text("{}")
            self.assertEqual(unresolved_approvals(root), 1)
            self.assertEqual(decision(o(approved=unresolved_approvals(root))), "BLOCKED_RECONCILE_APPROVED_WORK")

    def test_terminal_marker_excludes_finished_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_id = "5f8b8a94-5aed-4b01-bb28-3b0c89e4f49f"
            approvals = root / "approvals"
            approvals.mkdir()
            (approvals / (task_id + ".json")).write_text("{}")
            terminal = root / "jobs" / task_id / "terminal.json"
            terminal.parent.mkdir(parents=True)
            terminal.write_text('{"schema_version":1,"task_id":"' + task_id + '","state":"completed"}')
            self.assertEqual(unresolved_approvals(root), 0)
            terminal.write_text('{"schema_version":1,"task_id":"wrong","state":"completed"}')
            self.assertEqual(unresolved_approvals(root), 1)

if __name__ == "__main__":
    unittest.main()
