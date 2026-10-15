import tempfile,unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from atlas.approval_inbox import DurableApprovalInbox

class DurableApprovalInboxTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"approvals.sqlite"
        self.inbox=DurableApprovalInbox(self.path)
        self.inbox.initialize()
        self.kw=dict(nonce="abc",proposal_id="p1",proposal_hash="a"*64,
                     approver="owner",verified=True,unexpired=True)
    def test_once_after_restart(self):
        self.assertTrue(self.inbox.claim(**self.kw))
        other=DurableApprovalInbox(self.path)
        self.assertFalse(other.claim(**self.kw))
    def test_same_proposal_different_nonce_denied(self):
        self.assertTrue(self.inbox.claim(**self.kw))
        self.assertFalse(self.inbox.claim(**dict(self.kw,nonce="different")))
    def test_unverified_denied(self):
        self.assertFalse(self.inbox.claim(**dict(self.kw,verified=False)))
        self.assertTrue(self.inbox.claim(**self.kw))
    def test_expired_denied(self):
        self.assertFalse(self.inbox.claim(**dict(self.kw,unexpired=False)))
    def test_bad_hash_denied(self):
        self.assertFalse(self.inbox.claim(**dict(self.kw,proposal_hash="xyz")))
    def test_concurrent_once(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:self.inbox.claim(**self.kw),range(8)))
        self.assertEqual(results.count(True),1)

if __name__=="__main__":unittest.main()
