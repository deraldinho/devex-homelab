import unittest
from types import SimpleNamespace

from infrastructure.pentium.atlas.presence_registry import (
    PresenceRegistry,
    PresenceRegistryError,
)


def neighbor(mac, ipv4, hostname=None, vendor=None):
    return SimpleNamespace(mac=mac, ipv4=ipv4, hostname=hostname, vendor=vendor)


class PresenceRegistryTests(unittest.TestCase):
    def test_new_device_is_persisted_by_mac_and_emits_appeared(self):
        registry = PresenceRegistry(presence_window_s=180.0, max_devices=256)

        update = registry.observe(
            [neighbor("aa:bb:cc:dd:ee:01", "192.168.1.10")],
            1000.0,
        )

        self.assertEqual(len(update.devices), 1)
        self.assertEqual(update.devices[0].mac, "aa:bb:cc:dd:ee:01")
        self.assertEqual(update.devices[0].first_seen, 1000.0)
        self.assertEqual(update.devices[0].last_seen, 1000.0)
        self.assertEqual(update.devices[0].presence, "present")
        self.assertEqual([(event.kind, event.mac) for event in update.events], [("appeared", "aa:bb:cc:dd:ee:01")])

    def test_same_mac_new_ip_is_changed_not_new_entity(self):
        registry = PresenceRegistry(presence_window_s=180.0, max_devices=256)
        registry.observe([neighbor("aa:bb:cc:dd:ee:01", "192.168.1.10")], 1000.0)

        update = registry.observe(
            [neighbor("aa:bb:cc:dd:ee:01", "192.168.1.20")],
            1060.0,
        )

        self.assertEqual(len(update.devices), 1)
        self.assertEqual(update.devices[0].ipv4, "192.168.1.20")
        self.assertEqual(update.devices[0].first_seen, 1000.0)
        self.assertEqual(update.events[0].kind, "changed")
        self.assertEqual(update.events[0].changed_fields, ("ipv4",))

    def test_single_absence_keeps_device_present_without_event(self):
        registry = PresenceRegistry(presence_window_s=180.0, max_devices=256)
        registry.observe([neighbor("aa:bb:cc:dd:ee:01", "192.168.1.10")], 1000.0)

        update = registry.observe([], 1060.0)

        self.assertEqual(update.devices[0].presence, "present")
        self.assertEqual(update.devices[0].last_seen, 1000.0)
        self.assertEqual(update.events, ())

    def test_expiration_marks_missing_but_keeps_identity(self):
        registry = PresenceRegistry(presence_window_s=180.0, max_devices=256)
        registry.observe([neighbor("aa:bb:cc:dd:ee:01", "192.168.1.10")], 1000.0)
        update = registry.observe([], 1181.0)

        self.assertEqual(len(update.devices), 1)
        self.assertEqual(update.devices[0].presence, "missing")
        self.assertEqual([(event.kind, event.mac) for event in update.events], [("missing", "aa:bb:cc:dd:ee:01")])

    def test_missing_device_reappears_as_recovered(self):
        registry = PresenceRegistry(presence_window_s=180.0, max_devices=256)
        registry.observe([neighbor("aa:bb:cc:dd:ee:01", "192.168.1.10")], 1000.0)
        registry.observe([], 1181.0)

        update = registry.observe(
            [neighbor("aa:bb:cc:dd:ee:01", "192.168.1.11")],
            1240.0,
        )

        self.assertEqual(len(update.devices), 1)
        self.assertEqual(update.devices[0].presence, "present")
        self.assertEqual(update.devices[0].ipv4, "192.168.1.11")
        self.assertEqual([(event.kind, event.mac) for event in update.events], [("recovered", "aa:bb:cc:dd:ee:01")])

    def test_hostname_and_vendor_changes_are_reported_without_new_identity(self):
        registry = PresenceRegistry(presence_window_s=180.0, max_devices=256)
        registry.observe([neighbor("aa:bb:cc:dd:ee:01", "192.168.1.10")], 1000.0)

        update = registry.observe(
            [neighbor("aa:bb:cc:dd:ee:01", "192.168.1.10", "phone", "Acme")],
            1060.0,
        )
        self.assertEqual(len(update.devices), 1)
        self.assertEqual(update.devices[0].hostname, "phone")
        self.assertEqual(update.devices[0].vendor, "Acme")
        self.assertEqual(update.events[0].kind, "changed")
        self.assertEqual(update.events[0].changed_fields, ("hostname", "vendor"))

    def test_registry_rejects_new_identity_above_bound_without_partial_mutation(self):
        registry = PresenceRegistry(presence_window_s=180.0, max_devices=1)
        registry.observe([neighbor("aa:bb:cc:dd:ee:01", "192.168.1.10")], 1000.0)

        with self.assertRaises(PresenceRegistryError):
            registry.observe(
                [
                    neighbor("aa:bb:cc:dd:ee:01", "192.168.1.10"),
                    neighbor("aa:bb:cc:dd:ee:02", "192.168.1.20"),
                ],
                1060.0,
            )

        self.assertEqual(len(registry.devices()), 1)
        self.assertEqual(registry.devices()[0].mac, "aa:bb:cc:dd:ee:01")


if __name__ == "__main__":
    unittest.main()
