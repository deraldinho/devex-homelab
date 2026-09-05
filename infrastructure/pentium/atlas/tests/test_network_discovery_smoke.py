import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from infrastructure.pentium.atlas.network_discovery import DiscoveredNeighbor


class FakeScanner:
    def scan(self, interface):
        self.interface = interface
        return (
            DiscoveredNeighbor("aa:bb:cc:dd:ee:01", "192.168.1.10"),
            DiscoveredNeighbor("aa:bb:cc:dd:ee:02", "192.168.1.20"),
        )


class NetworkDiscoverySmokeTests(unittest.TestCase):
    def test_smoke_uses_interface_env_and_emits_bounded_json(self):
        try:
            from infrastructure.pentium.atlas import network_discovery_smoke as smoke
        except ImportError as exc:
            self.fail(f"smoke D1 missing: {exc}")

        scanner = FakeScanner()
        output = StringIO()
        previous = os.environ.get("ATLAS_WIFI_INTERFACE")
        os.environ["ATLAS_WIFI_INTERFACE"] = "wlan0"
        try:
            with redirect_stdout(output):
                rc = smoke.main([], scanner=scanner)
        finally:
            if previous is None:
                os.environ.pop("ATLAS_WIFI_INTERFACE", None)
            else:
                os.environ["ATLAS_WIFI_INTERFACE"] = previous
        self.assertEqual(rc, 0)
        self.assertEqual(scanner.interface, "wlan0")
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["zone"], "WIFI_OBSERVED")
        self.assertEqual(payload["interface"], "wlan0")
        self.assertEqual(payload["device_count"], 2)
        self.assertEqual(len(payload["devices"]), 2)
        self.assertEqual(
            set(payload["devices"][0]),
            {"mac", "ipv4"},
        )

    def test_smoke_refuses_to_run_without_interface_contract(self):
        from infrastructure.pentium.atlas import network_discovery_smoke as smoke

        previous = os.environ.pop("ATLAS_WIFI_INTERFACE", None)
        try:
            with redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit):
                    smoke.main([], scanner=FakeScanner())
        finally:
            if previous is not None:
                os.environ["ATLAS_WIFI_INTERFACE"] = previous


if __name__ == "__main__":
    unittest.main()
