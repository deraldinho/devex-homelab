import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from infrastructure.pentium.atlas.action_plan import AtlasAction
from infrastructure.pentium.atlas.chat_inbox import ChatInbox

class ActionSecurityTests(unittest.TestCase):
    def test_shell_like_chat_is_inert_text(self):
        with TemporaryDirectory() as tmp:
            inbox=ChatInbox(Path(tmp)/'chat.json')
            env=inbox.enqueue('rm -rf / && systemctl stop atlas','c1')
            self.assertEqual('rm -rf / && systemctl stop atlas',env.message)
            self.assertEqual(1,inbox.pending_count())

    def test_forbidden_action_type_is_rejected(self):
        with self.assertRaises(ValueError): AtlasAction.create('SHELL',parameters={'command':'whoami'})

if __name__=='__main__': unittest.main()
