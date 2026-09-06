import unittest

from infrastructure.pentium.atlas.live_tts import LiveTtsBackend


class Proc:
    def __init__(self, returncode=0, stdout=b"RIFFaudio", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if "--stdout" in argv:
            return Proc(stdout=b"RIFFaudio")
        return Proc(stdout=b"")


class LiveTtsBackendTests(unittest.TestCase):
    def test_synthesizes_text_live_then_plays_wav(self):
        runner = FakeRunner()
        tts = LiveTtsBackend("/opt/espeak-ng", "/opt/aplay", voice="pt-br", device="plughw:0,0", max_text_chars=128, max_audio_bytes=1024, runner=runner)
        tts.speak("Ola, aqui e o Atlas.")
        self.assertEqual(2, len(runner.calls))
        self.assertIn("--stdout", runner.calls[0][0])
        self.assertEqual(b"RIFFaudio", runner.calls[1][1]["input"])

    def test_rejects_oversized_text_before_subprocess(self):
        runner = FakeRunner()
        tts = LiveTtsBackend("e", "a", voice="pt-br", device="plughw:0,0", max_text_chars=8, max_audio_bytes=1024, runner=runner)
        with self.assertRaises(ValueError):
            tts.speak("texto grande demais")
        self.assertEqual([], runner.calls)


if __name__ == "__main__":
    unittest.main()
