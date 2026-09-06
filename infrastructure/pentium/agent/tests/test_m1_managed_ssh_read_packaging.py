from pathlib import Path
import json
import unittest


class ManagedSshReadM1PackagingTests(unittest.TestCase):
    def test_installer_packages_m1_modules(self):
        text = Path("infrastructure/pentium/agent/install-user.sh").read_text(encoding="utf-8")
        self.assertIn("managed_inventory.py", text)
        self.assertIn("managed_read.py", text)
        self.assertIn("PENTIUM_AGENT_MANAGED_SSH_READ_M1_INSTALL_PASS", text)

    def test_foundation_ci_compiles_tests_and_marks_m1(self):
        text = Path(".github/workflows/foundation-ci.yml").read_text(encoding="utf-8")
        self.assertIn('"$agent/managed_inventory.py"', text)
        self.assertIn('"$agent/managed_read.py"', text)
        self.assertIn("DEVEX_HOMELAB_ATLAS_MANAGED_SSH_READ_M1_PASS", text)

    def test_production_x99_uses_certified_control_plane_identity(self):
        payload = json.loads(Path("infrastructure/pentium/agent/config.json").read_text(encoding="utf-8"))
        host = next(item for item in payload["managed_hosts"] if item["host_id"] == "x99")
        self.assertEqual(host["identity_file"], "~/.ssh/id_ed25519_x99_control")
        self.assertEqual(host["known_hosts_file"], "~/.ssh/known_hosts_x99")

    def test_architecture_and_prd_document_m1_boundary(self):
        architecture = Path("docs/architecture/atlas-local-intelligence-design.md").read_text(encoding="utf-8")
        prd = Path("docs/prd/PRD-0006-atlas-local-intelligence.md").read_text(encoding="utf-8")
        self.assertIn("Managed SSH READ M1", architecture)
        self.assertIn("sem shell arbitrario", architecture)
        self.assertIn("Managed SSH READ M1", prd)
        self.assertIn("M2 CONTROL", prd)


if __name__ == "__main__":
    unittest.main()
