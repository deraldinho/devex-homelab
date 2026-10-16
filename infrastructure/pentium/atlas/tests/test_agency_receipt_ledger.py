"""CP28 durable agency ledger tests. No runtime or production SQLite touched."""
from __future__ import annotations

import concurrent.futures
import importlib.util
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "agency_receipt_ledger.py"
spec = importlib.util.spec_from_file_location("cp28_agency_receipts", SRC)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Ledger = module.AgencyReceiptLedger


class ReceiptLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "receipts.sqlite3")
        self.ledger = Ledger(self.path)

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def insert(self, key="idem-1", **kwargs):
        return self.ledger.insert(
            idempotency_key=key,
            task_id=kwargs.pop("task_id", "task-1"),
            specialist_id=kwargs.pop("specialist_id", "worker-1"),
            correlation_id=kwargs.pop("correlation_id", "trace-1"),
            summary=kwargs.pop("summary", "Tarefa aguardando"),
            **kwargs
        )

    def test_create_get_and_identical_duplicate_do_not_mutate(self):
        self.assertTrue(self.insert())
        one = self.ledger.get("idem-1")
        self.assertEqual(one["state"], "PENDING")
        self.assertFalse(self.insert())
        self.assertEqual(one, self.ledger.get("idem-1"))
        self.assertEqual(len(one), 11)

    def test_conflicting_duplicate_is_not_silently_accepted(self):
        self.insert()
        with self.assertRaises(ValueError):
            self.insert(task_id="other")
        self.assertEqual(self.ledger.get("idem-1")["task_id"], "task-1")

    def test_persistence_after_close_and_reopen(self):
        self.insert()
        self.ledger.close()
        reopened = Ledger(self.path)
        try:
            self.assertEqual(reopened.get("idem-1")["task_id"], "task-1")
        finally:
            reopened.close()
        self.ledger = Ledger(self.path)

    def test_identifiers_are_bounded_and_not_paths(self):
        for value in ("../bad", "/etc/passwd", "a"*129, "bad\nkey", "bad\\path", " "):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.insert(key=value)
        for value in ("../work", "b"*129, ""):
            with self.subTest(task=value), self.assertRaises(ValueError):
                self.insert(key="different", task_id=value)

    def test_summary_is_safe_and_bounded(self):
        self.assertTrue(self.insert(summary="<b>Validacao</b> ok"))
        self.assertEqual(self.ledger.get("idem-1")["summary"], "Validacao ok")
        with self.assertRaises(ValueError):
            self.insert(key="other", summary="<script>alert(1)</script>")
        with self.assertRaises(ValueError):
            self.insert(key="oversize", summary="A"*501)

    def test_retry_budget_requires_valid_integer(self):
        for n in (-1, 11, True, 1.5, "3"):
            with self.subTest(max_retries=n), self.assertRaises(ValueError):
                self.insert(key="badbudget", max_retries=n)

    def test_state_machine_blocks_invalid_and_terminal_transitions(self):
        self.insert()
        self.assertFalse(self.ledger.update_state("unknown", "PROCESSING"))
        self.assertTrue(self.ledger.update_state("idem-1", "PROCESSING"))
        self.assertTrue(self.ledger.update_state("idem-1", "COMPLETED"))
        for name in ("PENDING", "PROCESSING", "FAILED", "CANCELLED"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.ledger.update_state("idem-1", name)
        self.assertEqual(self.ledger.get("idem-1")["state"], "COMPLETED")

    def test_retry_is_bounded_and_only_from_failed_state(self):
        self.insert(max_retries=2)
        self.assertFalse(self.ledger.increment_retry("missing"))
        self.assertFalse(self.ledger.increment_retry("idem-1"))
        self.assertTrue(self.ledger.set_error("idem-1", "upstream timeout"))
        self.assertTrue(self.ledger.increment_retry("idem-1"))
        self.assertTrue(self.ledger.increment_retry("idem-1"))
        self.assertFalse(self.ledger.increment_retry("idem-1"))
        self.assertEqual(self.ledger.get("idem-1")["retry_count"], 2)

    def test_failure_retry_resets_only_after_recording_retry(self):
        self.insert()
        self.ledger.set_error("idem-1", "timeout")
        with self.assertRaises(ValueError):
            self.ledger.update_state("idem-1", "PENDING")
        self.ledger.increment_retry("idem-1")
        self.assertTrue(self.ledger.update_state("idem-1", "PENDING"))
        self.assertEqual(self.ledger.get("idem-1")["retry_count"], 1)

    def test_retry_receipt_cannot_be_replayed_twice(self):
        self.insert(max_retries=2)
        self.ledger.set_error("idem-1", "timeout-1")
        self.assertTrue(self.ledger.increment_retry("idem-1"))
        self.assertTrue(self.ledger.update_state("idem-1", "PENDING"))
        self.ledger.set_error("idem-1", "timeout-2")
        with self.assertRaises(ValueError):
            self.ledger.update_state("idem-1", "PENDING")
        self.assertTrue(self.ledger.increment_retry("idem-1"))
        self.assertTrue(self.ledger.update_state("idem-1", "PENDING"))
        self.ledger.set_error("idem-1", "timeout-3")
        with self.assertRaises(ValueError):
            self.ledger.update_state("idem-1", "PENDING")

    def test_terminal_receipts_cannot_be_rewritten_as_failure(self):
        self.insert()
        self.ledger.update_state("idem-1", "PROCESSING")
        self.ledger.update_state("idem-1", "COMPLETED")
        with self.assertRaises(ValueError):
            self.ledger.set_error("idem-1", "late error")
        self.assertFalse(self.ledger.increment_retry("idem-1"))

    def test_failure_messages_are_bounded(self):
        self.insert()
        self.ledger.set_error("idem-1", "<b>" + "x"*2000 + "</b>")
        message = self.ledger.get("idem-1")["error_message"]
        self.assertLessEqual(len(message), 500)
        self.assertNotIn("<", message)

    def test_invalid_correlation_id_is_rejected(self):
        for value in ("../../secret", "A"*200, object()):
            with self.subTest(value=type(value).__name__), self.assertRaises(ValueError):
                self.insert(correlation_id=value)

    def test_sql_metacharacters_cannot_inject(self):
        self.insert()
        with self.assertRaises(ValueError):
            self.ledger.get("' OR 1=1 --")
        self.assertIsNotNone(self.ledger.get("idem-1"))

    def test_concurrent_writers_share_exactly_one_receipt(self):
        def job(i):
            with Ledger(self.path) as ledger:
                return ledger.insert(
                    idempotency_key="concurrent-1",
                    task_id="task-concurrent",
                    specialist_id="worker-1",
                    correlation_id=None,
                    summary="Uma tarefa",
                )
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(job, range(16)))
        self.assertEqual(sum(results), 1)
        self.assertIsNotNone(self.ledger.get("concurrent-1"))


if __name__ == "__main__":
    unittest.main()
