import unittest

from infrastructure.pentium.atlas.alsa_capture import AlsaCaptureBackend


class FakeRunner:
    def __init__(self, data=b"RIFF"):
        self.data = data
        self.calls = []

    def run(self, argv, *, timeout_s, max_output_bytes):
        self.calls.append((argv, timeout_s, max_output_bytes))
        return self.data


class AlsaCaptureBackendTests(unittest.TestCase):
    def test_captures_mono_16khz_wav_with_bounded_duration(self):
        runner = FakeRunner(b"RIFF....WAVE")
        capture = AlsaCaptureBackend("/bin/arecord", runner=runner, device="plughw:0,0", duration_s=4, max_audio_bytes=200000)
        data = capture.capture_utterance()
        self.assertEqual(b"RIFF....WAVE", data)
        argv = runner.calls[0][0]
        self.assertIn("16000", argv)
        self.assertIn("1", argv)
        self.assertIn("4", argv)

    def test_rejects_invalid_duration(self):
        with self.assertRaises(ValueError):
            AlsaCaptureBackend("arecord", duration_s=0)
