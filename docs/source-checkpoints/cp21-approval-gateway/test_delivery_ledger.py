import tempfile,unittest
from pathlib import Path
from atlas.delivery_ledger import DeliveryLedger

class DeliveryLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.t=[1000]
        self.d=DeliveryLedger(Path(self.tmp.name)/"d.db",clock=lambda:self.t[0],max_attempts=2)
        self.d.initialize();self.d.track("p1")
    def test_lease_exclusion_and_ack(self):
        self.assertTrue(self.d.acquire("p1"))
        self.assertFalse(self.d.acquire("p1"))
        self.assertTrue(self.d.ack("p1"))
        self.assertFalse(self.d.acquire("p1"))
    def test_retry_backoff_and_dead_letter(self):
        self.assertTrue(self.d.acquire("p1"))
        self.assertTrue(self.d.failed("p1"))
        self.assertFalse(self.d.acquire("p1"))
        self.t[0]+=30
        self.assertTrue(self.d.acquire("p1"))
        self.assertTrue(self.d.failed("p1"))
        self.assertEqual(self.d.status("p1"),("DEAD",2))
    def test_expired_lease_recovers(self):
        self.assertTrue(self.d.acquire("p1",lease_seconds=5))
        self.t[0]+=6
        self.assertTrue(self.d.acquire("p1"))
    def test_restart_preserves_state(self):
        self.d.acquire("p1")
        again=DeliveryLedger(self.d.db,clock=lambda:self.t[0])
        self.assertFalse(again.acquire("p1"))
if __name__=="__main__":unittest.main()
