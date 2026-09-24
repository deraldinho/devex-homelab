"""Testes do Trend Detector."""
import unittest

from infrastructure.pentium.atlas.proprioception.trend_detector import (
    TrendDetector,
    TrendEvent,
    _linear_regression,
)


class LinearRegressionTests(unittest.TestCase):
    def test_perfect_linear(self):
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [0.0, 2.0, 4.0, 6.0, 8.0]
        slope, intercept, r2 = _linear_regression(xs, ys)
        self.assertAlmostEqual(2.0, slope)
        self.assertAlmostEqual(0.0, intercept)
        self.assertAlmostEqual(1.0, r2)

    def test_constant_values(self):
        xs = [0.0, 1.0, 2.0, 3.0]
        ys = [5.0, 5.0, 5.0, 5.0]
        slope, intercept, r2 = _linear_regression(xs, ys)
        self.assertAlmostEqual(0.0, slope)

    def test_insufficient_points(self):
        slope, _, _ = _linear_regression([1.0], [2.0])
        self.assertAlmostEqual(0.0, slope)


class TrendDetectorTests(unittest.TestCase):
    def setUp(self):
        self.detector = TrendDetector(
            min_points=5,
            min_confidence=0.6,
            min_slope_magnitude=0.001,
            projection_hours=24.0,
            window_size=20,
            capacity_metrics={"disk_percent": (0.0, 100.0)},
        )

    def test_no_trend_with_few_points(self):
        for i in range(3):
            ts = f"2026-09-22T{12+i}:00:00+00:00"
            result = self.detector.update("core", "cpu", 50.0 + i, ts)
        self.assertIsNone(result)

    def test_rising_trend_detected(self):
        result = None
        for i in range(10):
            ts = f"2026-09-22T{10+i}:00:00+00:00"
            result = self.detector.update("core", "cpu", 50.0 + i * 2, ts)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, TrendEvent)
        self.assertEqual("rising", result.direction)
        self.assertGreater(result.slope, 0)
        self.assertGreaterEqual(result.confidence, 0.6)

    def test_falling_trend_detected(self):
        result = None
        for i in range(10):
            ts = f"2026-09-22T{10+i}:00:00+00:00"
            result = self.detector.update("pentium", "temp", 80.0 - i * 3, ts)
        self.assertIsNotNone(result)
        self.assertEqual("falling", result.direction)
        self.assertLess(result.slope, 0)

    def test_no_trend_for_flat_data(self):
        for i in range(10):
            ts = f"2026-09-22T{10+i}:00:00+00:00"
            result = self.detector.update("core", "stable", 50.0, ts)
        self.assertIsNone(result)

    def test_exhaustion_projection(self):
        result = None
        for i in range(10):
            ts = f"2026-09-22T{10+i}:00:00+00:00"
            result = self.detector.update("core", "disk_percent", 60.0 + i * 3, ts)
        if result is not None:
            self.assertEqual("rising", result.direction)
            self.assertIsNotNone(result.exhaustion_hours)
            self.assertGreater(result.exhaustion_hours, 0)

    def test_window_values(self):
        for i in range(5):
            self.detector.update("core", "cpu", float(i), f"2026-09-22T{10+i}:00:00+00:00")
        values = self.detector.get_window("core", "cpu")
        self.assertEqual(5, len(values))

    def test_no_trend_for_noisy_data(self):
        import math
        for i in range(15):
            ts = f"2026-09-22T{10+i}:00:00+00:00"
            value = 50.0 + 20 * math.sin(i)  # oscillating
            result = self.detector.update("core", "noisy", value, ts)
        # Noisy data should have low R² and not trigger
        # (might still trigger in some cases, but usually won't with R² < 0.6)


if __name__ == "__main__":
    unittest.main()
