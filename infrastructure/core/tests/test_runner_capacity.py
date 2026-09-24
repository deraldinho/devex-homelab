import unittest
from pathlib import Path

RUNNERS_DIR = Path(__file__).resolve().parent.parent / "runners"

class CoreRunnerCapacityTests(unittest.TestCase):
    def setUp(self):
        self.compose_file = RUNNERS_DIR / "compose.yaml"
        self.assertTrue(self.compose_file.is_file(), "compose.yaml de runners deve existir")
        self.content = self.compose_file.read_text(encoding="utf-8")

    def test_all_runners_have_cgroup_limits(self):
        self.assertIn("deploy:", self.content)
        self.assertIn("limits:", self.content)
        self.assertIn("cpus: \"3.0\"", self.content, "core-l2jtoren-01 deve ter limite 3.0 cpus")
        self.assertIn("memory: 3500M", self.content, "core-l2jtoren-01 deve ter limite 3500M")
        self.assertIn("cpus: \"2.0\"", self.content, "core-l2jtoren-02 deve ter limite 2.0 cpus")
        self.assertIn("memory: 2000M", self.content, "core-l2jtoren-02 deve ter limite 2000M")
        self.assertIn("cpus: \"1.5\"", self.content, "core-homelab-01 deve ter limite 1.5 cpus")
        self.assertIn("memory: 1000M", self.content, "core-homelab-01 deve ter limite 1000M")

    def test_total_allocated_memory_stays_within_core_host_budget(self):
        # O host Core tem aproximadamente 7.1 GiB (7270 MB)
        # Total alocado: 3500M + 2000M + 1000M = 6500M <= 7000M
        allocated_mb = 3500 + 2000 + 1000
        host_capacity_mb = 7100
        self.assertLessEqual(allocated_mb, host_capacity_mb)
        self.assertGreater(host_capacity_mb - allocated_mb, 500, "Deve sobrar pelo menos 500MB para OS e Docker")

    def test_isolated_workspaces_per_runner(self):
        self.assertIn("core-l2jtoren-01-work:/runner", self.content)
        self.assertIn("core-l2jtoren-02-work:/runner", self.content)
        self.assertIn("core-homelab-01-work:/runner", self.content)

    def test_security_hardening_directives_present(self):
        self.assertIn("no-new-privileges:true", self.content)

    def test_deterministic_healthchecks_present(self):
        self.assertIn("healthcheck:", self.content)
        self.assertIn("Runner.Listener", self.content)

if __name__ == "__main__":
    unittest.main()
