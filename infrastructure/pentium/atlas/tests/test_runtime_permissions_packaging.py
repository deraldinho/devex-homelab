import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"
DASHBOARD = ROOT / "infrastructure" / "pentium" / "dashboard"


class RuntimePermissionsPackagingTests(unittest.TestCase):
    def assert_installer_hardens_runtime(self, path: Path, runtime_line: str):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        self.assertIn(runtime_line, lines)
        self.assertIn('  find "${RUNTIME_DIR}" -type f -exec chmod 0600 {} +', lines)
        self.assertNotIn('chown ', text)
        self.assertNotIn('`n', text)

    def test_atlas_installer_hardens_existing_runtime_regular_files(self):
        self.assert_installer_hardens_runtime(
            ATLAS / "install-user.sh", 'RUNTIME_DIR="${TARGET_DIR}/runtime"'
        )

    def test_dashboard_installer_hardens_existing_runtime_regular_files(self):
        self.assert_installer_hardens_runtime(
            DASHBOARD / "install-user.sh", 'RUNTIME_DIR="$HOME/pentium-agent/atlas/runtime"'
        )


if __name__ == "__main__":
    unittest.main()
