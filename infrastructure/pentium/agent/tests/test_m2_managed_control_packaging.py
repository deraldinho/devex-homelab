import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[4]
AGENT = ROOT / "infrastructure" / "pentium" / "agent"


class ManagedControlM2PackagingTests(unittest.TestCase):
    def test_repository_config_is_default_deny_for_control(self):
        config = json.loads((AGENT / "config.json").read_text(encoding="utf-8"))
        host = config["managed_hosts"][0]
        self.assertEqual(host["allowed_controls"], [])
        self.assertEqual(host["allowed_services"], [])
        self.assertIn("control_audit_file", config)

    def test_installer_packages_m2_modules_and_marker(self):
        text = (AGENT / "install-user.sh").read_text(encoding="utf-8")
        self.assertIn("control_audit.py", text)
        self.assertIn("managed_control.py", text)
        self.assertIn("PENTIUM_AGENT_MANAGED_CONTROL_M2_INSTALL_PASS", text)

    def test_foundation_ci_compiles_and_marks_m2(self):
        text = (ROOT / ".github" / "workflows" / "foundation-ci.yml").read_text(encoding="utf-8")
        self.assertIn('"$agent/control_audit.py"', text)
        self.assertIn('"$agent/managed_control.py"', text)
        self.assertIn("DEVEX_HOMELAB_ATLAS_MANAGED_CONTROL_M2_PASS", text)

    def test_architecture_and_prd_document_m2_boundary(self):
        architecture = (ROOT / "docs" / "architecture" / "atlas-local-intelligence-design.md").read_text(encoding="utf-8")
        prd = (ROOT / "docs" / "prd" / "PRD-0006-atlas-local-intelligence.md").read_text(encoding="utf-8")
        self.assertIn("Managed CONTROL M2", architecture)
        self.assertIn("default-deny", architecture)
        self.assertIn("Managed CONTROL M2", prd)
        self.assertIn("REBOOT_HOST", prd)


if __name__ == "__main__":
    unittest.main()
