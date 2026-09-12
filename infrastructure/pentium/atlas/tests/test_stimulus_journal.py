import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_compacts_to_most_recent_records_when_record_limit_is_exceeded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stimuli.jsonl"
            for index in range(5):
                append_stimulus(path, sample_stimulus(f"stim-{index}"), {}, max_records=3, max_bytes=4096)
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([item["stimulus_id"] for item in records], ["stim-2", "stim-3", "stim-4"])

    def test_compacts_to_byte_limit_and_preserves_newest_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stimuli.jsonl"
            for index in range(8):
                append_stimulus(path, sample_stimulus(f"stim-{index}"), {"blob": "x" * 180}, max_records=8192, max_bytes=900)
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertLessEqual(path.stat().st_size, 900)
            self.assertEqual(records[-1]["stimulus_id"], "stim-7")
    def test_record_limit_compaction_creates_headroom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stimuli.jsonl"
            max_records = 64
            for index in range(max_records):
                append_stimulus(path, sample_stimulus(f"warm-{index}"), {}, max_records=max_records, max_bytes=65536)
            real_replace = __import__("os").replace
            replace_count = 0

            def counted_replace(src, dst):
                nonlocal replace_count
                replace_count += 1
                return real_replace(src, dst)

            with patch("infrastructure.pentium.atlas.stimulus_journal.os.replace", side_effect=counted_replace):
                for index in range(12):
                    append_stimulus(path, sample_stimulus(f"hot-{index}"), {}, max_records=max_records, max_bytes=65536)
            self.assertEqual(replace_count, 1)
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertLessEqual(len(records), max_records)
            self.assertEqual(records[-1]["stimulus_id"], "hot-11")

    def test_byte_limit_compaction_creates_headroom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stimuli.jsonl"
            max_bytes = 32768
            index = 0
            while path.stat().st_size < max_bytes * 0.95 if path.exists() else True:
                append_stimulus(path, sample_stimulus(f"warm-{index}"), {"blob": "x" * 180}, max_records=8192, max_bytes=max_bytes)
                index += 1
            real_replace = __import__("os").replace
            replace_count = 0

            def counted_replace(src, dst):
                nonlocal replace_count
                replace_count += 1
                return real_replace(src, dst)

            with patch("infrastructure.pentium.atlas.stimulus_journal.os.replace", side_effect=counted_replace):
                for index in range(12):
                    append_stimulus(path, sample_stimulus(f"hot-{index}"), {"blob": "x" * 180}, max_records=8192, max_bytes=max_bytes)
            self.assertEqual(replace_count, 1)
            self.assertLessEqual(path.stat().st_size, max_bytes)

    def test_oversized_record_is_rejected_before_file_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stimuli.jsonl"
            with self.assertRaises(StimulusJournalError):
                append_stimulus(path, sample_stimulus("huge"), {"blob": "x" * 1024}, max_records=8192, max_bytes=256)
            self.assertFalse(path.exists())

    def test_failed_atomic_replace_preserves_original_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stimuli.jsonl"
            append_stimulus(path, sample_stimulus("one"), {}, max_records=2, max_bytes=4096)
            original = path.read_bytes()
            with patch("infrastructure.pentium.atlas.stimulus_journal.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaises(StimulusJournalError):
                    append_stimulus(path, sample_stimulus("two"), {}, max_records=1, max_bytes=4096)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(path.with_name(path.name + ".tmp").exists())

    def test_cleanup_failure_never_masks_journal_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent_file = Path(tmp) / "not-a-directory"
            parent_file.write_text("x", encoding="utf-8")
            path = parent_file / "stimuli.jsonl"
            with patch.object(Path, "unlink", side_effect=NotADirectoryError("cleanup failed")):
                with self.assertRaises(StimulusJournalError):
                    append_stimulus(path, sample_stimulus(), {"runtime": "atlas"})
    def test_write_failure_is_wrapped(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent_file = Path(tmp) / "not-a-directory"
            parent_file.write_text("x", encoding="utf-8")
            path = parent_file / "stimuli.jsonl"
            with self.assertRaises(StimulusJournalError):
                append_stimulus(path, sample_stimulus(), {"runtime": "atlas"})


if __name__ == "__main__":
    unittest.main()
