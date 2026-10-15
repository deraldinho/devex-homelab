import tempfile,unittest
from pathlib import Path
from infrastructure.pentium.atlas.opencode_usage_store import InferenceUsageStore

class UsageStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/"usage.db"
        self.store=InferenceUsageStore(self.db)
        self.store.initialize()
        self.event={"provider":"opencode","model":"free",
            "session_id":"sid-1","tokens_input":5,
            "tokens_output":7,"tokens_cache_read":20,
            "cost_usd":0,"duration_ms":10,"success":True}
    def test_records_once_after_reconciliation(self):
        self.assertTrue(self.store.record(self.event))
        self.assertFalse(self.store.record({**self.event,"duration_ms":0}))
        self.assertEqual(self.store.summary(),(1,5,7,20,0.0))
    def test_conflicting_usage_is_not_overwritten(self):
        self.store.record(self.event)
        with self.assertRaises(ValueError):
            self.store.record({**self.event,"tokens_output":900})
    def test_persistence_after_restart(self):
        self.store.record(self.event)
        again=InferenceUsageStore(self.db)
        self.assertEqual(again.summary()[0],1)
    def test_missing_session_id_is_not_counted(self):
        self.assertFalse(self.store.record({**self.event,"session_id":None}))
        self.assertEqual(self.store.summary()[0],0)
if __name__=="__main__":unittest.main()
