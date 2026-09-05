import importlib
import unittest
from types import SimpleNamespace


DEFAULT_INTERFACE_JSON = (
    '[{"ifname":"wlan0","addr_info":'
    '[{"family":"inet","local":"192.168.1.8","prefixlen":24}]}]'
)


class RecordingRunner:
    def __init__(self, *, interface_json=DEFAULT_INTERFACE_JSON, scan_stdout=None):
        self.calls = []
        self.interface_json = interface_json
        self.scan_stdout = scan_stdout or "192.168.1.10\taa:bb:cc:dd:ee:01\n"

    def __call__(self, argv, timeout_s):
        self.calls.append((tuple(argv), timeout_s))
        if argv[0] == "ip":
            return SimpleNamespace(returncode=0, stdout=self.interface_json, stderr="")
        return SimpleNamespace(returncode=0, stdout=self.scan_stdout, stderr="")


def discovery_module():
    try:
        return importlib.import_module("infrastructure.pentium.atlas.network_discovery")
    except ModuleNotFoundError as exc:
        raise AssertionError(f"network discovery feature missing: {exc}") from exc


class NetworkDiscoveryTests(unittest.TestCase):
    def test_scanner_restricts_arp_scan_to_configured_interface_and_direct_cidr(self):
        module = discovery_module()
        runner = RecordingRunner()
        scanner = module.LinuxArpScanner(runner=runner, timeout_s=5.0)

        discovered = scanner.scan("wlan0")

        self.assertEqual(len(runner.calls), 2)
        scan_argv, timeout_s = runner.calls[1]
        self.assertIn("--interface=wlan0", scan_argv)
        self.assertIn("--plain", scan_argv)
        self.assertIn("--ignoredups", scan_argv)
        self.assertIn("--retry=1", scan_argv)
        self.assertEqual(scan_argv[-1], "192.168.1.0/24")
        self.assertEqual(timeout_s, 5.0)
        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0].mac, "aa:bb:cc:dd:ee:01")
        self.assertEqual(discovered[0].ipv4, "192.168.1.10")

    def test_scanner_ignores_neighbors_outside_directly_connected_network(self):
        module = discovery_module()
        runner = RecordingRunner(
            scan_stdout=(
                "192.168.1.10\taa:bb:cc:dd:ee:01\n"
                "10.0.0.20\taa:bb:cc:dd:ee:02\n"
            )
        )
        discovered = module.LinuxArpScanner(runner=runner).scan("wlan0")

        self.assertEqual(
            [(item.mac, item.ipv4) for item in discovered],
            [("aa:bb:cc:dd:ee:01", "192.168.1.10")],
        )

    def test_scanner_rejects_direct_network_larger_than_bound(self):
        module = discovery_module()
        runner = RecordingRunner(interface_json='[{"ifname":"wlan0","addr_info":[{"family":"inet","local":"192.168.0.8","prefixlen":22}]}]')
        scanner = module.LinuxArpScanner(runner=runner)

        with self.assertRaises(module.NetworkDiscoveryError):
            scanner.scan("wlan0")

        self.assertEqual(len(runner.calls), 1)

    def test_scanner_rejects_interface_with_multiple_ipv4_addresses(self):
        module = discovery_module()
        runner = RecordingRunner(interface_json='[{"ifname":"wlan0","addr_info":[{"family":"inet","local":"192.168.1.8","prefixlen":24},{"family":"inet","local":"192.168.2.8","prefixlen":24}]}]')
        scanner = module.LinuxArpScanner(runner=runner)

        with self.assertRaises(module.NetworkDiscoveryError):
            scanner.scan("wlan0")

        self.assertEqual(len(runner.calls), 1)

    def test_scanner_rejects_device_count_above_bound(self):
        module = discovery_module()
        rows = []
        for i in range(257):
            ipv4 = f"192.168.{i // 254}.{(i % 254) + 1}"
            mac = f"02:00:00:00:{i // 256:02x}:{i % 256:02x}"
            rows.append(f"{ipv4}\t{mac}\n")
        interface_json = '[{"ifname":"wlan0","addr_info":[{"family":"inet","local":"192.168.0.8","prefixlen":23}]}]'
        runner = RecordingRunner(interface_json=interface_json, scan_stdout="".join(rows))
        scanner = module.LinuxArpScanner(runner=runner)

        with self.assertRaises(module.NetworkDiscoveryError):
            scanner.scan("wlan0")

    def test_scanner_accepts_only_valid_unicast_mac_addresses(self):
        module = discovery_module()
        runner = RecordingRunner(scan_stdout=("192.168.1.10\taa:bb:cc:dd:ee:01\n" "192.168.1.11\t01:00:5e:00:00:01\n" "192.168.1.12\tnot-a-mac\n"))

        discovered = module.LinuxArpScanner(runner=runner).scan("wlan0")

        self.assertEqual([(item.mac, item.ipv4) for item in discovered], [("aa:bb:cc:dd:ee:01", "192.168.1.10")])


if __name__ == "__main__":
    unittest.main()
