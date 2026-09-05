import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"
WORKFLOW = ROOT / ".github" / "workflows" / "foundation-ci.yml"


class PresencePackagingD2Tests(unittest.TestCase):
    def test_installer_packages_identity_presence_modules(self):
        text = (ATLAS / "install-user.sh").read_text(encoding="utf-8")

        self.assertIn("presence_registry.py", text)
        self.assertIn("presence_persistence.py", text)

    def test_foundation_ci_has_d2_identity_presence_gate(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("presence_registry.py", text)
        self.assertIn("presence_persistence.py", text)
        self.assertIn("infrastructure.pentium.atlas.tests.test_presence_registry", text)
        self.assertIn("infrastructure.pentium.atlas.tests.test_presence_persistence", text)
        self.assertIn("infrastructure.pentium.atlas.tests.test_presence_source_d2", text)
        self.assertIn("DEVEX_HOMELAB_ATLAS_D2_IDENTITY_PRESENCE_PASS", text)


if __name__ == "__main__":
    unittest.main()
