import unittest
import wave
from pathlib import Path

from infrastructure.pentium.atlas.audio.generate_tone_assets import CATEGORIES

AUDIO_ROOT = Path(__file__).resolve().parent.parent.parent / "assets" / "audio"


class AudioAssetsContractTests(unittest.TestCase):
    def test_all_categories_have_valid_wav_files(self):
        self.assertTrue(AUDIO_ROOT.is_dir(), "Diretório de áudio deve existir")
        for category in CATEGORIES:
            cat_dir = AUDIO_ROOT / category
            self.assertTrue(cat_dir.is_dir(), f"Categoria {category} deve possuir diretório")
            wav_file = cat_dir / "tone_01.wav"
            self.assertTrue(wav_file.is_file(), f"Arquivo tone_01.wav deve existir em {category}")

            with wave.open(str(wav_file), "rb") as wf:
                self.assertEqual(wf.getnchannels(), 1, "Deve ser mono")
                self.assertEqual(wf.getsampwidth(), 2, "Deve ser 16-bit PCM")
                self.assertEqual(wf.getframerate(), 44100, "Deve ser 44.1kHz")
                frames = wf.getnframes()
                duration = frames / 44100.0
                self.assertGreater(duration, 0.05, "Tom deve ter duração audível mínima")
                self.assertLess(duration, 2.0, "Tom não deve ser excessivamente longo")


if __name__ == "__main__":
    unittest.main()
