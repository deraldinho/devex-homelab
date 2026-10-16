"""Atlas feature inventory tests: no application imports or production access."""
from pathlib import Path
import json
import tempfile
import unittest

from tools.atlas_feature_inventory import inventory


class FeatureInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "entry.py").write_text("from .worker import do_work\n", encoding="utf-8")
        (self.root / "worker.py").write_text("def do_work(): pass\n", encoding="utf-8")
        (self.root / "legacy.py").write_text("raise RuntimeError('must never import')\n", encoding="utf-8")
        (self.root / "atlas-cognitive.service").write_text(
            "ExecStart=/usr/bin/python3 -m atlas.entry\n", encoding="utf-8")
        (self.root / "config_agency_specialists.json").write_text(
            json.dumps({"enabled": False, "flags": {"beta": True}}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_entrypoint_import_and_unused_distinguished(self):
        data = inventory(self.root)
        modules = {x["module"]: x for x in data["modules"]}
        self.assertEqual(modules["entry.py"]["classification"], "ENTRYPOINT_REFERENCED")
        self.assertEqual(modules["worker.py"]["classification"], "REFERENCED")
        self.assertEqual(modules["worker.py"]["direct_importers"], ["entry.py"])
        self.assertEqual(modules["legacy.py"]["classification"], "REVIEW_DYNAMIC_OR_LEGACY")
        self.assertEqual(data["syntax_errors"], [])

    def test_no_source_import_side_effects(self):
        # 'legacy.py' raises if imported; AST parsing does not execute it.
        self.assertEqual(inventory(self.root)["source_modules"], 3)

    def test_flags_recursed_without_exposing_other_values(self):
        data = inventory(self.root)
        flags = {(f["flag"], f["enabled"]) for f in data["feature_flags"]}
        self.assertIn(("enabled", False), flags)
        self.assertIn(("flags.beta", True), flags)

    def test_invalid_or_missing_root_denied(self):
        with self.assertRaises(ValueError):
            inventory(self.root / "does-not-exist")

    def test_invalid_syntax_reported_without_import(self):
        (self.root / "invalid.py").write_text("def f(:\n", encoding="utf-8")
        self.assertEqual(inventory(self.root)["syntax_errors"], ["invalid.py"])


if __name__ == "__main__":
    unittest.main()
