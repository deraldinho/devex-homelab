import json, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / 'infrastructure' / 'pentium' / 'atlas'

class UtteranceWiringTests(unittest.TestCase):
    def test_daemon_config_and_installer_use_streaming_segmentation(self):
        daemon = (ATLAS / 'voice_daemon.py').read_text(encoding='utf-8')
        install = (ATLAS / 'install-user.sh').read_text(encoding='utf-8')
        cfg = json.loads((ATLAS / 'config_voice.json').read_text(encoding='utf-8'))
        self.assertIn('StreamingUtteranceCapture', daemon)
        self.assertIn('open_arecord_pcm', daemon)
        self.assertIn('StreamingAdaptiveVad', daemon)
        self.assertEqual(200, cfg['utterance_pre_roll_ms'])
        self.assertEqual(800, cfg['utterance_trailing_silence_ms'])
        self.assertEqual(12, cfg['utterance_max_s'])
        for name in ('utterance_capture.py', 'alsa_stream.py', 'streaming_vad.py'):
            self.assertGreaterEqual(install.count(name), 2)
