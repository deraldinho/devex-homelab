import unittest

from infrastructure.pentium.atlas.stimulus_bus import StimulusBus
from infrastructure.pentium.atlas.stimulus_model import Stimulus, StimulusSeverity


def make_stimulus(stimulus_id: str, severity: StimulusSeverity) -> Stimulus:
    return Stimulus(
        stimulus_id=stimulus_id,
        source="core",
        kind="status_changed",
        severity=severity,
        timestamp="2026-09-04T01:00:00+00:00",
        payload={"id": stimulus_id},
        novelty=1.0,
        correlation_id=f"corr-{stimulus_id}",
        current_fingerprint=stimulus_id,
    )


class StimulusBusTests(unittest.TestCase):
    def test_fifo_under_capacity(self):
        bus = StimulusBus(capacity=2)
        bus.publish(make_stimulus("a", StimulusSeverity.INFO))
        bus.publish(make_stimulus("b", StimulusSeverity.WARNING))
        self.assertEqual(bus.poll().stimulus_id, "a")
        self.assertEqual(bus.poll().stimulus_id, "b")
        self.assertIsNone(bus.poll())

    def test_overflow_evicts_oldest_noncritical(self):
        bus = StimulusBus(capacity=2)
        bus.publish(make_stimulus("a", StimulusSeverity.INFO))
        bus.publish(make_stimulus("b", StimulusSeverity.WARNING))
        result = bus.publish(make_stimulus("c", StimulusSeverity.NOTICE))
        self.assertTrue(result.accepted)
        self.assertEqual(result.dropped_stimulus_id, "a")
        self.assertEqual([bus.poll().stimulus_id, bus.poll().stimulus_id], ["b", "c"])

    def test_critical_evicts_noncritical_before_any_critical(self):
        bus = StimulusBus(capacity=2)
        bus.publish(make_stimulus("critical-old", StimulusSeverity.CRITICAL))
        bus.publish(make_stimulus("info-old", StimulusSeverity.INFO))
        result = bus.publish(make_stimulus("critical-new", StimulusSeverity.CRITICAL))
        self.assertTrue(result.accepted)
        self.assertEqual(result.dropped_stimulus_id, "info-old")
        self.assertEqual(
            [bus.poll().stimulus_id, bus.poll().stimulus_id],
            ["critical-old", "critical-new"],
        )

    def test_noncritical_is_rejected_when_queue_contains_only_critical(self):
        bus = StimulusBus(capacity=2)
        bus.publish(make_stimulus("c1", StimulusSeverity.CRITICAL))
        bus.publish(make_stimulus("c2", StimulusSeverity.CRITICAL))
        result = bus.publish(make_stimulus("info", StimulusSeverity.INFO))
        self.assertFalse(result.accepted)
        self.assertEqual(result.dropped_stimulus_id, "info")
        self.assertEqual(
            [bus.poll().stimulus_id, bus.poll().stimulus_id],
            ["c1", "c2"],
        )

    def test_metrics_count_pressure_decisions(self):
        bus = StimulusBus(capacity=1)
        bus.publish(make_stimulus("c1", StimulusSeverity.CRITICAL))
        bus.publish(make_stimulus("info", StimulusSeverity.INFO))
        metrics = bus.metrics()
        self.assertEqual(metrics.published, 1)
        self.assertEqual(metrics.dropped, 1)
        self.assertEqual(metrics.critical_preserved, 1)


if __name__ == "__main__":
    unittest.main()

# Spec ratchet: ObservationRuntime records unchanged snapshots here.
def _test_deduplicated_metric_can_be_recorded(self):
    bus = StimulusBus(capacity=1)
    bus.record_deduplicated()
    bus.record_deduplicated()
    self.assertEqual(bus.metrics().deduplicated, 2)

StimulusBusTests.test_deduplicated_metric_can_be_recorded = _test_deduplicated_metric_can_be_recorded
