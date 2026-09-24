"""Testes do Temporal Correlator."""
import unittest

from infrastructure.pentium.atlas.proprioception.temporal_correlator import (
    TemporalCorrelation,
    TemporalCorrelator,
)


class TemporalCorrelatorTests(unittest.TestCase):
    def setUp(self):
        self.correlator = TemporalCorrelator(
            window_seconds=300.0,
            min_cooccurrences=3,
            max_events=100,
            known_rules={("cpu_high", "swap_high"): "pressao de memoria"},
        )

    def test_no_correlation_with_few_events(self):
        r1 = self.correlator.record_event("cpu_high", "2026-09-22T12:00:00+00:00")
        r2 = self.correlator.record_event("swap_high", "2026-09-22T12:00:01+00:00")
        self.assertEqual(0, len(r1))
        self.assertEqual(0, len(r2))

    def test_correlation_detected_after_min_cooccurrences(self):
        correlations = []
        for i in range(5):
            base = f"2026-09-22T12:{i:02d}:00+00:00"
            offset = f"2026-09-22T12:{i:02d}:02+00:00"
            self.correlator.record_event("cpu_high", base)
            r = self.correlator.record_event("swap_high", offset)
            correlations.extend(r)

        self.assertGreater(len(correlations), 0)
        corr = correlations[-1]
        self.assertIsInstance(corr, TemporalCorrelation)
        self.assertGreaterEqual(corr.co_occurrences, 3)
        self.assertGreater(corr.confidence, 0)

    def test_known_rule_lookup(self):
        interpretation = self.correlator.get_known_interpretation("cpu_high", "swap_high")
        self.assertEqual("pressao de memoria", interpretation)
        self.assertIsNone(self.correlator.get_known_interpretation("cpu_high", "disk_full"))

    def test_no_self_correlation(self):
        for i in range(5):
            ts = f"2026-09-22T12:{i:02d}:00+00:00"
            r = self.correlator.record_event("same_event", ts)
            self.assertEqual(0, len(r))

    def test_events_outside_window_not_correlated(self):
        correlator = TemporalCorrelator(window_seconds=10.0, min_cooccurrences=2)
        # Events 1 hour apart — outside 10s window
        for i in range(5):
            correlator.record_event("a", f"2026-09-22T{10+i}:00:00+00:00")
            r = correlator.record_event("b", f"2026-09-22T{10+i}:30:00+00:00")
            self.assertEqual(0, len(r))

    def test_get_all_correlations(self):
        for i in range(5):
            ts = f"2026-09-22T12:{i:02d}:00+00:00"
            ts2 = f"2026-09-22T12:{i:02d}:01+00:00"
            self.correlator.record_event("event_a", ts)
            self.correlator.record_event("event_b", ts2)
        all_corrs = self.correlator.get_all_correlations()
        self.assertGreater(len(all_corrs), 0)
        self.assertTrue(all(c.confidence > 0 for c in all_corrs))

    def test_event_count(self):
        for i in range(10):
            self.correlator.record_event("x", f"2026-09-22T12:{i:02d}:00+00:00")
        self.assertEqual(10, self.correlator.event_count())

    def test_bounded_events(self):
        correlator = TemporalCorrelator(max_events=5)
        for i in range(10):
            correlator.record_event("x", f"2026-09-22T12:{i:02d}:00+00:00")
        self.assertLessEqual(correlator.event_count(), 5)


if __name__ == "__main__":
    unittest.main()
