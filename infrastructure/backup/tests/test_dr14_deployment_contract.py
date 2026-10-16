"""CP-DR14 deployment contracts: all static until approved physical DR."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DR14DeploymentContractTests(unittest.TestCase):
    def test_systemd_requires_existing_environment_file(self):
        service = (ROOT / "systemd" / "homelab-backup.service").read_text(encoding="utf-8")
        self.assertIn("EnvironmentFile=/etc/homelab/backup.env", service)
        self.assertNotIn("EnvironmentFile=-", service)

    def test_systemd_timer_is_opt_in_not_automatically_installed(self):
        timer = (ROOT / "systemd" / "homelab-backup.timer").read_text(encoding="utf-8")
        self.assertIn("Persistent=true", timer)
        self.assertIn("Unit=homelab-backup.service", timer)
        self.assertIn("WantedBy=timers.target", timer)

    def test_env_example_is_safe_and_does_not_supply_secret(self):
        example = (ROOT / "backup.env.example").read_text(encoding="utf-8")
        expected = ("RESTIC_REPOSITORY=", "RESTIC_PASSWORD_FILE=",
                    "HOMELAB_NODE=", "BACKUP_SOURCE_DIR=",
                    "HOMELAB_STATE_DIR=", "BACKUP_STAGING_PARENT=")
        for name in expected:
            self.assertIn(name, example)
        self.assertNotIn("RESTIC_PASSWORD=", example)
        self.assertIn("DO NOT DEPLOY AS-IS", example)

    def test_readiness_does_not_start_services_or_operate_restic(self):
        script = (ROOT / "dr14_preflight.py").read_text(encoding="utf-8")
        self.assertIn('"restoration_certification": "NOT_TESTED"', script)
        self.assertIn('"offsite_certification": "NOT_TESTED"', script)
        for forbidden in ('"start"', '"enable"', '"restart"', '"init"', '"unlock"', '"restore"'):
            self.assertNotIn(forbidden, script)


if __name__ == "__main__":
    unittest.main()
