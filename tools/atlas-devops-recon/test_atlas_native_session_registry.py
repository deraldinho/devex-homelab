import tempfile
import unittest
from pathlib import Path
from atlas_native_workflow import submit, decide
from atlas_native_dispatch import enqueue_readonly_review
from atlas_native_executor import claim
from atlas_native_session_registry import bind_session, session_for_task

ROOT=Path(__file__).resolve().parent

class BindingTests(unittest.TestCase):
    def test_unique_persisted_binding_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.db"
            submit(db,"bind",ROOT)
            decide(db,"bind",True)
            task=enqueue_readonly_review(db,"bind","qa")["task_id"]
            claim(db,task)
            expected={"task_id":task,"session_id":"sid-1","issuer":"trusted-worker"}
            self.assertEqual(bind_session(db,task,"sid-1","trusted-worker"),expected)
            self.assertEqual(bind_session(db,task,"sid-1","trusted-worker"),expected)
            self.assertEqual(session_for_task(db,task)["session_id"],"sid-1")
            with self.assertRaises(ValueError):
                bind_session(db,task,"sid-2","trusted-worker")
    def test_unclaimed_cannot_bind(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):
                bind_session(Path(tmp)/"state.db","missing","sid","issuer")
