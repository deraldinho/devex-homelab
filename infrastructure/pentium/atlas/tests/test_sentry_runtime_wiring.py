"""Opt-in runtime wiring for Sentry without changing existing production defaults."""
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from infrastructure.pentium.atlas.failure_memory import FailureMemory
from infrastructure.pentium.atlas.health_supervisor_daemon import build_owner

ROOT = Path(__file__).resolve().parents[1]


class SentryRuntimeWiringTests(unittest.TestCase):
    def _supervisor_config(self, root):
        body = {"schema_version": 1, "poll_interval_s": 5,
                "features": {"health_supervisor_v1": True, "self_healing_v1": False},
                "components": {}, "managed_hosts": {}}
        (root / "config_health_supervisor.json").write_text(json.dumps(body), encoding="utf-8")

    def test_health_supervisor_default_stays_off_and_creates_no_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._supervisor_config(root)
            with patch.dict("os.environ", {}, clear=True):
                owner = build_owner(config_root=root, state_dir=root / "runtime")
            try:
                self.assertIsNone(owner.failure_memory)
                self.assertFalse((root / "runtime" / "failure-memory.sqlite3").exists())
                self.assertEqual(owner.run_once().state.value, "healthy")
            finally:
                owner.close()

    def test_health_supervisor_opt_in_opens_real_failure_store_and_closes_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._supervisor_config(root)
            db_path = root / "runtime" / "failure-memory.sqlite3"
            with patch.dict("os.environ", {"ATLAS_SENTRY_HEALTH_SHADOW":"1"}, clear=True):
                owner = build_owner(config_root=root, state_dir=root / "runtime")
            self.assertIsInstance(owner.failure_memory, FailureMemory)
            try:
                owner.run_once()
                self.assertTrue(db_path.exists())
                self.assertEqual(owner.failure_memory.stats()["lessons"], 0)
            finally:
                owner.close()
            # Windows will only allow unlink after the SQLite connection closes.
            db_path.unlink()
            self.assertFalse(db_path.exists())

    def test_cognitive_factory_references_optional_backend_wrapper_and_cleanup(self):
        # Contract check for the deployed runtime owner; the full build is
        # exercised by its existing injection tests (requires host inventory).
        tree = ast.parse((ROOT / "cognitive_daemon.py").read_text(encoding="utf-8"))
        nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                 and n.name == "build_owner"]
        self.assertEqual(len(nodes), 1)
        names = {n.func.id for n in ast.walk(nodes[0])
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertIn("create_sentry_inference_backend", names)


if __name__ == "__main__":
    unittest.main()
