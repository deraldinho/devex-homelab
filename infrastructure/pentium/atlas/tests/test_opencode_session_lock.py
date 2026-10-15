import tempfile
import unittest
from pathlib import Path
from infrastructure.pentium.atlas.opencode_session_ledger import SessionLedger

class SessionLockTests(unittest.TestCase):
    def test_exclusive_lock_across_instances(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"state.json"
            a,b=SessionLedger(p),SessionLedger(p)
            held=a.acquire()
            with self.assertRaises(TimeoutError):b.acquire()
            a.release(held)
            second=b.acquire()
            b.release(second)
    def test_crash_lock_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            a=SessionLedger(Path(folder)/"state.json")
            a.acquire()
            with self.assertRaises(TimeoutError):a.acquire()
if __name__=="__main__":unittest.main()
