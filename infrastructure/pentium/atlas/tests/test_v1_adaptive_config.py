import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / 'infrastructure' / 'pentium' / 'atlas' / 'config_voice.json'


class AdaptiveVoiceConfigTests(unittest.TestCase):
    def test_physical_config_keeps_audio_bounds_without_private_llm_config(self):
        cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
        self.assertTrue(cfg['whisper_model'].endswith('ggml-base-q5_1.bin'))
        self.assertGreaterEqual(float(cfg['whisper_timeout_s']), 60.0)
        for key in ('llm_model', 'llm_timeout_s', 'llm_context_tokens'):
            self.assertNotIn(key, cfg)
        self.assertGreater(float(cfg['vad_snr_ratio']), 1.0)
        self.assertLessEqual(float(cfg['vad_snr_ratio']), 1.25)
        self.assertGreaterEqual(int(cfg['vad_margin']), 0)
        self.assertGreaterEqual(int(cfg['vad_calibration_frames']), 1)
        self.assertGreater(float(cfg['vad_alpha']), 0.0)
        self.assertEqual(20, int(cfg['vad_frame_ms']))
        self.assertGreaterEqual(int(cfg['vad_min_speech_frames']), 5)


if __name__ == '__main__':
    unittest.main()
