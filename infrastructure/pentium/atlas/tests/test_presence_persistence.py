import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from infrastructure.pentium.atlas.presence_persistence import (
    PresenceRepository,
    PresenceStateInvalid,
)
from infrastructure.pentium.atlas.presence_registry import PresenceRegistry


def neighbor(mac, ipv4):
    return SimpleNamespace(mac=mac, ipv4=ipv4)


class PresencePersistenceTests(unittest.TestCase):
    def test_repository_round_trip_preserves_identity_and_missing_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "presence.json"
            repo = PresenceRepository(path, max_devices=256)
            registry = PresenceRegistry(presence_window_s=180.0, max_devices=256)
            registry.observe([neighbor("aa:bb:cc:dd:ee:01", "192.168.1.10")], 1000.0)
            registry.observe([], 1181.0)

            repo.save(registry)
            restored = repo.load(presence_window_s=180.0)

            self.assertIsNotNone(restored)
            device = restored.devices()[0]
            self.assertEqual(device.mac, "aa:bb:cc:dd:ee:01")
            self.assertEqual(device.ipv4, "192.168.1.10")
            self.assertEqual(device.first_seen, 1000.0)
            self.assertEqual(device.last_seen, 1000.0)
            self.assertEqual(device.presence, "missing")
            self.assertFalse(path.with_name(path.name + ".tmp").exists())

    def test_repository_returns_none_when_state_file_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = PresenceRepository(Path(tmp) / "missing.json", max_devices=256)

            self.assertIsNone(repo.load(presence_window_s=180.0))

    def test_repository_rejects_unknown_schema_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "presence.json"
            path.write_text(json.dumps({"schema_version": 99, "devices": []}), encoding="utf-8")
            repo = PresenceRepository(path, max_devices=256)

            with self.assertRaises(PresenceStateInvalid):
                repo.load(presence_window_s=180.0)

    def test_repository_rejects_saved_state_above_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "presence.json"
            payload = {
                "schema_version": 1,
                "devices": [
                    {
                        "mac": "aa:bb:cc:dd:ee:01",
                        "ipv4": "192.168.1.10",
                        "first_seen": 1000.0,
                        "last_seen": 1000.0,
                        "presence": "present",
                        "zone": "WIFI_OBSERVED",
                        "hostname": None,
                        "vendor": None,
                    },
                    {
                        "mac": "aa:bb:cc:dd:ee:02",
                        "ipv4": "192.168.1.20",
                        "first_seen": 1000.0,
                        "last_seen": 1000.0,
                        "presence": "present",
                        "zone": "WIFI_OBSERVED",
                        "hostname": None,
                        "vendor": None,
                    },
                ],
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            repo = PresenceRepository(path, max_devices=1)

            with self.assertRaises(PresenceStateInvalid):
                repo.load(presence_window_s=180.0)


if __name__ == "__main__":
    unittest.main()
