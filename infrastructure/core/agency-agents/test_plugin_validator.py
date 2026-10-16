"""Offline tests for pinned Agency Agents Hermes staging contract."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("plugin_validator.py")
spec = importlib.util.spec_from_file_location("agency_stage_validator", MODULE_PATH)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
ValidationError = validator.ValidationError


class StageValidatorTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.plugin = self.root / "source" / "integrations" / "hermes" / "agency-agents-router"
        (self.plugin / "data").mkdir(parents=True)
        self.manifest = self.plugin / "plugin.yaml"
        self.agents = self.plugin / "data" / "agents.json"
        self.manifest.write_text(
            "name: agency-agents-router\nversion: 1.0.0\n"
            "description: Lazy router for The Agency.\nprovides_tools:\n"
            "  - agency_agents_search\n  - agency_agents_inspect\n"
            "  - agency_agents_load\n  - agency_agents_delegate\n",
            encoding="utf-8",
        )
        # Static validation must NOT import or execute generated plugin code.
        (self.plugin / "__init__.py").write_text(
            'raise RuntimeError("NEVER EXECUTE GENERATED PLUGIN")\n', encoding="utf-8"
        )
        self.sample = {
            "slug": "game-designer", "name": "Game Designer",
            "description": "Design and iterate games",
            "division": "game-development", "color": "teal",
            "emoji": "🎮", "vibe": "precise",
            "source_path": "game-development/game-designer.md",
            "body": "A long, detailed gaming specialist role.",
        }
        self.set_agents([self.sample])

    def set_agents(self, agents):
        self.agents.write_text(json.dumps(agents, ensure_ascii=False), encoding="utf-8")

    def validate(self):
        return validator.validate_plugin_staging(self.root)

    def test_upstream_fields_and_canonical_layout_accepted(self):
        result = self.validate()
        self.assertTrue(result["valid"])
        self.assertEqual(result["agent_count"], 1)
        self.assertEqual(len(result["tools"]), 4)
        self.assertIn("source", result["plugin_path"])

    def test_duplicate_tools_are_rejected(self):
        with self.manifest.open("a", encoding="utf-8") as f:
            f.write("  - agency_agents_delegate\n")
        with self.assertRaises(ValidationError):
            self.validate()

    def test_missing_tool_rejected(self):
        s = self.manifest.read_text(encoding="utf-8")
        self.manifest.write_text(s.replace("  - agency_agents_delegate\n", ""), encoding="utf-8")
        with self.assertRaises(ValidationError):
            self.validate()

    def test_extra_tool_rejected(self):
        with self.manifest.open("a", encoding="utf-8") as f:
            f.write("  - agency_agents_execute\n")
        with self.assertRaises(ValidationError):
            self.validate()

    def test_duplicate_slug_rejected(self):
        self.set_agents([self.sample, self.sample])
        with self.assertRaises(ValidationError):
            self.validate()

    def test_bad_json_rejected(self):
        self.agents.write_text("{malformed", encoding="utf-8")
        with self.assertRaises(ValidationError):
            self.validate()

    def test_bad_path_rejected(self):
        self.set_agents([{**self.sample, "source_path": "../../escape.md"}])
        with self.assertRaises(ValidationError):
            self.validate()

    def test_missing_generated_file_rejected(self):
        self.manifest.unlink()
        with self.assertRaises(ValidationError):
            self.validate()

    def test_wrong_layout_rejected(self):
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaises(ValidationError):
                validator.validate_plugin_staging(other)

    def test_symlink_escape_rejected(self):
        # Windows symlinks require Developer Mode or special permissions.
        with tempfile.TemporaryDirectory() as other:
            escaped = Path(other) / "plugin.yaml"
            escaped.write_text(self.manifest.read_text(encoding="utf-8"), encoding="utf-8")
            self.manifest.unlink()
            try:
                self.manifest.symlink_to(escaped)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable on host")
            with self.assertRaises(ValidationError):
                self.validate()

    def test_long_legitimate_body_accepted(self):
        self.set_agents([{**self.sample, "body": "Detailed instructions. " * 1000}])
        self.assertEqual(self.validate()["agent_count"], 1)

    def test_absolute_stage_required(self):
        with self.assertRaises(ValidationError):
            validator.validate_plugin_staging("relative-stage")

    def test_invalid_division_rejected(self):
        self.set_agents([{**self.sample, "division": "../engineering"}])
        with self.assertRaises(ValidationError):
            self.validate()


if __name__ == "__main__":
    unittest.main()
