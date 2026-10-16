import tempfile,unittest
from pathlib import Path
from atlas_native_workflow import submit,decide
from atlas_native_delegation import delegate
from atlas_native_dispatch import list_pending
ROOT=Path(__file__).resolve().parent
class DelegationTests(unittest.TestCase):
    def test_bounded_idempotent_free_review_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.db"
            submit(db,"delegation",ROOT)
            decide(db,"delegation",True)
            roles=["architecture","security","qa"]
            a=delegate(db,"delegation",roles)
            b=delegate(db,"delegation",roles)
            self.assertEqual(a,b)
            self.assertEqual(len(list_pending(db)),3)
            self.assertTrue(all("-free" in m for x in a for m in x["models"]))
            self.assertTrue(all(not x["request"]["execution_authorized"] for x in a))
    def test_no_unbounded_or_nested_spawning(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.db"
            with self.assertRaises(PermissionError):
                delegate(db,"missing",["qa"],parent_role="qa")
            with self.assertRaises(ValueError):
                delegate(db,"missing",["qa"]*4)
            with self.assertRaises(ValueError):
                delegate(db,"missing",["qa","qa"])
