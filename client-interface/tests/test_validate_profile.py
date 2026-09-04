from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools" / "client-interface" / "scripts" / "validate_profile.py"
PROFILE = ROOT / "tools" / "client-interface" / "profiles" / "interlude-746-l2jtoren.json"

spec = importlib.util.spec_from_file_location("validate_profile", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProfileValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = json.loads(PROFILE.read_text(encoding="utf-8"))

    def test_repository_profile_is_valid(self) -> None:
        module.validate_profile(deepcopy(self.profile))

    def test_rejects_non_interlude_schema(self) -> None:
        profile = deepcopy(self.profile)
        profile["clientRevision"]["xdatSchema"] = "ct17"
        with self.assertRaises(module.ValidationError):
            module.validate_profile(profile)

    def test_rejects_binary_commit_policy(self) -> None:
        profile = deepcopy(self.profile)
        profile["policy"]["commitClientBinaries"] = True
        with self.assertRaises(module.ValidationError):
            module.validate_profile(profile)

    def test_rejects_invalid_baseline_hash(self) -> None:
        profile = deepcopy(self.profile)
        profile["baseline"]["engineDll"]["sha256"] = "not-a-hash"
        with self.assertRaises(module.ValidationError):
            module.validate_profile(profile)

    def test_accepts_minimal_manifest(self) -> None:
        manifest = {
            "schemaVersion": 1,
            "profileId": self.profile["profileId"],
            "generatedAtUtc": "2026-08-04T00:00:00Z",
            "files": [
                {
                    "fileName": "Interface.xdat",
                    "relativePath": "Interface.xdat",
                    "sizeBytes": 1,
                    "sha256": "a" * 64,
                    "pe": None,
                }
            ],
        }
        module.validate_manifest(manifest, self.profile)

    def test_scan_detects_proprietary_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("ok", encoding="utf-8")
            (root / "Interface.xdat").write_bytes(b"x")
            violations = module.scan_repository(root)
            self.assertEqual([root / "Interface.xdat"], violations)


if __name__ == "__main__":
    unittest.main()
