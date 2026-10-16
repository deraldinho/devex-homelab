"""Contract tests for CP-DR14; synthetic host metadata only."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dr14_preflight import inspect_host, main


class PreflightTests(unittest.TestCase):
    def test_invalid_node_rejected(self):
        with self.assertRaises(ValueError):
            inspect_host("../../bad")

    def test_invalid_timer_rejected(self):
        with self.assertRaises(ValueError):
            inspect_host("core", backup_timer="systemctl; touch /tmp/unsafe")

    @patch("dr14_preflight._reference", return_value={"exists": True, "regular": True, "owner_only": True})
    @patch("dr14_preflight._run", return_value="ok")
    @patch("dr14_preflight.shutil.which", return_value="/usr/bin/mock")
    def test_all_metadata_present_never_certifies_restore(self, *_):
        with tempfile.TemporaryDirectory() as d:
            env, key = Path(d) / "env", Path(d) / "key"
            env.write_text("DO_NOT_READ_SECRET")
            key.write_text("SECRET_SHOULD_NOT_BE_OUTPUT")
            env.chmod(0o600)
            key.chmod(0o600)
            o = inspect_host("pentium", backup_env=env, credential_ref=key)
            self.assertEqual(o["status"], "PREFLIGHT_PRESENT_NOT_CERTIFIED")
            self.assertEqual(o["restoration_certification"], "NOT_TESTED")
            self.assertEqual(o["offsite_certification"], "NOT_TESTED")
            self.assertEqual(o["blockers"], [])
            self.assertNotIn("SECRET_SHOULD_NOT_BE_OUTPUT", str(o))
            self.assertNotIn("DO_NOT_READ_SECRET", str(o))

    @patch("dr14_preflight._run", return_value="not_ready")
    @patch("dr14_preflight.shutil.which", return_value=None)
    def test_missing_prerequisites_report_actionable_blockers(self, *_):
        obj = inspect_host("core", backup_env=Path("/does/not/exist"),
                           credential_ref=Path("/does/not/exist2"))
        self.assertEqual(obj["status"], "BLOCKED")
        self.assertIn("restic_binary_absent", obj["blockers"])
        self.assertIn("backup_timer_not_active", obj["blockers"])

    @patch("dr14_preflight._reference", side_effect=lambda p: {"exists": True, "regular": True, "owner_only": p.name != "key"})
    @patch("dr14_preflight._run", return_value="ok")
    @patch("dr14_preflight.shutil.which", return_value="/usr/bin/mock")
    def test_group_readable_credential_denied(self, *_):
        with tempfile.TemporaryDirectory() as d:
            env, key = Path(d) / "env", Path(d) / "key"
            env.write_text("dummy")
            key.write_text("dummy")
            env.chmod(0o600)
            key.chmod(0o640)
            obj = inspect_host("core", backup_env=env, credential_ref=key)
            self.assertEqual(obj["status"], "BLOCKED")
            self.assertIn("credential_reference_missing_or_permissions", obj["blockers"])

    @patch("dr14_preflight._run", return_value="ok")
    @patch("dr14_preflight.shutil.which", return_value="/usr/bin/mock")
    def test_symlink_config_denied(self, *_):
        with tempfile.TemporaryDirectory() as d:
            env = Path(d) / "env"
            target = Path(d) / "target"
            key = Path(d) / "key"
            target.write_text("dummy")
            target.chmod(0o600)
            key.write_text("dummy")
            key.chmod(0o600)
            try:
                env.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink privilege unavailable")
            obj = inspect_host("core", backup_env=env, credential_ref=key)
            self.assertEqual(obj["status"], "BLOCKED")

    @patch("dr14_preflight._reference", return_value={"exists": True, "regular": True, "owner_only": True})
    @patch("dr14_preflight._run", return_value="ok")
    @patch("dr14_preflight.shutil.which", return_value="/usr/bin/mock")
    def test_no_default_file_write(self, *_):
        with tempfile.TemporaryDirectory() as d:
            env, key = Path(d) / "env", Path(d) / "key"
            env.write_text("stub")
            key.write_text("stub")
            env.chmod(0o600)
            key.chmod(0o600)
            with patch("dr14_preflight.DEFAULT_ENV", env), patch(
                    "dr14_preflight.DEFAULT_KEY", key):
                self.assertEqual(main(["--node", "core"]), 0)

    @patch("dr14_preflight.inspect_host", return_value={"status": "BLOCKED"})
    def test_blocked_process_return_code(self, *_):
        self.assertEqual(main(["--node", "core"]), 2)

    @patch("dr14_preflight.inspect_host", return_value={"status": "BLOCKED"})
    def test_explicit_output_will_not_overwrite(self, *_):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "report.json"
            p.write_text("KEEP")
            self.assertEqual(main(["--node", "core", "--output", str(p)]), 2)
            self.assertEqual(p.read_text(), "KEEP")


if __name__ == "__main__":
    unittest.main()
