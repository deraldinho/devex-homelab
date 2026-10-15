import tempfile, unittest
from pathlib import Path
from atlas.discord_notification_outbox import NotificationOutbox

class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'outbox.db'
        self.store=NotificationOutbox(self.db)
        self.store.initialize()
        self.digest='a'*64

    def test_enqueue_idempotent(self):
        self.assertTrue(self.store.enqueue('p1',self.digest))
        self.assertFalse(self.store.enqueue('p1',self.digest))
        self.assertEqual(self.store.pending(), [('p1',self.digest)])

    def test_conflict_is_rejected(self):
        self.store.enqueue('p1',self.digest)
        with self.assertRaises(ValueError):
            self.store.enqueue('p1','b'*64)

    def test_ack_and_replay(self):
        self.store.enqueue('p1',self.digest)
        self.assertTrue(self.store.mark_sent('p1',self.digest,'msg-123'))
        self.assertFalse(self.store.mark_sent('p1',self.digest,'msg-456'))
        self.assertEqual(self.store.pending(),[])

    def test_recovery_after_restart(self):
        self.store.enqueue('p1',self.digest)
        self.assertEqual(NotificationOutbox(self.db).pending(), [('p1',self.digest)])
