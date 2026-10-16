"""Slice 2 TDD: recibos operacionais duraveis, isolados da memoria cognitiva."""
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from infrastructure.pentium.atlas.agency_specialists import (
    AgencyConfig, AgencyGateway, AgencyRequest,
)
from infrastructure.pentium.atlas.memory_store import MemoryStore, MemoryStoreError
from infrastructure.pentium.atlas.self_work import SelfWorkRuntime


def _config():
    return AgencyConfig(1, True, "core", "atlas-specialists", 2, 30, 8192, ("atlas",))


def _gateway(store, worker):
    runtime = SelfWorkRuntime(id_factory=lambda: "sw-receipt", max_inferences=4)
    now = datetime.now(timezone.utc).isoformat()
    runtime.propose("testar falha simulada", "engineering", now=now)
    runtime.activate(now=now)
    runtime.begin_work(now=now)
    return AgencyGateway(_config(), runtime, worker, memory_store=store)


class AgencyFailureReceiptTests(unittest.TestCase):
    def test_durable_receipt_survives_restart_without_episodic_contamination(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "memory.db"
            store = MemoryStore(path)
            gateway = _gateway(store, Mock(side_effect=RuntimeError("Bearer test-secret")))
            result = gateway.execute(AgencyRequest("sw-receipt", "atlas", "diagnosticar"))
            self.assertEqual("failed", result.status)
            self.assertEqual("worker_unavailable", result.reason)
            self.assertEqual(1, gateway.snapshot()["failure_receipts_persisted"])
            self.assertEqual(0, store.count())
            store.close()
            reopened = MemoryStore(path)
            receipts = reopened.list_agency_failure_receipts(task_id="sw-receipt")
            self.assertEqual(1, len(receipts))
            self.assertEqual("worker_unavailable", receipts[0]["reason_code"])
            self.assertEqual(1, receipts[0]["schema_version"])
            self.assertEqual("atlas", receipts[0]["project"])
            self.assertNotIn("secret", str(receipts))
            self.assertEqual(0, reopened.count())
            reopened.close()

    def test_duplicate_event_is_idempotent_and_conflicting_replay_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.db")
            data = dict(event_id="01HV0000000000000000000001", task_id="task-a",
                        project="atlas", reason_code="worker_unavailable",
                        attempt=1, created_at="2026-10-16T12:00:00+00:00")
            self.assertTrue(store.record_agency_failure_receipt(**data))
            self.assertFalse(store.record_agency_failure_receipt(**data))
            with self.assertRaises(MemoryStoreError):
                store.record_agency_failure_receipt(**{**data, "reason_code": "invalid_worker_result"})
            self.assertEqual(1, len(store.list_agency_failure_receipts(task_id="task-a")))
            store.close()

    def test_untrusted_free_text_is_rejected_and_not_saved(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.db")
            with self.assertRaises(ValueError):
                store.record_agency_failure_receipt(
                    event_id="event-1", task_id="task-1", project="atlas",
                    reason_code="Bearer synthetic-secret", attempt=1,
                    created_at="2026-10-16T12:00:00+00:00")
            self.assertEqual((), store.list_agency_failure_receipts())
            store.close()

    def test_retention_is_explicit_bounded_and_does_not_touch_cognitive_memory(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.db")
            for n, at in enumerate(("2026-10-01T12:00:00+00:00", "2026-10-02T12:00:00+00:00",
                                    "2026-10-03T12:00:00+00:00"), 1):
                store.record_agency_failure_receipt(
                    event_id=f"event-{n}", task_id="task-ret", project="atlas",
                    reason_code="worker_unavailable", attempt=n, created_at=at)
            self.assertEqual(1, store.prune_agency_failure_receipts(
                before_utc="2026-10-03T12:00:00+00:00", max_delete=1))
            self.assertEqual(2, len(store.list_agency_failure_receipts()))
            self.assertEqual(1, store.prune_agency_failure_receipts(
                before_utc="2026-10-03T12:00:00+00:00", max_delete=1))
            self.assertEqual(1, len(store.list_agency_failure_receipts()))
            with self.assertRaises(ValueError):
                store.prune_agency_failure_receipts(before_utc="yesterday")
            self.assertEqual(0, store.count())
            store.close()

    def test_failure_of_receipt_store_does_not_change_worker_failure_result(self):
        broken = Mock()
        broken.record_agency_failure_receipt.side_effect = sqlite3.OperationalError("disk full")
        gateway = _gateway(broken, Mock(side_effect=RuntimeError("Bearer example")))
        result = gateway.execute(AgencyRequest("sw-receipt", "atlas", "diagnosticar"))
        self.assertEqual("failed", result.status)
        self.assertEqual("worker_unavailable", result.reason)
        self.assertEqual(0, gateway.snapshot()["failure_receipts_persisted"])
        self.assertEqual(1, gateway.snapshot()["failure_receipts_store_errors"])


if __name__ == "__main__":
    unittest.main()
