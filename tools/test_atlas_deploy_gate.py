"""Isolated CP-DEPLOY-01 security and drift classification tests."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from tools.atlas_deploy_gate import compare, main, ReleaseGateDenied

ESSENTIAL = ("cognitive_daemon.py", "hermes_adapter.py",
             "reaction_loop_cognitivo.py")


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.source = Path(self.tmp.name) / "atlas"
        self.source.mkdir()
        for name in ESSENTIAL:
            (self.source / name).write_text("original", encoding="utf-8")
        self.host = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in self.source.glob("*.py")}

    def tearDown(self):
        self.tmp.cleanup()

    def test_identical_source_is_not_deploy_authorization(self):
        result = compare(self.source, self.host)
        self.assertEqual(result["status"], "MATCHED_NO_DEPLOY")
        self.assertIs(result["deploy_allowed"], False)

    def test_changed_production_entrypoint_denies_release(self):
        (self.source / "hermes_adapter.py").write_text("changed", encoding="utf-8")
        result = compare(self.source, self.host)
        self.assertIn("hermes_adapter.py", result["modified_existing"])
        self.assertEqual(result["status"], "HOLD_DRIFT_REQUIRES_PLAN")

    def test_new_and_host_only_modules_are_preserved(self):
        (self.source / "agency_worker_cli.py").write_text("new", encoding="utf-8")
        self.host["legacy_backend.py"] = "a" * 64
        result = compare(self.source, self.host)
        self.assertIn("agency_worker_cli.py", result["not_installed"])
        self.assertIn("legacy_backend.py", result["host_only_preserve"])
        self.assertIs(result["deploy_allowed"], False)

    def test_invalid_manifest_path_and_hash_denied(self):
        for invalid in ({"../evil.py": "a" * 64}, {"other.py": "notahash"}):
            with self.subTest(invalid=invalid), self.assertRaises(ReleaseGateDenied):
                compare(self.source, invalid)

    def test_missing_essential_entrypoint_denied(self):
        self.host.pop("cognitive_daemon.py")
        with self.assertRaises(ReleaseGateDenied):
            compare(self.source, self.host)

    def test_symlinked_module_denied(self):
        target = Path(self.tmp.name) / "external.py"
        target.write_text("print('secret')", encoding="utf-8")
        try:
            (self.source / "sneaky.py").symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        with self.assertRaises(ReleaseGateDenied):
            compare(self.source, self.host)

    def test_cli_returns_hold_on_drift_without_writes(self):
        (self.source / "hermes_adapter.py").write_text("changed", encoding="utf-8")
        f = Path(self.tmp.name) / "host.json"
        f.write_text(json.dumps(self.host), encoding="utf-8")
        self.assertEqual(main(["--source", str(self.source), "--host-manifest", str(f)]), 2)
        self.assertTrue(f.is_file())
        self.assertEqual(len(list(Path(self.tmp.name).rglob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
