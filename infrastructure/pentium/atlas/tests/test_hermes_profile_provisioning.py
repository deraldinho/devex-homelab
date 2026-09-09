import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HermesProfileProvisioningTests(unittest.TestCase):
    def test_provisioner_creates_locked_down_atlas_profile(self):
        text = (ROOT / "prepare-hermes-atlas.sh").read_text(encoding="utf-8")
        self.assertIn("profile create atlas --no-alias --no-skills", text)
        self.assertIn("skills opt-out --remove --yes", text)
        self.assertIn("tools disable", text)
        self.assertIn("hermes_preflight", text)
        self.assertNotIn("auth add", text)
        self.assertNotIn("oauth", text.lower())

    def test_installer_requires_hermes_but_never_starts_voice(self):
        text = (ROOT / "install-user.sh").read_text(encoding="utf-8")
        self.assertIn("command -v hermes", text)
        self.assertIn("prepare-hermes-atlas.sh", text)
        self.assertIn("hermes_preflight.py", text)
        self.assertNotIn("restart atlas-voice.service", text)


if __name__ == "__main__":
    unittest.main()

# Foundation CI must compile the preflight and syntax-check the provisioner.
class HermesFoundationPackagingTests(unittest.TestCase):
    def test_foundation_ci_validates_preflight_and_provisioner(self):
        workflow = (ROOT.parents[2] / ".github/workflows/foundation-ci.yml").read_text(encoding="utf-8")
        self.assertIn("hermes_preflight.py", workflow)
        self.assertIn("prepare-hermes-atlas.sh", workflow)
        self.assertIn("bash -n", workflow)
