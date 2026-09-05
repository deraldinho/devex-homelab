import dataclasses
import unittest

from infrastructure.pentium.atlas import stimulus_sources as stimulus_sources_module
from infrastructure.pentium.atlas.network_discovery import DiscoveredNeighbor, NetworkDiscoveryError
from infrastructure.pentium.atlas.stimulus_model import StimulusSeverity
from infrastructure.pentium.atlas.stimulus_sources import (
    CoreHealthSource,
    PentiumSelfSource,
    SourceSnapshot,
    X99StatusSource,
)


class SequenceScanner:
    def __init__(self, rounds):
        self._rounds = iter(rounds)

    def scan(self, interface):
        return next(self._rounds)


class SequenceClock:
    def __init__(self, values):
        self._values = iter(values)

    def __call__(self):
        return next(self._values)


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

    def test_pentium_source_propagates_observed_timestamp(self):
        source = PentiumSelfSource(lambda: {
            "status": "healthy",
            "checks": {},
            "metrics": {},
            "checked_at": "2026-09-04T03:10:00+00:00",
        })
        snapshot = source.poll()
        self.assertEqual(snapshot.observed_at, "2026-09-04T03:10:00+00:00")
        self.assertNotIn("checked_at", snapshot.payload)

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

    def test_required_unavailable_source_is_critical(self):
        core = CoreHealthSource(lambda: {
            "status": "unavailable",
            "nodes": [{"name": "core", "status": "unavailable"}],
        })
        x99 = X99StatusSource(lambda: {"status": "unavailable"})
        self.assertEqual(core.poll().severity, StimulusSeverity.CRITICAL)
        self.assertEqual(x99.poll().severity, StimulusSeverity.WARNING)

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


    def test_source_snapshot_exposes_observed_at(self):
        snapshot = SourceSnapshot(
            source="core",
            status="healthy",
            severity=StimulusSeverity.INFO,
            payload={"status": "healthy"},
            observed_at="2026-09-04T03:00:00+00:00",
        )
        self.assertEqual(snapshot.observed_at, "2026-09-04T03:00:00+00:00")

    def test_wifi_presence_source_keeps_device_present_across_single_empty_round(self):
        source_cls = getattr(stimulus_sources_module, "WifiPresenceSource", None)
        if source_cls is None:
            self.fail("WifiPresenceSource not implemented")
        scanner = SequenceScanner([(DiscoveredNeighbor("aa:bb:cc:dd:ee:01", "192.168.1.10"),), ()])
        source = source_cls("wlan0", scanner=scanner, clock=SequenceClock([1000.0, 1060.0]), presence_window_s=180.0)

        first = source.poll()
        second = source.poll()

        self.assertEqual(first.payload["devices"][0]["presence"], "present")
        self.assertEqual(second.payload["devices"][0]["presence"], "present")
        self.assertEqual(first.payload["devices"][0]["first_seen"], second.payload["devices"][0]["first_seen"])

    def test_wifi_presence_source_expires_device_after_presence_window(self):
        source_cls = getattr(stimulus_sources_module, "WifiPresenceSource")
        scanner = SequenceScanner([(DiscoveredNeighbor("aa:bb:cc:dd:ee:01", "192.168.1.10"),), ()])
        source = source_cls("wlan0", scanner=scanner, clock=SequenceClock([1000.0, 1181.0]), presence_window_s=180.0)

        source.poll()
        expired = source.poll()

        self.assertEqual(expired.payload["devices"], [])

    def test_wifi_presence_source_emits_sorted_bounded_zone_payload(self):
        source_cls = getattr(stimulus_sources_module, "WifiPresenceSource")
        scanner = SequenceScanner([(DiscoveredNeighbor("aa:bb:cc:dd:ee:02", "192.168.1.20"), DiscoveredNeighbor("aa:bb:cc:dd:ee:01", "192.168.1.10"))])
        source = source_cls("wlan0", scanner=scanner, clock=SequenceClock([1000.0]))

        snapshot = source.poll()

        self.assertEqual(snapshot.source, "wifi.presence")
        self.assertEqual(snapshot.status, "healthy")
        self.assertEqual(snapshot.payload.get("zone"), "WIFI_OBSERVED")
        self.assertEqual([item["mac"] for item in snapshot.payload["devices"]], ["aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:02"])
        self.assertTrue(all(item.get("zone") == "WIFI_OBSERVED" for item in snapshot.payload["devices"]))

    def test_wifi_presence_source_rejects_snapshot_above_device_bound(self):
        source_cls = getattr(stimulus_sources_module, "WifiPresenceSource")
        neighbors = tuple(DiscoveredNeighbor(f"02:00:00:00:{i // 256:02x}:{i % 256:02x}", f"192.168.{i // 254}.{(i % 254) + 1}") for i in range(257))
        source = source_cls("wlan0", scanner=SequenceScanner([neighbors]), clock=SequenceClock([1000.0]))

        with self.assertRaises(NetworkDiscoveryError):
            source.poll()

if __name__ == "__main__":
    unittest.main()
