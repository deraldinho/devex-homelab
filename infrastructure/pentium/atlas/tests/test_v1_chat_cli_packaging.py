import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / 'infrastructure' / 'pentium' / 'atlas'


class ChatCliPackagingTests(unittest.TestCase):
    def test_chat_cli_is_packaged_and_has_main(self):
        install = (ATLAS / 'install-user.sh').read_text(encoding='utf-8')
        cli = (ATLAS / 'chat_cli.py').read_text(encoding='utf-8')
        self.assertGreaterEqual(install.count('chat_cli.py'), 2)
        self.assertIn('def main()', cli)
        self.assertIn('if __name__ == "__main__"', cli)
