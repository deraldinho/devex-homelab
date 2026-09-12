import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"


class DeploymentTruthPackagingTests(unittest.TestCase):
    def test_installer_requires_and_persists_exact_deploy_sha(self):
        text = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        self.assertIn('DEPLOY_SHA="${ATLAS_DEPLOY_SHA:-}"', text)
        self.assertIn('[[ "${DEPLOY_SHA}" =~ ^[0-9a-fA-F]{40}$ ]]', text)
        self.assertIn("grep -v '^ATLAS_EXPECTED_SHA='", text)
        self.assertNotIn('ATLAS_WIFI_INTERFACE=', text)
        self.assertIn(r'printf "%s\n" "${DEPLOY_SHA}" > "${RUNTIME_DIR}/deployed-sha.tmp"', text)
        self.assertIn('mv "${RUNTIME_DIR}/deployed-sha.tmp" "${RUNTIME_DIR}/deployed-sha"', text)
        self.assertIn(r'printf "ATLAS_EXPECTED_SHA=%s\n" "${DEPLOY_SHA}"', text)


if __name__ == "__main__":
    unittest.main()
