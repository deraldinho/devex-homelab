import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.stimulus_journal import (
    StimulusJournalError,
    append_stimulus,
)
from infrastructure.pentium.atlas.stimulus_model import Stimulus, StimulusSeverity


def sample_stimulus(stimulus_id: str = "stim-1") -> Stimulus:
    return Stimulus(
        stimulus_id=stimulus_id,
        source="core",
        kind="status_changed",
        severity=StimulusSeverity.WARNING,
        timestamp="2026-09-04T01:00:00+00:00",
        payload={"status": "degraded"},
        novelty=0.8,
        correlation_id="corr-1",
        previous_fingerprint="aaa",
        current_fingerprint="bbb",
    )


class StimulusJournalTests(unittest.TestCase):
    def test_append_stimulus_writes_independent_jsonl_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "stimuli.jsonl"
            append_stimulus(path, sample_stimulus("one"), {"runtime": "atlas"})
            append_stimulus(path, sample_stimulus("two"), {"runtime": "atlas"})
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([item["stimulus_id"] for item in records], ["one", "two"])
            self.assertEqual(records[0]["severity"], "warning")
            self.assertEqual(records[0]["runtime_meta"], {"runtime": "atlas"})

    def test_write_failure_is_wrapped(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent_file = Path(tmp) / "not-a-directory"
            parent_file.write_text("x", encoding="utf-8")
            path = parent_file / "stimuli.jsonl"
            with self.assertRaises(StimulusJournalError):
                append_stimulus(path, sample_stimulus(), {"runtime": "atlas"})


if __name__ == "__main__":
    unittest.main()
