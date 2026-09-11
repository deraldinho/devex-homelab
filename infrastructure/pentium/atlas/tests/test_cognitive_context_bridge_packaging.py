import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"
WORKFLOW = ROOT / ".github" / "workflows" / "foundation-ci.yml"


class CognitiveContextBridgePackagingTest(unittest.TestCase):
    def test_installer_packages_bridge_and_does_not_enable_voice(self):
        text = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for token in (
            "cognitive_observation_projection.py",
            "cognitive_context_bridge_certification.py",
            "ATLAS_COGNITIVE_CONTEXT_BRIDGE_INSTALL_PASS",
        ):
            self.assertIn(token, text)
        self.assertIn("enable atlas-observation.service", text)
        self.assertNotIn("enable atlas-voice.service", text)

    def test_foundation_ci_compiles_bridge_and_exposes_gate(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cognitive_observation_projection.py", text)
        self.assertIn("cognitive_context_bridge_certification.py", text)
        self.assertIn("DEVEX_HOMELAB_ATLAS_COGNITIVE_CONTEXT_BRIDGE_PASS", text)


if __name__ == "__main__":
    unittest.main()
