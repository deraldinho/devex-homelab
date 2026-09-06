from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from infrastructure.pentium.agent.control_audit import ControlAuditJournal, ControlAuditRecord


class ControlAuditTests(unittest.TestCase):
    def record(self, *, phase="attempt", status="authorized"):
        return ControlAuditRecord(
            timestamp=datetime(2026, 9, 6, 18, 0, tzinfo=timezone.utc),
            phase=phase,
            host_id="x99",
            operation="restart_service",
            target="docker",
            authorized=True,
            status=status,
            reason="policy_authorized",
        )

    def test_jsonl_journal_persists_bounded_deterministic_record(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "control-audit.jsonl"
            ControlAuditJournal(path).append(self.record())
            payload = json.loads(path.read_text(encoding="utf-8").strip())
            self.assertEqual(payload["host_id"], "x99")
            self.assertEqual(payload["phase"], "attempt")
            self.assertEqual(payload["target"], "docker")
