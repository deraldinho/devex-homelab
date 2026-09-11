import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HermesDeploymentBoundaryTests(unittest.TestCase):
    def test_provisioner_runs_from_installed_atlas_package_root(self):
        text = (ROOT / "prepare-hermes-atlas.sh").read_text(encoding="utf-8")
        self.assertIn('PYTHONPATH="$(dirname "${SCRIPT_DIR}")', text)
        self.assertIn("python3 -m atlas.hermes_preflight", text)
        self.assertNotIn('dirname "$(dirname "$(dirname', text)

    def test_cognitive_service_allows_remote_provider_and_finds_user_hermes(self):
        text = (ROOT / "atlas-cognitive.service").read_text(encoding="utf-8")
        self.assertIn("Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin", text)
        self.assertIn("RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6", text)


if __name__ == "__main__":
    unittest.main()
