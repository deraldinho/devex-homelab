"""Adversarial session ownership regression tests."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from atlas_native_workflow import submit,decide
from atlas_native_dispatch import enqueue_readonly_review
from atlas_native_executor import claim
from atlas_native_session_registry import bind_session,session_for_task

ROOT=Path(__file__).resolve().parent
class SessionConcurrencyTests(unittest.TestCase):
    def test_same_session_cannot_bind_two_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.db"
            submit(db,"collision-mission",ROOT)
            decide(db,"collision-mission",True)
            ids=[]
            for role in ("qa","security"):
                task=enqueue_readonly_review(db,"collision-mission",role)["task_id"]
                claim(db,task)
                ids.append(task)
            bind_session(db,ids[0],"session-one","worker")
            with self.assertRaises(Exception):
                bind_session(db,ids[1],"session-one","worker")
            self.assertIsNone(session_for_task(db,ids[1]))
    def test_concurrent_conflicting_bindings_never_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.db"
            submit(db,"concurrent",ROOT)
            decide(db,"concurrent",True)
            task=enqueue_readonly_review(db,"concurrent","qa")["task_id"]
            claim(db,task)
            def bind(n):
                try:
                    bind_session(db,task,"session-"+str(n),"worker")
                    return True
                except ValueError:
                    return False
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(bind,[1,2]))
            self.assertEqual(sum(results),1)
            self.assertIn(session_for_task(db,task)["session_id"],("session-1","session-2"))
