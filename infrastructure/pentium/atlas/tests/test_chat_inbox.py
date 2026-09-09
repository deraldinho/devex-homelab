import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from infrastructure.pentium.atlas.chat_inbox import ChatInbox


class ChatInboxTests(unittest.TestCase):
    def test_enqueue_is_idempotent_by_client_message_id(self):
        with TemporaryDirectory() as tmp:
            inbox=ChatInbox(Path(tmp)/"chat-inbox.json")
            first=inbox.enqueue("Como esta o x99?","client-1")
            second=inbox.enqueue("Como esta o x99?","client-1")
            self.assertEqual(first.message_id,second.message_id)
            self.assertEqual(first.stimulus_id,second.stimulus_id)
            self.assertEqual(1,inbox.pending_count())

    def test_oversized_text_is_rejected(self):
        with TemporaryDirectory() as tmp:
            inbox=ChatInbox(Path(tmp)/"chat-inbox.json",max_message_chars=512)
            with self.assertRaises(ValueError): inbox.enqueue("x"*513,"client-2")

    def test_claim_and_ack_are_durable_and_bounded(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"chat-inbox.json"; inbox=ChatInbox(path,max_items=3)
            a=inbox.enqueue("a","c1"); claimed=inbox.claim_next()
            self.assertEqual(a.message_id,claimed.message_id)
            inbox.ack(a.message_id); self.assertEqual(0,inbox.pending_count())
            for i in range(5):
                env=inbox.enqueue(str(i),f"c-{i+10}"); inbox.ack(env.message_id)
            self.assertLessEqual(len(inbox.list_items()),3)

    def test_claim_returns_none_when_empty(self):
        with TemporaryDirectory() as tmp:
            self.assertIsNone(ChatInbox(Path(tmp)/"chat-inbox.json").claim_next())
