import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"
WORKFLOW = ROOT / ".github" / "workflows" / "foundation-ci.yml"


class I1PackagingTests(unittest.TestCase):
    def test_observation_config_declares_managed_x99_schedule(self):
        payload = json.loads((ATLAS / "observation_config.json").read_text(encoding="utf-8"))
        managed = payload["sources"]["managed.x99"]
        self.assertLessEqual(managed["timeout_seconds"], 8)
        self.assertGreaterEqual(managed["max_backoff_seconds"], managed["interval_seconds"])

    def test_installer_packages_i1_modules_and_marker(self):
        text = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        self.assertIn("dual_zone_runtime.py", text)
        self.assertIn("i1_certification.py", text)
        self.assertIn("ATLAS_I1_OBSERVATION_INTEGRATION_INSTALL_PASS", text)

    def test_foundation_ci_compiles_and_marks_i1(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('"$atlas/dual_zone_runtime.py"', text)
        self.assertIn('"$atlas/i1_certification.py"', text)
        self.assertIn("DEVEX_HOMELAB_ATLAS_I1_OBSERVATION_INTEGRATION_PASS", text)

    def test_architecture_and_prd_document_i1_boundary(self):
        architecture = (ROOT / "docs" / "architecture" / "atlas-local-intelligence-design.md").read_text(encoding="utf-8")
        prd = (ROOT / "docs" / "prd" / "PRD-0006-atlas-local-intelligence.md").read_text(encoding="utf-8")
        for text in (architecture, prd):
            self.assertIn("Observation Integration I1", text)
            self.assertIn("WIFI_OBSERVED", text)
            self.assertIn("MANAGED", text)
            self.assertIn("um unico ObservationRuntime", text)


if __name__ == "__main__":
    unittest.main()
