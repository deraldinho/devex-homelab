import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from infrastructure.pentium.atlas.whisper_stt import SubprocessWhisperRunner


class WhisperTempDirTests(unittest.TestCase):
    def test_runner_uses_private_runtime_directory_and_cleans_wav(self):
        with tempfile.TemporaryDirectory() as td:
            audio_dir = Path(td) / 'audio'
            seen = []
            def executor(argv, **kwargs):
                wav = Path(argv[-1]); seen.append(wav)
                self.assertEqual(audio_dir, wav.parent)
                self.assertTrue(wav.exists())
                return SimpleNamespace(stdout=b'Atlas', stderr=b'', returncode=0)
            runner = SubprocessWhisperRunner(temp_dir=audio_dir, executor=executor)
            text = runner.run(['whisper'], input_bytes=b'RIFF....WAVE', timeout_s=2, max_output_bytes=64)
            self.assertEqual('Atlas', text)
            self.assertTrue(audio_dir.is_dir())
            self.assertFalse(seen[0].exists())


if __name__ == '__main__':
    unittest.main()
