import unittest
from infrastructure.pentium.atlas.observation_runtime import ObservationRuntime, SourceSchedule
from infrastructure.pentium.atlas.stimulus_bus import StimulusBus

class TestObservationBackoffOverflow(unittest.TestCase):
    def test_backoff_handles_3000_consecutive_failures_without_overflow(self):
        clock_val = 100.0
        def fake_clock():
            return clock_val

        class FakeSource:
            name = "test_src"
            def poll(self):
                raise RuntimeError("failure")

        schedule = {
            "test_src": SourceSchedule(
                interval_seconds=10.0,
                timeout_seconds=2.0,
                max_backoff_seconds=300.0,
                jitter_seconds=0.0
            )
        }

        bus = StimulusBus(capacity=16)
        runtime = ObservationRuntime(
            sources=[FakeSource()],
            schedule=schedule,
            bus=bus,
            journal=lambda s: None,
            monotonic_clock=fake_clock
        )

        # Simular 3000 falhas consecutivas acumuladas
        runtime._consecutive_failures["test_src"] = 3000
        # Força o source a estar due
        runtime._next_due["test_src"] = 90.0

        # Não deve lançar OverflowError: int too large to convert to float
        delay = runtime.run_scheduled_cycle()
        self.assertLessEqual(delay, 300.0)
        self.assertEqual(3001, runtime._consecutive_failures["test_src"])

if __name__ == "__main__":
    unittest.main()
