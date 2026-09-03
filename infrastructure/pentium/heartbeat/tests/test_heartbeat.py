import json
import sqlite3
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import heartbeat


class HeartbeatContractTests(unittest.TestCase):
    def test_user_unit_check_uses_fixed_systemctl_contract(self):
        calls = []

        def runner(command, timeout):
            calls.append(command)
            return heartbeat.CommandResult(0, "active\n", "")

        result = heartbeat.check_unit(
            "pentium-agent.service", user=True, command_runner=runner
        )
        self.assertTrue(result["ok"])
        self.assertEqual(
            calls,
            [["systemctl", "--user", "is-active", "pentium-agent.service"]],
        )

    def test_sqlite_quick_check_accepts_healthy_control_database(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "control.db"
            connection = sqlite3.connect(path)
            try:
                connection.execute("create table heartbeat_probe(id integer primary key)")
                connection.commit()
            finally:
                connection.close()
            result = heartbeat.check_database(path)
        self.assertTrue(result["ok"])
        self.assertEqual(result["detail"], "quick_check=ok")

    def test_network_check_requires_core_healthy(self):
        def runner(command, timeout):
            payload = {"status": "healthy", "nodes": [{"name": "core"}]}
            return heartbeat.CommandResult(0, json.dumps(payload), "")

        result = heartbeat.check_core_network(
            Path("network_health.py"),
            Path("network_inventory.json"),
            command_runner=runner,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["detail"], "core=healthy")

    def test_required_failure_degrades_summary(self):
        checks = {
            "os": {"ok": True, "required": True, "detail": "linux/pentium"},
            "agent": {"ok": False, "required": True, "detail": "inactive"},
        }
        summary = heartbeat.summarize(checks, {"memory_available_mb": 512})
        self.assertEqual(summary["status"], "degraded")

    def test_resource_thresholds_are_gated(self):
        result = heartbeat.check_resources(
            disk_free_percent=8.0,
            memory_available_mb=128,
            min_disk_free_percent=10.0,
            min_memory_available_mb=256,
        )
        self.assertFalse(result["ok"])
        self.assertIn("disk_free=8.0%", result["detail"])

    def test_write_state_is_valid_json_and_replaces_previous_snapshot(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "health" / "latest.json"
            first = {"status": "healthy", "checks": {}, "metrics": {}}
            second = {"status": "degraded", "checks": {}, "metrics": {}}
            heartbeat.write_state(path, first)
            heartbeat.write_state(path, second)
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], "degraded")

    def test_human_output_is_ascii_safe(self):
        summary = {
            "status": "healthy",
            "checks": {
                "os": {"ok": True},
                "tailscale": {"ok": True},
                "agent": {"ok": True},
                "sentinel": {"ok": True},
                "jobs": {"ok": True},
                "db": {"ok": True},
                "resources": {"ok": True},
                "core": {"ok": True},
            },
        }
        rendered = heartbeat.render_text(summary)
        rendered.encode("ascii")
        self.assertEqual(
            rendered,
            "PENTIUM: HEALTHY | OS=ok | TAILSCALE=ok | AGENT=ok | "
            "SENTINEL=ok | JOBS=ok | DB=ok | RESOURCES=ok | CORE=ok",
        )


if __name__ == "__main__":
    unittest.main()
