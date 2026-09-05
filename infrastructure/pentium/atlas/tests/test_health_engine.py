import unittest

from infrastructure.pentium.atlas.health_engine import assess
from infrastructure.pentium.atlas.state_model import Signal, TechnicalState


class HealthEngineTests(unittest.TestCase):
    def test_severity_precedence_selects_worst_required_signal(self):
        signals = [
            Signal("pentium", TechnicalState.HEALTHY, 0),
            Signal("core", TechnicalState.BUSY, 1, reason="core.cpu.high"),
            Signal("internet", TechnicalState.DEGRADED, 2, reason="internet.loss"),
            Signal("dns", TechnicalState.STRESSED, 3, reason="dns.timeout"),
            Signal("mikrotik", TechnicalState.CRITICAL, 4, reason="mikrotik.offline"),
        ]
        result = assess(signals, TechnicalState.HEALTHY)
        self.assertEqual(result.state, TechnicalState.CRITICAL)
        self.assertEqual(result.intensity, 4)
        self.assertIn("mikrotik:mikrotik.offline", result.reasons)

    def test_optional_critical_signal_cannot_raise_global_to_critical(self):
        signals = [
            Signal("core", TechnicalState.HEALTHY, 0),
            Signal("x99", TechnicalState.CRITICAL, 4, required=False, reason="x99.offline"),
        ]
        result = assess(signals, TechnicalState.HEALTHY)
        self.assertEqual(result.state, TechnicalState.HEALTHY)

    def test_problem_to_normal_becomes_recovered(self):
        result = assess(
            [Signal("core", TechnicalState.HEALTHY, 0)],
            TechnicalState.CRITICAL,
        )
        self.assertEqual(result.state, TechnicalState.RECOVERED)
        self.assertTrue(result.recovered)

    def test_healthy_to_healthy_is_not_recovered(self):
        result = assess(
            [Signal("core", TechnicalState.HEALTHY, 0)],
            TechnicalState.HEALTHY,
        )
        self.assertEqual(result.state, TechnicalState.HEALTHY)
        self.assertFalse(result.recovered)

    def test_intensity_is_maximum_relevant_signal_and_is_clamped(self):
        result = assess(
            [
                Signal("core", TechnicalState.BUSY, 2),
                Signal("dns", TechnicalState.DEGRADED, 99),
            ],
            None,
        )
        self.assertEqual(result.state, TechnicalState.DEGRADED)
        self.assertEqual(result.intensity, 4)


if __name__ == "__main__":
    unittest.main()
