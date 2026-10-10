import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AutonomyWiringV1Tests(unittest.TestCase):
    def test_cognitive_owner_preserves_dispatcher_and_uses_managed_multi_host_executor(self):
        source = (ROOT / "cognitive_daemon.py").read_text(encoding="utf-8")
        compact = source.replace(" ", "")
        self.assertIn("SafeLocalCapabilityExecutor", source)
        self.assertIn("MultiHostCapabilityExecutor", source)
        self.assertIn("ManagedInventory", source)
        self.assertIn("ManagedControlService", source)
        self.assertIn("SshTransport", source)
        self.assertIn("ControlAuditJournal", source)
        self.assertIn('auto_control_allow=("restart_service","restart_container")', compact)
        self.assertIn('auto_service_targets=(("pentium","atlas-observation.service"),("pentium","atlas-dashboard.service"))', compact)
        self.assertIn("auto_container_targets=()", compact)
        self.assertNotIn('auto_hosts=("pentium","core"', compact)
        self.assertIn("MultiHostCapabilityExecutor(", source)
        self.assertIn("on_executed=capabilities.registrar_execucao", source)
        self.assertIn("CapabilityDispatcher(autonomy_executor,workspace_executor", source)
        self.assertIn("capability_sink=dispatcher", source)

    def test_remote_control_remains_bound_to_managed_inventory_not_static_broad_hosts(self):
        source = (ROOT / "cognitive_daemon.py").read_text(encoding="utf-8")
        compact = source.replace(" ", "")
        self.assertIn('AGENT_ROOT/"agent"/"config.json"', compact)
        self.assertIn("_managed_host_from_config", source)
        self.assertIn("ManagedInventory([", source)
        self.assertNotIn('auto_hosts=("pentium","x99","core")', compact)

    def test_voice_activation_is_not_introduced_by_autonomy_wiring(self):
        source = (ROOT / "cognitive_daemon.py").read_text(encoding="utf-8")
        self.assertNotIn("atlas-voice.service", source)


if __name__ == "__main__":
    unittest.main()
