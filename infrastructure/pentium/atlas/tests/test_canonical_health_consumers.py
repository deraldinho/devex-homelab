import json
import sys
import tempfile
import unittest
from pathlib import Path


DASHBOARD_ROOT = Path(__file__).resolve().parents[2] / "dashboard"
sys.path.insert(0, str(DASHBOARD_ROOT))
import dashboard_collectors as dc

from infrastructure.pentium.atlas.discord_gateway import format_system_dashboard


def canonical_snapshot():
    return {
        "schema_version": 1,
        "generated_at": "2026-10-09T12:00:00+00:00",
        "state": "degraded",
        "components": [
            {"component_id": "atlas-cognitive.service", "host": "pentium", "expected_state": "running", "state": "healthy"},
            {"component_id": "atlas-discord.service", "host": "pentium", "expected_state": "running", "state": "disconnected"},
            {"component_id": "atlas-observation.service", "host": "pentium", "expected_state": "running", "state": "stale"},
            {"component_id": "atlas-dashboard.service", "host": "pentium", "expected_state": "running", "state": "healthy"},
            {"component_id": "atlas-voice.service", "host": "pentium", "expected_state": "paused", "state": "paused_intentionally"},
        ],
    }


class CanonicalHealthConsumerTests(unittest.TestCase):
    def test_discord_prefers_canonical_functional_state_over_systemd_liveness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "health-supervisor.json").write_text(json.dumps(canonical_snapshot()), encoding="utf-8")
            calls = []
            def runner(*args, **kwargs):
                calls.append((args, kwargs))
                raise AssertionError("systemctl fallback should not run with canonical health")
            rendered = format_system_dashboard(state_dir=root, systemctl_runner=runner)
        self.assertIn("atlas-discord.service" + chr(96) + ": disconnected", rendered)
        self.assertIn("atlas-observation.service" + chr(96) + ": stale", rendered)
        self.assertIn("atlas-voice.service" + chr(96) + ": paused_intentionally", rendered)
        self.assertEqual([], calls)

    def test_discord_corrupt_snapshot_falls_back_to_existing_systemd_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "health-supervisor.json").write_text("{bad", encoding="utf-8")
            class Result:
                stdout = "active\n"
            rendered = format_system_dashboard(
                state_dir=root,
                systemctl_runner=lambda *args, **kwargs: Result(),
            )
        self.assertIn("atlas-cognitive.service" + chr(96) + ": active", rendered)
        self.assertIn("atlas-discord.service" + chr(96) + ": active", rendered)
        self.assertIn("atlas-observation.service" + chr(96) + ": active", rendered)

    def test_dashboard_uses_same_canonical_component_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical = root / "health-supervisor.json"
            canonical.write_text(json.dumps(canonical_snapshot()), encoding="utf-8")
            old_health = root / "old-health.json"
            old_health.write_text('{"status":"healthy"}', encoding="utf-8")
            voice = root / "voice.json"
            voice.write_text('{"anc_enabled":false}', encoding="utf-8")
            sha = root / "sha"
            sha.write_text("abc", encoding="utf-8")
            cfg = dc.default_config() | {
                "health_supervisor_path": str(canonical),
                "health_path": str(old_health),
                "voice_config_path": str(voice),
                "deploy_sha_path": str(sha),
            }
            status = dc.collect_status(cfg, command_runner=lambda *_: dc.CommandResult(0, "active\n", ""))
        self.assertEqual("degraded", status["atlas"]["health"])
        self.assertEqual("disconnected", status["services"]["discord"]["health"])
        self.assertEqual("stale", status["services"]["observation"]["health"])
        self.assertEqual("paused_intentionally", status["services"]["voice"]["health"])

    def test_dashboard_missing_or_corrupt_canonical_snapshot_preserves_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "health-supervisor.json"
            bad.write_text("{bad", encoding="utf-8")
            old_health = root / "old-health.json"
            old_health.write_text('{"status":"healthy"}', encoding="utf-8")
            voice = root / "voice.json"
            voice.write_text('{"anc_enabled":false}', encoding="utf-8")
            cfg = dc.default_config() | {
                "health_supervisor_path": str(bad),
                "health_path": str(old_health),
                "voice_config_path": str(voice),
            }
            status = dc.collect_status(cfg, command_runner=lambda *_: dc.CommandResult(0, "active\n", ""))
        self.assertEqual("healthy", status["atlas"]["health"])
        self.assertNotIn("health", status["services"]["discord"])


if __name__ == "__main__":
    unittest.main()
