import tempfile
import unittest
from pathlib import Path
from atlas_native_workflow import submit, decide

ROOT = Path(__file__).resolve().parent

class NativeWorkflowTests(unittest.TestCase):
    def test_idempotent_resume_across_connections(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.sqlite"
            first=submit(db,"cp19",ROOT)
            self.assertEqual(first["status"],"REVIEW_PENDING")
            self.assertEqual(submit(db,"cp19",ROOT),first)
            self.assertEqual(decide(db,"cp19",True)["status"],"REVIEW_APPROVED")
            self.assertEqual(submit(db,"cp19",ROOT)["status"],"REVIEW_APPROVED")
            self.assertFalse(decide(db,"cp19",True)["execution_authorized"])
    def test_denied_is_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.sqlite"
            submit(db,"deny",ROOT)
            self.assertEqual(decide(db,"deny",False)["status"],"REVIEW_DENIED")
            self.assertEqual(decide(db,"deny",True)["status"],"REVIEW_DENIED")
    def test_missing_baseline_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.sqlite"
            self.assertEqual(submit(db,"missing",tmp)["status"],"BLOCKED_BASELINE")
            self.assertEqual(decide(db,"missing",True)["status"],"BLOCKED_BASELINE")
    def test_id_collision_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.sqlite"
            submit(db,"collision",ROOT)
            with self.assertRaises(ValueError):
                submit(db,"collision",tmp)
    def test_requires_boolean_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.sqlite"
            submit(db,"type",ROOT)
            with self.assertRaises(TypeError):
                decide(db,"type","true")
