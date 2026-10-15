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
    def test_closed_connection_releases_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            a=SessionLedger(Path(folder)/"state.json")
            held=a.acquire()
            with self.assertRaises(TimeoutError):a.acquire()
            held.close()  # simulates OS releasing lock after process termination
            next_lock=a.acquire()
            a.release(next_lock)
if __name__=="__main__":unittest.main()
