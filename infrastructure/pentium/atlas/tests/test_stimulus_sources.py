import dataclasses
import unittest

from infrastructure.pentium.atlas import stimulus_sources as stimulus_sources_module
from infrastructure.pentium.atlas.network_discovery import DiscoveredNeighbor, NetworkDiscoveryError
from infrastructure.pentium.atlas.stimulus_model import StimulusSeverity
from infrastructure.pentium.atlas.stimulus_sources import (
    CoreHealthSource,
    MikroTikPerimeterSource,
    PentiumSelfSource,
    SourceSnapshot,
    X99StatusSource,
    probe_dhcp_leases,
    probe_dns_latency,
    probe_wan_traffic,
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

        self.assertEqual(len(expired.payload["devices"]), 1)
        self.assertEqual(expired.payload["devices"][0]["presence"], "missing")
        self.assertEqual(expired.payload["events"][0]["kind"], "missing")

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

    def test_probe_dns_latency_deterministic(self):
        # Mocked fast resolver
        res = probe_dns_latency(
            dns_server="1.1.1.1",
            query_domain="google.com",
            resolver_fn=lambda s, d, t: (True, 24.5, ["142.250.190.46"]),
        )
        self.assertTrue(res["success"])
        self.assertEqual(24.5, res["latency_ms"])
        self.assertEqual("HEALTHY", res["status"])
        self.assertFalse(res["high_latency"])

        # High latency test (> 150ms)
        res_slow = probe_dns_latency(
            dns_server="1.1.1.1",
            query_domain="google.com",
            resolver_fn=lambda s, d, t: (True, 195.0, ["142.250.190.46"]),
        )
        self.assertTrue(res_slow["success"])
        self.assertTrue(res_slow["high_latency"])
        self.assertEqual("DEGRADED", res_slow["status"])

        # Failure test
        res_fail = probe_dns_latency(
            dns_server="1.1.1.1",
            query_domain="google.com",
            resolver_fn=lambda s, d, t: (False, 2000.0, []),
        )
        self.assertFalse(res_fail["success"])
        self.assertEqual("DOWN", res_fail["status"])

    def test_probe_wan_traffic_deterministic(self):
        def fake_collector(host, iface):
            return {
                "link_up": True,
                "rx_bytes": 104857600,
                "tx_bytes": 52428800,
                "rx_rate_kbps": 12500.0,
                "tx_rate_kbps": 4200.0,
                "status": "UP",
            }

        res = probe_wan_traffic("192.168.88.1", "ether1", collector_fn=fake_collector)
        self.assertTrue(res["link_up"])
        self.assertEqual("UP", res["status"])
        self.assertEqual(104857600, res["rx_bytes"])
        self.assertEqual(12500.0, res["rx_rate_kbps"])

    def test_probe_dhcp_leases_deterministic(self):
        def fake_collector(host):
            return {
                "reachable": True,
                "static_count": 5,
                "dynamic_count": 12,
                "leases": [
                    {"ip": "192.168.88.10", "mac": "00:11:22:33:44:55", "hostname": "pentium", "status": "bound"},
                    {"ip": "192.168.88.11", "mac": "00:11:22:33:44:56", "hostname": "core", "status": "bound"},
                ],
            }

        res = probe_dhcp_leases("192.168.88.1", collector_fn=fake_collector)
        self.assertEqual(2, res["total_leases"])
        self.assertEqual(2, res["active_leases_count"])
        self.assertEqual(5, res["static_count"])
        self.assertEqual("HEALTHY", res["status"])

    def test_mikrotik_perimeter_source_healthy_and_degraded(self):
        # 1. Healthy perimeter
        src = MikroTikPerimeterSource(
            router_host="192.168.88.1",
            wan_interface="ether1",
            dns_target="1.1.1.1",
            wan_prober=lambda h, iface: {"status": "UP", "link_up": True, "rx_rate_kbps": 5000.0, "tx_rate_kbps": 1000.0},
            dns_prober=lambda dns, dom, to: {"status": "HEALTHY", "latency_ms": 18.0, "high_latency": False},
            dhcp_prober=lambda h: {"status": "HEALTHY", "total_leases": 10, "active_leases_count": 8},
            clock=lambda: 1726830000.0,
        )
        snap = src.poll()
        self.assertEqual("mikrotik.perimeter", snap.source)
        self.assertEqual("healthy", snap.status)
        self.assertEqual(StimulusSeverity.INFO, snap.severity)
        self.assertEqual("PERIMETER", snap.payload["zone"])
        self.assertEqual("UP", snap.payload["wan_traffic"]["status"])
        self.assertEqual(18.0, snap.payload["dns_latency"]["latency_ms"])

        # 2. Degraded due to high DNS latency
        src_slow_dns = MikroTikPerimeterSource(
            wan_prober=lambda h, iface: {"status": "UP", "link_up": True},
            dns_prober=lambda dns, dom, to: {"status": "DEGRADED", "latency_ms": 220.0, "high_latency": True},
            dhcp_prober=lambda h: {"status": "HEALTHY", "total_leases": 10, "active_leases_count": 8},
            clock=lambda: 1726830000.0,
        )
        snap_slow = src_slow_dns.poll()
        self.assertEqual("degraded", snap_slow.status)
        self.assertEqual(StimulusSeverity.WARNING, snap_slow.severity)


if __name__ == "__main__":
    unittest.main()
