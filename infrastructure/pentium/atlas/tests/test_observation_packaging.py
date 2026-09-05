import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"
WORKFLOW = ROOT / ".github" / "workflows" / "foundation-ci.yml"


class ObservationPackagingTests(unittest.TestCase):
    def test_installer_packages_observation_runtime_without_persistence(self):
        text = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for required in (
            "stimulus_model.py",
            "stimulus_bus.py",
            "stimulus_journal.py",
            "stimulus_sources.py",
            "network_discovery.py",
            "observation_runtime.py",
            "observation_config.json",
        ):
            self.assertIn(required, text)
        lowered = text.lower()
        self.assertNotIn("systemctl enable", lowered)
        self.assertNotIn("systemctl start", lowered)
        self.assertNotIn("tailscale up", lowered)
        self.assertNotIn("nmcli", lowered)

    def test_foundation_ci_has_observation_gate(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("observation_runtime.py", text)
        self.assertIn("network_discovery.py", text)
        self.assertIn("observation_config.json", text)
        self.assertIn("DEVEX_HOMELAB_ATLAS_OBSERVATION_PASS", text)
        self.assertIn("DEVEX_HOMELAB_ATLAS_D1_DISCOVERY_PASS", text)
        self.assertIn("infrastructure.pentium.atlas.tests.test_network_discovery", text)
        self.assertIn("python3 -m unittest discover", text)


if __name__ == "__main__":
    unittest.main()
