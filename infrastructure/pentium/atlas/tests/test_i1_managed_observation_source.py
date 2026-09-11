import unittest

from infrastructure.pentium.atlas.stimulus_sources import ManagedObservationSource


class FakeReader:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def read(self, host_id, operation):
        self.calls.append((host_id, operation))
        value = self.results[operation]
        if isinstance(value, Exception):
            raise value
        return value


class ManagedObservationSourceTests(unittest.TestCase):
    def test_healthy_reads_become_managed_snapshot(self):
        reader = FakeReader({
            "uptime": {"status": "healthy", "uptime_seconds": 123},
            "memory": {"status": "healthy", "memory": {"available_bytes": 10}},
        })
        source = ManagedObservationSource("x99", reader, operations=("uptime", "memory"))
        snapshot = source.poll()
        self.assertEqual(snapshot.source, "managed.x99")
        self.assertEqual(snapshot.status, "healthy")
        self.assertEqual(snapshot.payload["zone"], "MANAGED")
        self.assertEqual(snapshot.payload["host_id"], "x99")
        self.assertEqual(set(snapshot.payload["reads"]), {"uptime", "memory"})

    def test_degraded_read_is_channel_evidence_not_host_offline(self):
        reader = FakeReader({
            "uptime": {"status": "degraded", "error": "ssh-failed"},
            "memory": {"status": "healthy", "memory": {"available_bytes": 10}},
        })
        source = ManagedObservationSource("x99", reader, operations=("uptime", "memory"))
        snapshot = source.poll()
        self.assertEqual(snapshot.status, "degraded")
        self.assertEqual(snapshot.payload["channel_status"], "degraded")
        self.assertNotIn("offline", snapshot.payload)

    def test_source_exposes_no_control_or_shell_surface(self):
        source = ManagedObservationSource("x99", FakeReader({"uptime": {"status": "healthy"}}), operations=("uptime",))
        self.assertFalse(hasattr(source, "control"))
        self.assertFalse(hasattr(source, "execute"))
        self.assertFalse(hasattr(source, "run_shell"))


if __name__ == "__main__":
    unittest.main()
