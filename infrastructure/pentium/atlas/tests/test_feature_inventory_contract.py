"""Safe, read-only feature-inventory contract.

Never imports application modules merely to classify them: import side effects
could execute integrations. Enabled features are valid; disabled features are
tracked, not universally forbidden.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

ATLAS_ROOT = Path(__file__).resolve().parents[1]


def collect_inventory(root: Path = ATLAS_ROOT) -> dict:
    configs = {}
    disabled = []
    enabled = []
    for path in sorted(root.glob("config*.json")):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("config_not_object")
        configs[path.name] = data
        def walk(value, prefix=""):
            if not isinstance(value, dict):
                return
            for key, item in value.items():
                name = f"{prefix}.{key}" if prefix else key
                if isinstance(item, bool):
                    entry = {"file": path.name, "flag": name}
                    (enabled if item else disabled).append(entry)
                elif isinstance(item, dict):
                    walk(item, name)
        walk(data)
    modules = sorted(path.name for path in root.glob("*.py") if path.is_file())
    syntax_errors = []
    for name in modules:
        try:
            ast.parse((root / name).read_text(encoding="utf-8-sig"))
        except SyntaxError:
            syntax_errors.append(name)
    return {"configs": len(configs), "modules": len(modules),
            "disabled": disabled, "enabled": enabled,
            "syntax_errors": syntax_errors}


class FeatureInventoryContractTests(unittest.TestCase):
    def test_config_inventory_is_readonly(self):
        inventory = collect_inventory()
        self.assertGreater(inventory["configs"], 0)
        self.assertGreater(inventory["modules"], 0)
        self.assertEqual(inventory["syntax_errors"], [])

    def test_agency_worker_stays_opt_in(self):
        config = json.loads((ATLAS_ROOT / "config_agency_specialists.json").read_text(encoding="utf-8"))
        self.assertIs(config["enabled"], False)

    def test_known_service_entrypoint_is_not_dead_code(self):
        inventory = collect_inventory()
        self.assertTrue((ATLAS_ROOT / "cognitive_daemon.py").is_file())
        service = (ATLAS_ROOT / "atlas-cognitive.service").read_text(encoding="utf-8")
        self.assertIn("-m atlas.cognitive_daemon", service)
        self.assertGreater(inventory["modules"], 100)


if __name__ == "__main__":
    unittest.main()
