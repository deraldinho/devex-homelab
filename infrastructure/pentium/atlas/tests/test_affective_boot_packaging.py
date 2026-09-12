import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"
WORKFLOW = ROOT / ".github" / "workflows" / "foundation-ci.yml"


class AffectiveBootPackagingTests(unittest.TestCase):
    def test_observation_service_has_bounded_memory(self):
        service = (ATLAS / "atlas-observation.service").read_text(encoding="utf-8")
        self.assertIn("MemoryHigh=128M", service)
        self.assertIn("MemoryMax=192M", service)

    def test_observation_user_service_is_independent_and_restartable(self):
        service = (ATLAS / "atlas-observation.service").read_text(encoding="utf-8")
        self.assertIn("ExecStart=/usr/bin/python3 -m atlas.observation_daemon", service)
        self.assertIn("Restart=on-failure", service)
        self.assertIn("EnvironmentFile=-%h/pentium-agent/atlas/runtime/observation.env", service)
        self.assertNotIn("x99", service.lower())
        self.assertNotIn("atlas-voice.service", service)

    def test_installer_packages_runtime_and_preserves_voice_enable_state(self):
        text = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for name in (
            "affective_composition.py", "affective_interaction_ipc.py",
            "observation_daemon.py", "affective_boot_certification.py", "atlas-observation.service",
            "ATLAS_AFFECTIVE_BOOT_INSTALL_PASS",
        ):
            self.assertIn(name, text)
        self.assertIn("enable atlas-observation.service", text)
        self.assertNotIn("enable atlas-voice.service", text)

    def test_foundation_ci_compiles_and_exposes_boot_gate(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for name in ("affective_composition.py", "affective_interaction_ipc.py", "observation_daemon.py", "affective_boot_certification.py"):
            self.assertIn(name, text)
        self.assertIn("DEVEX_HOMELAB_ATLAS_AFFECTIVE_BOOT_PASS", text)
        self.assertIn("atlas-observation.service", text)


if __name__ == "__main__":
    unittest.main()
