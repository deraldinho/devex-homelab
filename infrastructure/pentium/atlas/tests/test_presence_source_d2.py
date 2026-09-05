import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.network_discovery import (
    DiscoveredNeighbor,
    NetworkDiscoveryError,
)
from infrastructure.pentium.atlas.presence_persistence import PresenceRepository
from infrastructure.pentium.atlas.presence_registry import PresenceRegistry
from infrastructure.pentium.atlas.stimulus_sources import WifiPresenceSource


class SequenceScanner:
    def __init__(self, rounds):
        self._rounds = iter(rounds)

    def scan(self, interface):
        value = next(self._rounds)
        if isinstance(value, Exception):
            raise value
        return value


class SequenceClock:
    def __init__(self, values):
        self._values = iter(values)

    def __call__(self):
        return next(self._values)


class PresenceSourceD2Tests(unittest.TestCase):
    def test_same_mac_new_ip_emits_changed_without_duplicate_identity(self):
        registry = PresenceRegistry(presence_window_s=180.0, max_devices=256)
        source = WifiPresenceSource(
            "wlan0",
            scanner=SequenceScanner([
                (DiscoveredNeighbor("aa:bb:cc:dd:ee:01", "192.168.1.10"),),
                (DiscoveredNeighbor("aa:bb:cc:dd:ee:01", "192.168.1.20"),),
            ]),
            registry=registry,
            clock=SequenceClock([1000.0, 1060.0]),
        )

        source.poll()
        changed = source.poll()

        self.assertEqual(len(changed.payload["devices"]), 1)
        self.assertEqual(changed.payload["devices"][0]["ipv4"], "192.168.1.20")
        self.assertEqual(changed.payload["events"][0]["kind"], "changed")
        self.assertEqual(changed.payload["events"][0]["changed_fields"], ["ipv4"])

    def test_missing_then_reappearing_device_emits_recovered(self):
        registry = PresenceRegistry(presence_window_s=180.0, max_devices=256)
        source = WifiPresenceSource(
            "wlan0",
            scanner=SequenceScanner([
                (DiscoveredNeighbor("aa:bb:cc:dd:ee:01", "192.168.1.10"),),
                (),
                (DiscoveredNeighbor("aa:bb:cc:dd:ee:01", "192.168.1.11"),),
            ]),
            registry=registry,
            clock=SequenceClock([1000.0, 1181.0, 1240.0]),
        )
        source.poll()
        missing = source.poll()
        recovered = source.poll()

        self.assertEqual(missing.payload["events"][0]["kind"], "missing")
        self.assertEqual(missing.payload["devices"][0]["presence"], "missing")
        self.assertEqual(recovered.payload["events"][0]["kind"], "recovered")
        self.assertEqual(recovered.payload["devices"][0]["presence"], "present")

    def test_discovery_failure_does_not_change_registry_presence(self):
        registry = PresenceRegistry(presence_window_s=180.0, max_devices=256)
        source = WifiPresenceSource(
            "wlan0",
            scanner=SequenceScanner([
                (DiscoveredNeighbor("aa:bb:cc:dd:ee:01", "192.168.1.10"),),
                NetworkDiscoveryError("arp failed"),
            ]),
            registry=registry,
            clock=SequenceClock([1000.0, 1300.0]),
        )

        source.poll()
        with self.assertRaises(NetworkDiscoveryError):
            source.poll()

        self.assertEqual(registry.devices()[0].presence, "present")
        self.assertEqual(registry.devices()[0].last_seen, 1000.0)

    def test_repository_restores_identity_across_source_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = PresenceRepository(Path(tmp) / "presence.json", max_devices=256)
            first = WifiPresenceSource(
                "wlan0",
                scanner=SequenceScanner([(DiscoveredNeighbor("aa:bb:cc:dd:ee:01", "192.168.1.10"),)]),
                repository=repo,
                clock=SequenceClock([1000.0]),
                presence_window_s=180.0,
            )
            first.poll()

            second = WifiPresenceSource(
                "wlan0",
                scanner=SequenceScanner([()]),
                repository=repo,
                clock=SequenceClock([1181.0]),
                presence_window_s=180.0,
            )
            snapshot = second.poll()

            self.assertEqual(snapshot.payload["devices"][0]["mac"], "aa:bb:cc:dd:ee:01")
            self.assertEqual(snapshot.payload["devices"][0]["presence"], "missing")
            self.assertEqual(snapshot.payload["events"][0]["kind"], "missing")


if __name__ == "__main__":
    unittest.main()
