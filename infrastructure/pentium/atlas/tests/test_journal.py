import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.journal import JournalError, append_event
from infrastructure.pentium.atlas.state_model import (
    GlobalAssessment,
    ReactionDecision,
    TechnicalState,
)


def sample_assessment(state=TechnicalState.BUSY):
    return GlobalAssessment(
        previous_state=TechnicalState.HEALTHY,
        state=state,
        intensity=2,
        reasons=("core:core.cpu.high",),
        recovered=False,
    )


class JournalTests(unittest.TestCase):
    def test_append_event_writes_independent_jsonl_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "events.jsonl"
            decision = ReactionDecision("busy", "busy.tech.01", "meme.busy.01")
            append_event(path, "2026-09-03T19:00:00-03:00", sample_assessment(), decision)
            append_event(path, "2026-09-03T19:01:00-03:00", sample_assessment(), decision)
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["state"], "busy")
            self.assertEqual(records[0]["previous_state"], "healthy")
            self.assertEqual(records[0]["reaction_category"], "busy")
            self.assertEqual(records[0]["reaction_id"], "busy.tech.01")
            self.assertEqual(records[0]["meme_id"], "meme.busy.01")

    def test_write_failure_is_wrapped_as_journal_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent_file = Path(tmp) / "not-a-directory"
            parent_file.write_text("x", encoding="utf-8")
            path = parent_file / "events.jsonl"
            with self.assertRaises(JournalError):
                append_event(
                    path,
                    "2026-09-03T19:00:00-03:00",
                    sample_assessment(),
                    ReactionDecision("busy", "busy.tech.01"),
                )


if __name__ == "__main__":
    unittest.main()
