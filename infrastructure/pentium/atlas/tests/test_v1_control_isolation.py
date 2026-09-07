import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / 'infrastructure' / 'pentium' / 'atlas'


class VoiceControlIsolationTests(unittest.TestCase):
    def test_voice_and_cli_have_no_control_dispatcher(self):
        voice = (ATLAS / 'voice_daemon.py').read_text(encoding='utf-8')
        cli = (ATLAS / 'chat_cli.py').read_text(encoding='utf-8')
        for text in (voice, cli):
            self.assertIn('control_allow=()', text)
            self.assertNotIn('ManagedControlService', text)
            self.assertNotIn('managed_control', text.lower())

    def test_voice_runtime_never_executes_intent_directly(self):
        runtime = (ATLAS / 'voice_runtime.py').read_text(encoding='utf-8')
        self.assertNotIn('ssh', runtime.lower())
        self.assertNotIn('restart_service', runtime)
        self.assertNotIn('reboot_host', runtime)
