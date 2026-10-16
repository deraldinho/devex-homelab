"""Opt-in shadow Sentry recorder attached to existing health supervisor."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from infrastructure.pentium.atlas.failure_memory import FailureMemory
from infrastructure.pentium.atlas.health_probes import ProbeResult
from infrastructure.pentium.atlas.health_supervisor import AtlasHealthSupervisor, HealthSnapshotPublisher
from infrastructure.pentium.atlas.health_supervisor_daemon import HealthSupervisorOwner, ServiceProbeBundle
from infrastructure.pentium.atlas.health_supervisor_model import ComponentHealthState as State


BASE = datetime(2026, 10, 16, 13, tzinfo=timezone.utc)


class MutableProbe:
    def __init__(self):
        self.state = State.FAILED

    def probe(self):
        return ProbeResult(
            self.state == State.HEALTHY, self.state, BASE.isoformat(),
            self.state.value, ("probe:authenticated",), {},
        )


class FailingSink:
    def observe_snapshot(self, _):
        raise OSError("sensitive incident payload must not leak")


class FailureMemorySupervisorTests(unittest.TestCase):
    def test_opt_in_sink_records_without_mutating_ordinary_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            probe = MutableProbe()
            sink = FailureMemory(root / "failures.sqlite3")
            try:
                times = iter(BASE + timedelta(minutes=i) for i in range(4))
                owner = HealthSupervisorOwner(
                    AtlasHealthSupervisor(),
                    HealthSnapshotPublisher(root / "health.json", root / "events.jsonl"),
                    (ServiceProbeBundle("atlas-cognitive.service", "pentium",
                                        "running", True, probe, probe),),
                    poll_interval_s=15, now=lambda: next(times),
                    failure_memory=sink,
                )
                self.assertEqual(owner.run_once().state, State.FAILED)
                self.assertEqual(sink.stats()["open_incidents"], 1)
                probe.state = State.HEALTHY
                owner.run_once()
                self.assertEqual(sink.stats()["open_incidents"], 1)
                owner.run_once()
                self.assertEqual(sink.stats()["recovered_incidents"], 1)
                self.assertEqual(sink.stats()["lessons"], 0)
                self.assertIsNone(owner.last_failure_memory_error)
                self.assertEqual(json.loads((root / "health.json").read_text())["state"], "healthy")
            finally:
                sink.close()

    def test_failure_memory_exception_does_not_break_supervisor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            probe = MutableProbe()
            owner = HealthSupervisorOwner(
                AtlasHealthSupervisor(),
                HealthSnapshotPublisher(root / "health.json", root / "events.jsonl"),
                (ServiceProbeBundle("atlas-cognitive.service", "pentium",
                                    "running", True, probe, probe),),
                poll_interval_s=15, now=lambda: BASE,
                failure_memory=FailingSink(),
            )
            self.assertEqual(owner.run_once().state, State.FAILED)
            self.assertEqual(owner.last_failure_memory_error, "OSError")
            self.assertTrue((root / "health.json").exists())

    def test_disabled_default_does_not_create_failure_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            probe = MutableProbe()
            owner = HealthSupervisorOwner(
                AtlasHealthSupervisor(),
                HealthSnapshotPublisher(root / "health.json", root / "events.jsonl"),
                (ServiceProbeBundle("atlas-cognitive.service", "pentium",
                                    "running", True, probe, probe),),
                poll_interval_s=15, now=lambda: BASE,
            )
            owner.run_once()
            self.assertFalse((root / "failures.sqlite3").exists())
            self.assertIsNone(owner.last_failure_memory_error)


if __name__ == "__main__":
    unittest.main()
