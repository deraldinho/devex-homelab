import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AutonomyWiringV1Tests(unittest.TestCase):
    def test_cognitive_owner_wires_narrow_local_autonomy(self):
        source = (ROOT / "cognitive_daemon.py").read_text(encoding="utf-8")
        self.assertIn("SafeLocalCapabilityExecutor", source)
        self.assertIn('auto_control_allow=("restart_service",)', source)
        self.assertIn('auto_hosts=("pentium",)', source)
        self.assertIn('"atlas-observation.service"', source)
        self.assertIn('"atlas-dashboard.service"', source)
        self.assertIn("on_executed=capabilities.registrar_execucao", source)
        self.assertIn("capability_sink=autonomy_executor", source)


if __name__ == "__main__":
    unittest.main()
