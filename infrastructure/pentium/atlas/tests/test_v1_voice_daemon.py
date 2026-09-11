import json, tempfile, unittest
from pathlib import Path

from infrastructure.pentium.atlas.voice_daemon import load_voice_config


class VoiceDaemonTests(unittest.TestCase):
    def test_config_requires_bounded_runtime_fields(self):
        payload = {
            "schema_version": 1, "wake_phrase": "Atlas", "capture_duration_s": 4,
            "capture_device": "plughw:0,0", "vad_rms_threshold": 220,
            "vad_snr_ratio": 1.15, "vad_margin": 150, "vad_calibration_frames": 1,
            "vad_alpha": 0.2, "vad_frame_ms": 20, "vad_min_speech_frames": 5,
            "utterance_start_speech_frames": 3, "utterance_trailing_silence_ms": 800,
            "utterance_max_s": 12, "utterance_pre_roll_ms": 200, "utterance_listen_window_s": 4,
            "stream_vad_calibration_frames": 50, "stream_vad_history_frames": 200,
            "whisper_model": "~/w.bin", "whisper_timeout_s": 75,
            "llm_model": "~/q.gguf", "llm_timeout_s": 75, "llm_context_tokens": 2048,
            "tts_voice": "pt-br", "tts_device": "plughw:0,0",
            "health_path": "~/latest.json", "idle_sleep_s": 0.2, "error_sleep_s": 5,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "voice.json"; path.write_text(json.dumps(payload), encoding="utf-8")
            cfg = load_voice_config(path)
        self.assertEqual("Atlas", cfg["wake_phrase"])
        self.assertLessEqual(cfg["capture_duration_s"], 10)
        self.assertLessEqual(cfg["llm_context_tokens"], 4096)

    def test_invalid_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "voice.json"; path.write_text('{"schema_version":2}', encoding="utf-8")
            with self.assertRaises(ValueError): load_voice_config(path)

if __name__ == "__main__": unittest.main()
