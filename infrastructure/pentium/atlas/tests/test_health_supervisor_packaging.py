import json
import unittest
from pathlib import Path


ATLAS = Path(__file__).resolve().parents[1]


class HealthSupervisorPackagingTests(unittest.TestCase):
    def test_config_declares_core_services_voice_paused_and_managed_hosts(self):
        config = json.loads((ATLAS / "config_health_supervisor.json").read_text(encoding="utf-8"))
        self.assertEqual(1, config["schema_version"])
        self.assertTrue(config["features"]["health_supervisor_v1"])
        self.assertFalse(config["features"]["self_healing_v1"])
        components = config["components"]
        for unit in (
            "atlas-observation.service",
            "atlas-cognitive.service",
            "atlas-discord.service",
            "atlas-dashboard.service",
        ):
            self.assertEqual("running", components[unit]["expected_state"])
        self.assertEqual("paused", components["atlas-voice.service"]["expected_state"])
        self.assertTrue(config["managed_hosts"]["x99"]["enabled"])
        self.assertTrue(config["managed_hosts"]["core"]["enabled"])

    def test_systemd_unit_runs_supervisor_and_restarts_only_on_failure(self):
        unit = (ATLAS / "atlas-health-supervisor.service").read_text(encoding="utf-8")
        self.assertIn("ExecStart=/usr/bin/python3 -m atlas.health_supervisor_daemon", unit)
        self.assertIn("Restart=on-failure", unit)
        self.assertIn("ReadWritePaths=%h/pentium-agent/atlas/runtime", unit)
        self.assertIn("NoNewPrivileges=true", unit)

    def test_installer_packages_and_enables_supervisor_without_enabling_voice(self):
        script = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for name in (
            "health_supervisor_model.py",
            "health_supervisor.py",
            "health_probes.py",
            "host_adapters.py",
            "recovery_model.py",
            "decision_preconditions.py",
            "multi_host_executor.py",
            "recovery_controller.py",
            "health_supervisor_daemon.py",
        ):
            self.assertIn(name, script)
        self.assertIn("config_health_supervisor.json", script)
        self.assertIn("atlas-health-supervisor.service", script)
        self.assertIn("systemctl --user enable atlas-health-supervisor.service", script)
        self.assertNotIn("systemctl --user enable atlas-voice.service", script)

    def test_deployed_modules_prefer_top_level_agent_package_with_source_fallback(self):
        for name in ("host_adapters.py", "multi_host_executor.py"):
            source = (ATLAS / name).read_text(encoding="utf-8")
            self.assertIn("from agent.", source)
            self.assertIn("from infrastructure.pentium.agent.", source)


if __name__ == "__main__":
    unittest.main()
