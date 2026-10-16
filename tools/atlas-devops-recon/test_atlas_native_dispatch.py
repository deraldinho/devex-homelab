import tempfile
import unittest
from pathlib import Path
from atlas_native_workflow import submit,decide
from atlas_native_dispatch import enqueue_readonly_review,list_pending

ROOT=Path(__file__).resolve().parent

class NativeDispatchTests(unittest.TestCase):
    def test_idempotent_pending_readonly_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.db"
            submit(db,"m1",ROOT)
            decide(db,"m1",True)
            first=enqueue_readonly_review(db,"m1","qa")
            second=enqueue_readonly_review(db,"m1","qa")
            self.assertEqual(first,second)
            self.assertEqual(len(list_pending(db)),1)
            self.assertFalse(first["execution_authorized"])
            self.assertTrue(first["payload"]["read_only"])
    def test_no_approval_no_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.db"
            submit(db,"m2",ROOT)
            with self.assertRaises(PermissionError):
                enqueue_readonly_review(db,"m2","qa")
            self.assertEqual(list_pending(db),[])
    def test_role_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                enqueue_readonly_review(Path(tmp)/"db","unknown","shell")
    def test_drift_blocks_pending_outbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.db"
            root=Path(tmp)/"project"
            root.mkdir()
            import shutil
            from atlas_native_workflow import REQUIRED
            for name in REQUIRED: shutil.copyfile(ROOT/name,root/name)
            submit(db,"m3",root)
            decide(db,"m3",True)
            enqueue_readonly_review(db,"m3","qa")
            (root/REQUIRED[0]).write_text("changed",encoding="utf-8")
            self.assertEqual(enqueue_readonly_review(db,"m3","qa")["status"],"BLOCKED_DRIFT")
            self.assertEqual(list_pending(db),[])
