import unittest

from infrastructure.pentium.atlas.chat_cli import AtlasChatCli


class FakeGateway:
    def __init__(self): self.calls = []
    def handle(self, text, *, source='human.voice'):
        self.calls.append((text, source))
        return 'resposta'


class AtlasChatCliTests(unittest.TestCase):
    def test_text_uses_same_gateway_with_cli_source(self):
        gateway = FakeGateway(); cli = AtlasChatCli(gateway, status_provider=lambda: 'LISTENING')
        self.assertEqual('resposta', cli.process_line('como esta o x99?'))
        self.assertEqual([('como esta o x99?', 'human.cli')], gateway.calls)

    def test_commands_do_not_call_cognition(self):
        gateway = FakeGateway(); cli = AtlasChatCli(gateway, status_provider=lambda: 'LISTENING')
        self.assertIn('LISTENING', cli.process_line('/status'))
        self.assertIn('/help', cli.process_line('/help'))
        self.assertIsNone(cli.process_line('/exit'))
        self.assertTrue(cli.should_exit)
        self.assertEqual([], gateway.calls)
