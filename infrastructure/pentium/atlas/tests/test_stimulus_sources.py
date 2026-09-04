import dataclasses
import unittest

from infrastructure.pentium.atlas.stimulus_model import StimulusSeverity
from infrastructure.pentium.atlas.stimulus_sources import (
    CoreHealthSource,
    PentiumSelfSource,
    SourceSnapshot,
    X99StatusSource,
)


class StimulusSourceTests(unittest.TestCase):
    def test_pentium_source_reduces_heartbeat_payload(self):
        source = PentiumSelfSource(lambda: {
            "status": "healthy",
            "checks": {"agent": {"ok": True, "detail": "raw detail"}},
            "metrics": {"memory_available_mb": 700, "disk_free_percent": 55.5},
            "checked_at": "ignored",
        })
        snapshot = source.poll()
        self.assertEqual(snapshot.source, "pentium.self")
        self.assertEqual(snapshot.severity, StimulusSeverity.INFO)
        self.assertEqual(snapshot.payload["checks"], {"agent": True})
        self.assertNotIn("detail", repr(snapshot.payload))

    def test_core_source_reduces_network_contract(self):
        source = CoreHealthSource(lambda: {
            "status": "degraded",
            "nodes": [{
                "name": "core",
                "status": "degraded",
                "tailscale_online": False,
                "ipv4_matches": True,
                "ssh_reachable": False,
                "expected_ipv4": "secret-ish-noise",
            }],
        })
        snapshot = source.poll()
        self.assertEqual(snapshot.severity, StimulusSeverity.WARNING)
        self.assertEqual(snapshot.payload["status"], "degraded")
        self.assertNotIn("expected_ipv4", snapshot.payload)

    def test_x99_source_keeps_only_stable_status_fields(self):
        source = X99StatusSource(lambda: {
            "status": "degraded",
            "error": "ssh-failed",
            "detail": "raw ssh stderr should not propagate",
        })
        snapshot = source.poll()
        self.assertEqual(snapshot.source, "x99")
        self.assertEqual(snapshot.severity, StimulusSeverity.WARNING)
        self.assertEqual(snapshot.payload, {"status": "degraded", "error": "ssh-failed"})

    def test_source_snapshot_is_frozen(self):
        snapshot = SourceSnapshot(
            source="core",
            status="healthy",
            severity=StimulusSeverity.INFO,
            payload={"status": "healthy"},
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            snapshot.status = "degraded"


if __name__ == "__main__":
    unittest.main()
