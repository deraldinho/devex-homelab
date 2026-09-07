import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"


class V1PackagingTests(unittest.TestCase):
    def test_installer_copies_compiles_and_marks_v1_modules(self):
        text = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        copy_section = text.split("for config in", 1)[0]
        compile_section = text.split("python3 -m py_compile", 1)[1]
        modules = (
            "voice_gate.py", "live_tts.py", "alsa_capture.py", "whisper_stt.py",
            "voice_runtime.py", "energy_vad.py", "human_interaction.py",
            "human_context.py", "voice_daemon.py",
        )
        for name in modules:
            self.assertIn(name, copy_section)
            self.assertIn(name, compile_section)
        self.assertIn("config_voice.json", text)
        self.assertIn("atlas-voice.service", text)
        self.assertIn("systemctl --user enable atlas-voice.service", text)
        self.assertIn("ATLAS_V1_ALWAYS_ON_VOICE_INSTALL_PASS", text)

if __name__ == "__main__": unittest.main()

class V1WorkflowPackagingTests(unittest.TestCase):
    def test_foundation_ci_emits_v1_voice_marker(self):
        workflow = (ROOT / ".github" / "workflows" / "foundation-ci.yml").read_text(encoding="utf-8")
        self.assertIn("DEVEX_HOMELAB_ATLAS_V1_ALWAYS_ON_VOICE_PASS", workflow)
