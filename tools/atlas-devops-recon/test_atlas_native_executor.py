import tempfile
import unittest
from pathlib import Path
from atlas_native_workflow import submit,decide
from atlas_native_dispatch import enqueue_readonly_review
from atlas_native_executor import claim,finish,status

ROOT=Path(__file__).resolve().parent

class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/"state.sqlite"
        submit(self.db,"task",ROOT)
        decide(self.db,"task",True)
        self.task=enqueue_readonly_review(self.db,"task","qa")["task_id"]
    def test_claim_only_once_no_retry_unknown(self):
        a=claim(self.db,self.task)
        self.assertTrue(a["claimed"])
        self.assertFalse(a["payload"]["execution_authorized"])
        b=claim(self.db,self.task)
        self.assertFalse(b["claimed"])
        self.assertEqual(b["status"],"IN_FLIGHT")
        self.assertEqual(status(self.db,self.task)["attempt"],1)
    def test_terminal_receipt_idempotent(self):
        claim(self.db,self.task)
        r={"status":"SUCCEEDED","cost":0,"tool_activity":False}
        self.assertFalse(finish(self.db,self.task,r)["idempotent"])
        self.assertTrue(finish(self.db,self.task,r)["idempotent"])
        with self.assertRaises(ValueError):
            finish(self.db,self.task,{"status":"FAILED"})
    def test_reject_unclaimed_receipt(self):
        with self.assertRaises(KeyError):
            finish(self.db,self.task,{"status":"SUCCEEDED"})
    def test_reject_ambiguous_result(self):
        claim(self.db,self.task)
        with self.assertRaises(ValueError):
            finish(self.db,self.task,{"status":"TIMEOUT"})
        self.assertEqual(status(self.db,self.task)["status"],"IN_FLIGHT")
