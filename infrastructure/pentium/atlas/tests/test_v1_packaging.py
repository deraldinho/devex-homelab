import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"


class V1PackagingTests(unittest.TestCase):
    def test_installer_copies_compiles_and_marks_v1_modules(self):
        text = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        copy_section = text.split("for config in", 1)[0]
        compile_section = text.split("python3 -m py_compile", 1)[1]
        for name in ("voice_gate.py", "live_tts.py", "alsa_capture.py", "whisper_stt.py", "voice_runtime.py"):
            self.assertIn(name, copy_section)
            self.assertIn(name, compile_section)
        self.assertIn("ATLAS_V1_ALWAYS_ON_VOICE_INSTALL_PASS", text)


if __name__ == "__main__":
    unittest.main()
