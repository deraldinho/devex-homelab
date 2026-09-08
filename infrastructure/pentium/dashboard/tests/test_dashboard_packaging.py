import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DashboardPackagingTests(unittest.TestCase):
    def test_systemd_unit_binds_dashboard_service_only(self):
        unit = (ROOT / "systemd" / "atlas-dashboard.service").read_text(encoding="utf-8")
        self.assertIn("atlas_dashboard.py", unit)
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertNotIn("atlas-voice.service", unit)

    def test_installer_never_enables_voice(self):
        script = (ROOT / "install-user.sh").read_text(encoding="utf-8")
        self.assertIn("atlas-dashboard.service", script)
        self.assertNotIn("enable --now atlas-voice.service", script)
        self.assertNotIn("start atlas-voice.service", script)

    def test_systemd_allows_only_required_socket_families(self):
        unit = (ROOT / "systemd" / "atlas-dashboard.service").read_text(encoding="utf-8")
        self.assertIn("RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK", unit)

    def test_installer_restarts_dashboard_after_install(self):
        script = (ROOT / "install-user.sh").read_text(encoding="utf-8")
        self.assertIn("systemctl --user restart atlas-dashboard.service", script)

    def test_installer_packages_avatar_renderer_asset(self):
        script = (ROOT / "install-user.sh").read_text(encoding="utf-8")
        self.assertIn("atlas-avatar-renderer.js", script)


if __name__ == "__main__":
    unittest.main()
