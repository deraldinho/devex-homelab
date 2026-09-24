"""Testes do Baseline Tracker."""
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.proprioception.baseline_tracker import (
    BaselineDeviation,
    BaselineStats,
    BaselineTracker,
)


NOW = "2026-09-22T12:00:00+00:00"


class BaselineStatsTests(unittest.TestCase):
    def test_variance_with_few_samples(self):
        s = BaselineStats(count=1, mean=5.0, m2=0.0)
        self.assertAlmostEqual(0.0, s.variance)
        self.assertFalse(s.is_deviation(5.0))

    def test_z_score_requires_enough_samples(self):
        s = BaselineStats(count=3, mean=5.0, m2=10.0)
        self.assertAlmostEqual(0.0, s.z_score(10.0))


class BaselineTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "baselines.json"
        self.tracker = BaselineTracker(self.path, sigma=2.0, hysteresis=3)

    def tearDown(self):
        self.tmp.cleanup()

    def test_update_builds_baseline(self):
        for v in [50.0, 51.0, 49.0, 50.5, 48.5, 52.0, 50.0, 49.5, 51.5, 50.0]:
            self.tracker.update("core", "cpu_percent", v, NOW)
        stats = self.tracker.get_stats("core", "cpu_percent")
        self.assertIsNotNone(stats)
        self.assertEqual(10, stats.count)
        self.assertAlmostEqual(50.2, stats.mean, places=1)

    def test_no_deviation_within_normal(self):
        for v in range(20):
            result = self.tracker.update("core", "cpu", float(50 + v % 3), NOW)
        # Normal values should not trigger deviation
        result = self.tracker.update("core", "cpu", 52.0, NOW)
        self.assertIsNone(result)

    def test_deviation_detected_after_hysteresis(self):
        # Seed baseline with stable values
        for _ in range(20):
            self.tracker.update("core", "disk", 50.0, NOW)

        # Single spike should not trigger (hysteresis=3)
        r1 = self.tracker.update("core", "disk", 150.0, NOW)
        self.assertIsNone(r1)
        r2 = self.tracker.update("core", "disk", 150.0, NOW)
        self.assertIsNone(r2)
        # Third consecutive deviation triggers
        r3 = self.tracker.update("core", "disk", 150.0, NOW)
        self.assertIsNotNone(r3)
        self.assertIsInstance(r3, BaselineDeviation)
        self.assertEqual("core", r3.node)
        self.assertGreater(abs(r3.z_score), 2.0)

    def test_deviation_resets_on_normal(self):
        for _ in range(20):
            self.tracker.update("core", "mem", 50.0, NOW)
        self.tracker.update("core", "mem", 150.0, NOW)
        self.tracker.update("core", "mem", 150.0, NOW)
        # Normal value resets counter
        self.tracker.update("core", "mem", 50.0, NOW)
        r = self.tracker.update("core", "mem", 150.0, NOW)
        self.assertIsNone(r)  # Counter reset, needs 3 again

    def test_persistence(self):
        for v in [10.0, 20.0, 30.0, 40.0, 50.0]:
            self.tracker.update("pentium", "temp", v, NOW)
        self.tracker.save()

        tracker2 = BaselineTracker(self.path)
        stats = tracker2.get_stats("pentium", "temp")
        self.assertIsNotNone(stats)
        self.assertEqual(5, stats.count)
        self.assertAlmostEqual(30.0, stats.mean)

    def test_metric_limit(self):
        tracker = BaselineTracker(self.path, sigma=2.0, hysteresis=3)
        tracker.MAX_METRICS = 5
        for i in range(10):
            tracker.update("node", f"metric_{i}", float(i), NOW)
        self.assertEqual(5, len(tracker.get_all_stats()))


if __name__ == "__main__":
    unittest.main()
