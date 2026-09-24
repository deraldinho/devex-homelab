import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.observation_daemon import (
    build_observation_context,
    resolve_wifi_interface,
    run_daemon_cycle,
    run_observation_daemon,
)

ATLAS = Path(__file__).resolve().parents[1]
AGENT_CONFIG = ATLAS.parent / "agent" / "config.json"


class EmptyScanner:
    def scan(self, _interface):
        return ()


class ManagedService:
    def read(self, _host_id, operation):
        return {"status": "healthy", "operation": operation.value}


class GitHubClient:
    def repository_snapshot(self, repo):
        return {"repo": repo, "pull_requests": [], "issues": [], "workflow_runs": []}


class FakeListener:
    def __init__(self):
        self.calls = 0
        self.closed = False
    def run_once(self, *, timeout_s):
        self.calls += 1
        return False
    def errors(self):
        return ()
    def close(self):
        self.closed = True

class ObservationDaemonTests(unittest.TestCase):
    def build(self, tmp):
        listener = FakeListener()
        context = build_observation_context(
            config_root=ATLAS,
            agent_config_path=AGENT_CONFIG,
            state_dir=Path(tmp),
            wifi_interface="wlan0",
            managed_read_service=ManagedService(),
            github_client=GitHubClient(),
            scanner=EmptyScanner(),
            interaction_listener=listener,
            expected_sha="a" * 40,
        )
        return context, listener

    def test_managed_polling_operations_are_explicit_and_bounded(self):
        payload = json.loads((ATLAS / "observation_config.json").read_text(encoding="utf-8"))
        for source in ("managed.core", "managed.x99"):
            operations = payload["sources"][source]["operations"]
            self.assertEqual(["uptime", "cpu", "memory"], operations)
            self.assertLessEqual(len(operations), 4)

    def test_context_exposes_pentium_core_x99_and_wifi(self):
        with tempfile.TemporaryDirectory() as tmp:
            context, _ = self.build(tmp)
            try:
                for source in (
                    "pentium.self", "managed.core", "managed.x99", "wifi.presence",
                    "github.deraldinho.devex-homelab", "github.deraldinho.L2jToren",
                    "mikrotik.perimeter",
                ):
                    self.assertIsNotNone(context.runtime.run_once(source))
            finally:
                context.close()

    def test_context_wires_real_dual_zone_to_affective_composition(self):
        with tempfile.TemporaryDirectory() as tmp:
            context, _ = self.build(tmp)
            try:
                context.runtime.run_once("managed.x99")
                self.assertTrue((Path(tmp) / "visual-state.json").is_file())
                self.assertTrue((Path(tmp) / "affective-state.json").is_file())
            finally:
                context.close()

    def test_cycle_services_scheduler_ipc_drains_bus_and_writes_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            context, listener = self.build(tmp)
            try:
                run_daemon_cycle(context)
                health = json.loads((Path(tmp) / "observation-affective-health.json").read_text(encoding="utf-8"))
                self.assertEqual(1, health["schema_version"])
                self.assertEqual("a" * 40, health["expected_sha"])
                self.assertEqual({"a1", "a2", "a3", "a4"}, set(health["restoration"]))
                self.assertGreaterEqual(health["bus_metrics"]["published"], 1)
                self.assertIsNone(context.bus.poll())
                self.assertEqual(1, listener.calls)
            finally:
                context.close()

    def test_wifi_interface_resolves_env_then_wireless_sysfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "wlp9s0" / "wireless").mkdir(parents=True)
            self.assertEqual("env0", resolve_wifi_interface({"ATLAS_WIFI_INTERFACE": "env0"}, root))
            self.assertEqual("wlp9s0", resolve_wifi_interface({}, root))

    def test_run_observation_daemon_closes_after_stop(self):
        class StopAfterOne:
            calls = 0
            def is_set(self):
                self.calls += 1
                return self.calls > 1
        with tempfile.TemporaryDirectory() as tmp:
            context, listener = self.build(tmp)
            run_observation_daemon(context, StopAfterOne())
            self.assertTrue(listener.closed)

    def test_expected_ignored_source_is_diagnostic_not_health_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            context, _ = self.build(tmp)
            try:
                run_daemon_cycle(context)
                health = json.loads((Path(tmp) / "observation-affective-health.json").read_text(encoding="utf-8"))
                self.assertEqual("healthy", health["status"])
                self.assertIn("ignored_source:wifi.presence", health["diagnostics"]["affective"])
                self.assertEqual([], health["errors"]["affective"])
            finally:
                context.close()

    def test_close_closes_runtime_and_listener(self):
        with tempfile.TemporaryDirectory() as tmp:
            context, listener = self.build(tmp)
            context.close()
            self.assertTrue(listener.closed)


if __name__ == "__main__":
    unittest.main()
