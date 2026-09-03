import io
import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.cli import main


VALID = {
    "previous_state": "healthy",
    "signals": [
        {
            "source": "core",
            "state": "busy",
            "intensity": 1,
            "required": True,
            "reason": "core.cpu.high",
        }
    ],
}


class AtlasCliTests(unittest.TestCase):
    def run_cli(self, payload, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(list(args), stdin=io.StringIO(json.dumps(payload)), stdout=stdout, stderr=stderr)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_valid_snapshot_emits_stable_json(self):
        code, stdout, stderr = self.run_cli(VALID)
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        result = json.loads(stdout)
        self.assertEqual(result["assessment"]["state"], "busy")
        self.assertEqual(result["assessment"]["intensity"], 1)
        self.assertEqual(result["reaction"]["category"], "busy")

    def test_unknown_state_returns_contract_error(self):
        payload = {"signals": [{"source": "core", "state": "melting", "intensity": 4}]}
        code, stdout, stderr = self.run_cli(payload)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("invalid input", stderr.lower())

    def test_invalid_schema_does_not_create_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "events.jsonl"
            code, stdout, _ = self.run_cli({"signals": "bad"}, "--journal", str(journal))
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertFalse(journal.exists())

    def test_file_input_and_ascii_human_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / "snapshot.json"
            snapshot.write_text(json.dumps(VALID), encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = main(["--input", str(snapshot), "--human"], stdout=stdout, stderr=stderr)
            self.assertEqual(code, 0)
            stdout.getvalue().encode("ascii")
            self.assertIn("state=busy", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
