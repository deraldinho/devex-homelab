import tempfile
import unittest
from pathlib import Path
from atlas_native_workflow import submit, decide
from atlas_native_dispatch import enqueue_readonly_review
from atlas_native_executor import claim, status
from atlas_native_reconciler import reconcile_terminal
from atlas_native_session_registry import bind_session

ROOT = Path(__file__).resolve().parent

class ReconcilerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "state.db"
        submit(self.db, "reconcile", ROOT)
        decide(self.db, "reconcile", True)
        self.task = enqueue_readonly_review(self.db, "reconcile", "qa")["task_id"]
        claim(self.db, self.task)
        bind_session(self.db, self.task, "session-attested", "sandbox-reviewer")

    def receipt(self, **changes):
        data = dict(task_id=self.task, session_id="session-attested",
                    outcome="succeeded", cost=0, issuer="sandbox-reviewer")
        data.update(changes)
        return data

    def test_verified_terminal_success(self):
        result = reconcile_terminal(self.db, self.task, receipt=self.receipt(),
                                    verifier=lambda receipt: True)
        self.assertTrue(result["reconciled"])
        self.assertEqual(status(self.db, self.task)["status"], "SUCCEEDED")

    def test_unverified_or_ambiguous_keeps_in_flight(self):
        self.assertEqual(reconcile_terminal(self.db, self.task, receipt=self.receipt(),
                         verifier=lambda receipt: False)["status"], "IN_FLIGHT")
        self.assertEqual(reconcile_terminal(self.db, self.task,
                         receipt=self.receipt(outcome="running"),
                         verifier=lambda receipt: True)["status"], "IN_FLIGHT")
        self.assertEqual(status(self.db, self.task)["attempt"], 1)

    def test_invalid_task_fails_closed(self):
        with self.assertRaises(ValueError):
            reconcile_terminal(self.db, self.task, receipt=self.receipt(task_id="other"),
                               verifier=lambda receipt: True)
    def test_missing_session_or_nonzero_cost_does_not_complete(self):
        for item in [self.receipt(session_id=None), self.receipt(cost=1)]:
            self.assertEqual(reconcile_terminal(self.db, self.task, receipt=item,
                             verifier=lambda receipt: True)["status"], "IN_FLIGHT")
    def test_terminal_cannot_be_overwritten(self):
        reconcile_terminal(self.db, self.task, receipt=self.receipt(),
                           verifier=lambda receipt: True)
        result = reconcile_terminal(self.db, self.task,
                         receipt=self.receipt(outcome="failed"),
                         verifier=lambda receipt: True)
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertFalse(result["reconciled"])
