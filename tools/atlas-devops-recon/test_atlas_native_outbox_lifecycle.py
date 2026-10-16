import tempfile,unittest
from pathlib import Path
from atlas_native_workflow import submit,decide
from atlas_native_dispatch import enqueue_readonly_review,list_pending
from atlas_native_executor import claim,finish
ROOT=Path(__file__).resolve().parent
class LifecycleTests(unittest.TestCase):
    def test_success_does_not_remain_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.db"
            submit(db,"lifecycle",ROOT);decide(db,"lifecycle",True)
            task=enqueue_readonly_review(db,"lifecycle","qa")["task_id"]
            claim(db,task)
            finish(db,task,{"status":"SUCCEEDED","cost":0})
            self.assertEqual(list_pending(db),[])
    def test_claimed_task_is_not_unclaimed_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.db"
            submit(db,"claim",ROOT);decide(db,"claim",True)
            task=enqueue_readonly_review(db,"claim","qa")["task_id"]
            claim(db,task)
            self.assertEqual(list_pending(db),[])
