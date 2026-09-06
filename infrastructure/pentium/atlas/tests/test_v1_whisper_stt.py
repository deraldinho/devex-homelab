import unittest

from infrastructure.pentium.atlas.whisper_stt import WhisperSttBackend


class FakeRunner:
    def __init__(self, stdout=""):
        self.stdout = stdout
        self.calls = []

    def run(self, argv, *, input_bytes, timeout_s, max_output_bytes):
        self.calls.append((argv, input_bytes, timeout_s, max_output_bytes))
        return self.stdout


class WhisperSttBackendTests(unittest.TestCase):
    def test_transcribes_bounded_wav_with_pt_language(self):
        runner = FakeRunner(stdout="Atlas, está me ouvindo?\n")
        backend = WhisperSttBackend("/bin/whisper-cli", "/models/tiny.bin", runner=runner, max_audio_bytes=4096)
        text = backend.transcribe(b"RIFF....WAVE")
        self.assertEqual("Atlas, está me ouvindo?", text)
        argv = runner.calls[0][0]
        self.assertIn("-l", argv)
        self.assertIn("pt", argv)
        self.assertIn("--no-timestamps", argv)

    def test_rejects_oversized_audio_before_runner(self):
        runner = FakeRunner()
        backend = WhisperSttBackend("w", "m", runner=runner, max_audio_bytes=4)
        with self.assertRaises(ValueError):
            backend.transcribe(b"12345")
        self.assertEqual([], runner.calls)
