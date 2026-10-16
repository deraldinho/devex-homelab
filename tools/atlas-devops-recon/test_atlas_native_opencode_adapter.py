import tempfile
import unittest
from pathlib import Path
from atlas_native_workflow import submit,decide
from atlas_native_dispatch import enqueue_readonly_review
from atlas_native_executor import status
from atlas_native_opencode_adapter import process_review
ROOT=Path(__file__).resolve().parent
class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/"state.db"
        submit(self.db,"job",ROOT)
        decide(self.db,"job",True)
        self.task=enqueue_readonly_review(self.db,"job","security")["task_id"]
    def test_success_zero_cost_and_no_second_call(self):
        calls=[]
        def runner(payload):
            calls.append(payload)
            return {"status":"succeeded","cost":0,"text":"static findings"}
        self.assertEqual(process_review(self.db,self.task,runner)["status"],"SUCCEEDED")
        self.assertFalse(process_review(self.db,self.task,runner)["dispatched"])
        self.assertEqual(len(calls),1)
        self.assertEqual(status(self.db,self.task)["attempt"],1)
    def test_exception_does_not_replay(self):
        calls=[]
        def failing(payload):
            calls.append(1)
            raise TimeoutError()
        self.assertEqual(process_review(self.db,self.task,failing)["status"],"IN_FLIGHT")
        self.assertFalse(process_review(self.db,self.task,failing)["dispatched"])
        self.assertEqual(len(calls),1)
    def test_nonzero_cost_does_not_certify(self):
        result=process_review(self.db,self.task,lambda _:{"status":"succeeded","cost":1})
        self.assertEqual(result["status"],"IN_FLIGHT")
    def test_ambiguous_status_stays_pending(self):
        result=process_review(self.db,self.task,lambda _:{"status":"running","cost":0})
        self.assertEqual(result["status"],"IN_FLIGHT")
