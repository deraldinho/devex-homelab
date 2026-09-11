from pathlib import Path
import unittest

VERIFY = Path(__file__).resolve().parents[1] / "verify.sh"


class VerifyConcurrencyContractTests(unittest.TestCase):
    def test_concurrency_probe_has_per_probe_diagnostics_and_global_deadline(self):
        text = VERIFY.read_text(encoding="utf-8")
        self.assertIn("probe_id=", text)
        self.assertIn("DEVEX_SIMULATION_CONCURRENCY_PROBE_PASS probe=", text)
        self.assertIn("DEVEX_SIMULATION_CONCURRENCY_PROBE_FAIL probe=", text)
        self.assertIn("timeout 10s docker compose exec", text)
        self.assertIn("nc -w 5 sim-core 8080", text)


if __name__ == "__main__":
    unittest.main()
