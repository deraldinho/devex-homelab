import itertools
import unittest

from infrastructure.pentium.atlas.observation_runtime import ObservationRuntime
from infrastructure.pentium.atlas.stimulus_bus import StimulusBus
from infrastructure.pentium.atlas.stimulus_model import StimulusSeverity
from infrastructure.pentium.atlas.network_discovery import DiscoveredNeighbor
from infrastructure.pentium.atlas.stimulus_sources import SourceSnapshot, WifiPresenceSource


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

    def test_wifi_presence_last_seen_change_is_deduplicated_when_devices_are_unchanged(self):
        class SameNeighborScanner:
            def scan(self, interface):
                return (DiscoveredNeighbor("aa:bb:cc:dd:ee:01", "192.168.1.10"),)

        times = iter([1000.0, 1060.0])
        source = WifiPresenceSource("wlan0", scanner=SameNeighborScanner(), clock=lambda: next(times))
        runtime, bus = runtime_for(source)

        first = runtime.run_once("wifi.presence")
        second = runtime.run_once("wifi.presence")

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(bus.metrics().deduplicated, 1)

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

    def test_snapshot_observed_at_becomes_stimulus_timestamp(self):
        observed_at = "2026-09-04T03:20:00+00:00"
        source = SequenceSource(
            "core",
            [SourceSnapshot(
                "core",
                "healthy",
                StimulusSeverity.INFO,
                {"status": "healthy"},
                observed_at,
            )],
        )
        runtime, _ = runtime_for(source, clock=FakeClock(1000.0))
        stimulus = runtime.run_once("core")
        self.assertEqual(stimulus.timestamp, observed_at)

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

    def test_required_source_poll_failure_is_critical(self):
        class RequiredFailingSource:
            name = "core"
            required = True

            def poll(self):
                raise TimeoutError("unavailable")

        runtime, _ = runtime_for(RequiredFailingSource())
        stimulus = runtime.run_once("core")
        self.assertEqual(stimulus.kind, "source_error")
        self.assertEqual(stimulus.severity, StimulusSeverity.CRITICAL)

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


from infrastructure.pentium.atlas.observation_runtime import (
    SourcePolicy,
    SourceSchedule,
    load_observation_config,
    load_observation_policies,
)


class RepeatingSource:
    def __init__(self, name, result):
        self.name = name
        self.result = result
        self.calls = 0

    def poll(self):
        self.calls += 1
        return self.result


class FakeStopEvent:
    def __init__(self, stopped=False):
        self.stopped = stopped

    def is_set(self):
        return self.stopped

    def set(self):
        self.stopped = True


class ObservationSchedulingTests(unittest.TestCase):
    def test_source_policy_contract_matches_plan(self):
        policy = SourcePolicy(10.0, 0.5, 40.0, 15.0)
        self.assertEqual(policy.interval_s, 10.0)
        self.assertEqual(policy.timeout_s, 0.5)
        self.assertEqual(policy.max_backoff_s, 40.0)
        self.assertEqual(policy.cooldown_s, 15.0)

    def test_source_policy_applies_per_source_failure_cooldown(self):
        clock = FakeClock(1000.0)
        source = SequenceSource(
            "core",
            [TimeoutError("one"), TimeoutError("two"), TimeoutError("three")],
        )
        bus = StimulusBus(capacity=16)
        runtime = ObservationRuntime(
            sources=[source],
            bus=bus,
            journal=lambda stimulus: None,
            clock=clock,
            poll_runner=lambda item, timeout: item.poll(),
            policies={"core": SourcePolicy(10.0, 0.5, 40.0, 5.0)},
        )
        first = runtime.run_once("core")
        clock.advance(4.0)
        second = runtime.run_once("core")
        clock.advance(2.0)
        third = runtime.run_once("core")
        self.assertEqual(first.kind, "source_error")
        self.assertIsNone(second)
        self.assertEqual(third.kind, "source_error")
        self.assertEqual(bus.metrics().deduplicated, 1)

    def test_cycle_isolates_timeout_and_passes_source_timeout(self):
        clock = FakeClock(0.0)
        slow = RepeatingSource("slow", snapshot())
        fast = RepeatingSource("fast", snapshot())
        calls = []

        def runner(source, timeout):
            calls.append((source.name, timeout))
            if source.name == "slow":
                raise TimeoutError("bounded")
            return source.poll()
        runtime = ObservationRuntime(
            sources=[slow, fast],
            bus=StimulusBus(capacity=16),
            journal=lambda stimulus: None,
            clock=clock,
            monotonic_clock=clock,
            poll_runner=runner,
            schedule={
                "slow": SourceSchedule(10.0, 0.5, 40.0),
                "fast": SourceSchedule(10.0, 0.25, 40.0),
            },
        )
        next_sleep = runtime.run_scheduled_cycle()
        self.assertEqual(calls, [("slow", 0.5), ("fast", 0.25)])
        self.assertEqual(fast.calls, 1)
        self.assertEqual(next_sleep, 10.0)

    def test_failure_backoff_is_exponential_and_capped(self):
        clock = FakeClock(0.0)
        source = RepeatingSource("slow", snapshot())

        def runner(source, timeout):
            raise TimeoutError("bounded")

        runtime = ObservationRuntime(
            sources=[source],
            bus=StimulusBus(capacity=16),
            journal=lambda stimulus: None,
            clock=clock,
            monotonic_clock=clock,
            poll_runner=runner,
            schedule={"slow": SourceSchedule(10.0, 0.5, 25.0)},
        )
        self.assertEqual(runtime.run_scheduled_cycle(), 20.0)
        clock.advance(20.0)
        self.assertEqual(runtime.run_scheduled_cycle(), 25.0)
        clock.advance(25.0)
        self.assertEqual(runtime.run_scheduled_cycle(), 25.0)

    def test_run_forever_sleeps_positive_delay_and_stops_cleanly(self):
        clock = FakeClock(0.0)
        source = RepeatingSource("core", snapshot())
        stop = FakeStopEvent()
        sleeps = []

        def sleeper(seconds):
            sleeps.append(seconds)
            stop.set()

        runtime = ObservationRuntime(
            sources=[source],
            bus=StimulusBus(capacity=16),
            journal=lambda stimulus: None,
            clock=clock,
            monotonic_clock=clock,
            sleeper=sleeper,
            poll_runner=lambda source, timeout: source.poll(),
            schedule={"core": SourceSchedule(5.0, 0.5, 20.0)},
        )
        runtime.run_forever(stop)
        self.assertEqual(source.calls, 1)
        self.assertEqual(sleeps, [5.0])

    def test_run_forever_does_nothing_when_already_stopped(self):
        source = RepeatingSource("core", snapshot())
        runtime = ObservationRuntime(
            sources=[source],
            bus=StimulusBus(capacity=16),
            journal=lambda stimulus: None,
            schedule={"core": SourceSchedule(5.0, 0.5, 20.0)},
        )
        runtime.run_forever(FakeStopEvent(stopped=True))
        self.assertEqual(source.calls, 0)

    def test_load_observation_config_validates_schedule_contract(self):
        import json
        import tempfile
        from pathlib import Path

        payload = {
            "schema_version": 1,
            "sources": {
                "core": {
                    "interval_seconds": 10,
                    "timeout_seconds": 2,
                    "max_backoff_seconds": 40,
                    "jitter_seconds": 0,
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observation.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_observation_config(path)
        self.assertEqual(loaded["core"], SourceSchedule(10.0, 2.0, 40.0, 0.0))

        payload["sources"]["core"]["interval_seconds"] = 0
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observation.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_observation_config(path)

    def test_repository_config_exposes_per_source_policies(self):
        from pathlib import Path

        config_path = Path(__file__).resolve().parents[1] / "observation_config.json"
        policies = load_observation_policies(config_path)
        self.assertEqual(set(policies), {"pentium.self", "core", "x99", "managed.x99", "wifi.presence"})
        self.assertEqual(policies["pentium.self"].cooldown_s, 60.0)
        self.assertEqual(policies["core"].cooldown_s, 60.0)
        self.assertEqual(policies["x99"].cooldown_s, 60.0)
        self.assertEqual(policies["wifi.presence"].cooldown_s, 60.0)

    def test_repository_observation_config_covers_initial_sources(self):
        from pathlib import Path

        config_path = Path(__file__).resolve().parents[1] / "observation_config.json"
        schedules = load_observation_config(config_path)
        self.assertEqual(set(schedules), {"pentium.self", "core", "x99", "managed.x99", "wifi.presence"})
        self.assertLessEqual(schedules["pentium.self"].timeout_seconds, 5.0)
        self.assertLessEqual(schedules["core"].timeout_seconds, 8.0)
        self.assertLessEqual(schedules["x99"].timeout_seconds, 8.0)
        self.assertEqual(schedules["wifi.presence"].interval_seconds, 60.0)
        self.assertLessEqual(schedules["wifi.presence"].timeout_seconds, 10.0)
        self.assertEqual(schedules["wifi.presence"].jitter_seconds, 5.0)

    def test_repository_config_declares_wifi_interface_contract_and_bounds(self):
        import json
        from pathlib import Path

        config_path = Path(__file__).resolve().parents[1] / "observation_config.json"
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        wifi = payload["sources"].get("wifi.presence", {})
        self.assertEqual(wifi.get("interface_env"), "ATLAS_WIFI_INTERFACE")
        self.assertEqual(wifi.get("presence_window_seconds"), 180)
        self.assertEqual(wifi.get("max_devices"), 256)

    def test_timeout_does_not_start_overlapping_poll_for_same_source(self):
        import threading

        release = threading.Event()

        class BlockingSource:
            name = "core"

            def __init__(self):
                self.calls = 0

            def poll(self):
                self.calls += 1
                release.wait(1.0)
                return snapshot()

        source = BlockingSource()
        runtime = ObservationRuntime(
            sources=[source],
            bus=StimulusBus(capacity=16),
            journal=lambda stimulus: None,
            schedule={"core": SourceSchedule(1.0, 0.01, 4.0)},
        )
        try:
            runtime.run_once("core")
            runtime.run_once("core")
            self.assertEqual(source.calls, 1)
        finally:
            release.set()
