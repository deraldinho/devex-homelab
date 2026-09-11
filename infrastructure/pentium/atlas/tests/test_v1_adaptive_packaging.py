import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / 'infrastructure' / 'pentium' / 'atlas'


class AdaptiveVoicePackagingTests(unittest.TestCase):
    def test_installer_and_daemon_wire_adaptive_audio_modules(self):
        install = (ATLAS / 'install-user.sh').read_text(encoding='utf-8')
        daemon = (ATLAS / 'voice_daemon.py').read_text(encoding='utf-8')
        for name in ('adaptive_vad.py', 'transcript_filter.py'):
            self.assertGreaterEqual(install.count(name), 2)
        self.assertIn('AdaptiveEnergyVad', daemon)
        self.assertIn('NonSpeechTranscriptFilter', daemon)
        self.assertIn('vad_snr_ratio', daemon)
        self.assertIn('transcript_filter=', daemon)


if __name__ == '__main__':
    unittest.main()
