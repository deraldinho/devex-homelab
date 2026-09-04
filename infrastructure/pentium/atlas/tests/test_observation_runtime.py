import itertools
import unittest

from infrastructure.pentium.atlas.observation_runtime import ObservationRuntime
from infrastructure.pentium.atlas.stimulus_bus import StimulusBus
from infrastructure.pentium.atlas.stimulus_model import StimulusSeverity
from infrastructure.pentium.atlas.stimulus_sources import SourceSnapshot


class FakeClock:
    def __init__(self, value: float = 0.0):
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class SequenceSource:
    def __init__(self, name, items):
        self.name = name
        self._items = iter(items)

    def poll(self):
        item = next(self._items)
        if isinstance(item, BaseException):
            raise item
        return item


def snapshot(status="healthy", value=1):
    severity = StimulusSeverity.INFO if status == "healthy" else StimulusSeverity.WARNING
    return SourceSnapshot("core", status, severity, {"status": status, "value": value})


def runtime_for(source, *, clock=None, journal=None):
    ids = itertools.count()
    bus = StimulusBus(capacity=16)
    runtime = ObservationRuntime(
        sources=[source],
        bus=bus,
        journal=journal or (lambda stimulus: None),
        clock=clock or FakeClock(),
        id_factory=lambda: f"id-{next(ids)}",
        failure_cooldown_seconds=60.0,
    )
    return runtime, bus


class ObservationRuntimeTests(unittest.TestCase):
    def test_baseline_is_emitted_once_and_unchanged_snapshot_is_deduplicated(self):
        source = SequenceSource("core", [snapshot(), snapshot()])
        runtime, bus = runtime_for(source)
        first = runtime.run_once("core")
        second = runtime.run_once("core")
        self.assertEqual(first.kind, "baseline_observed")
        self.assertIsNone(second)
        self.assertEqual(bus.metrics().deduplicated, 1)
        self.assertEqual(bus.poll().stimulus_id, first.stimulus_id)
        self.assertIsNone(bus.poll())

    def test_degraded_then_healthy_emits_recovery_with_same_correlation(self):
        source = SequenceSource(
            "core",
            [snapshot("healthy", 1), snapshot("degraded", 2), snapshot("healthy", 1)],
        )
        runtime, _ = runtime_for(source)
        baseline = runtime.run_once("core")
        degraded = runtime.run_once("core")
        recovered = runtime.run_once("core")
        self.assertEqual(baseline.kind, "baseline_observed")
        self.assertEqual(degraded.kind, "status_changed")
        self.assertEqual(recovered.kind, "recovered")
        self.assertEqual(degraded.correlation_id, recovered.correlation_id)
        self.assertEqual(recovered.severity, StimulusSeverity.NOTICE)

    def test_novelty_decays_when_known_fingerprint_returns(self):
        source = SequenceSource(
            "core",
            [snapshot("healthy", 1), snapshot("degraded", 2), snapshot("healthy", 1)],
        )
        runtime, _ = runtime_for(source)
        self.assertEqual(runtime.run_once("core").novelty, 1.0)
        self.assertEqual(runtime.run_once("core").novelty, 1.0)
        self.assertEqual(runtime.run_once("core").novelty, 0.5)

    def test_repeated_identical_source_failure_is_suppressed_during_cooldown(self):
        clock = FakeClock(1000.0)
        source = SequenceSource(
            "core",
            [TimeoutError("secret one"), TimeoutError("secret two"), TimeoutError("secret three")],
        )
        runtime, bus = runtime_for(source, clock=clock)
        first = runtime.run_once("core")
        clock.advance(10.0)
        second = runtime.run_once("core")
        clock.advance(61.0)
        third = runtime.run_once("core")
        self.assertEqual(first.kind, "source_error")
        self.assertIsNone(second)
        self.assertEqual(third.kind, "source_error")
        self.assertEqual(first.correlation_id, third.correlation_id)
        self.assertEqual(third.novelty, 0.5)
        self.assertEqual(bus.metrics().deduplicated, 1)
        self.assertNotIn("secret", repr(first.payload))

    def test_journal_failure_does_not_block_bus_or_advance_twice(self):
        source = SequenceSource("core", [snapshot(), snapshot()])
        calls = []

        def failing_journal(stimulus):
            calls.append(stimulus.stimulus_id)
            raise OSError("disk unavailable")

        runtime, bus = runtime_for(source, journal=failing_journal)
        first = runtime.run_once("core")
        second = runtime.run_once("core")
        self.assertIsNone(second)
        self.assertEqual(bus.poll().stimulus_id, first.stimulus_id)
        self.assertEqual(len(calls), 1)
        self.assertTrue(any("journal" in item for item in runtime.errors()))


if __name__ == "__main__":
    unittest.main()
