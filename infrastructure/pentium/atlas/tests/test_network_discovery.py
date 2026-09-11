import importlib
import ipaddress
import unittest
from unittest import mock
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

    def test_default_neighbor_prober_is_bounded_to_direct_network(self):
        module = discovery_module()
        sent = []

        class FakeSocket:
            def bind(self, address):
                self.bound = address
            def setblocking(self, value):
                self.blocking = value
            def sendto(self, payload, target):
                sent.append((payload, target))
            def close(self):
                self.closed = True

        fake = FakeSocket()
        scoped = module.InterfaceNetwork(
            "wlan0", ipaddress.IPv4Address("192.168.1.2"), ipaddress.IPv4Network("192.168.1.0/30")
        )
        with mock.patch.object(module.socket, "socket", return_value=fake), mock.patch.object(module.time, "sleep"):
            module._prime_neighbor_table(scoped, 1.0)

        self.assertEqual(fake.bound, ("192.168.1.2", 0))
        self.assertEqual(sent, [(b"\x00", ("192.168.1.1", 9))])
        self.assertTrue(fake.closed)
    def test_scanner_falls_back_to_bounded_neighbor_table_without_arp_scan(self):
        module = discovery_module()
        calls = []
        probes = []

        def runner(argv, timeout_s):
            calls.append((tuple(argv), timeout_s))
            if tuple(argv[:5]) == ("ip", "-json", "-4", "addr", "show"):
                return SimpleNamespace(returncode=0, stdout=DEFAULT_INTERFACE_JSON, stderr="")
            if argv[0] == "arp-scan":
                raise FileNotFoundError("arp-scan")
            if tuple(argv) == ("ip", "-json", "neigh", "show", "dev", "wlan0"):
                payload = '[{"dst":"192.168.1.10","lladdr":"aa:bb:cc:dd:ee:01","state":["STALE"]},{"dst":"192.168.1.11","state":["FAILED"]}]'
                return SimpleNamespace(returncode=0, stdout=payload, stderr="")
            raise AssertionError(f"unexpected command: {argv}")

        def prober(scoped, timeout_s):
            probes.append((scoped.interface, str(scoped.address), str(scoped.network), timeout_s))

        scanner = module.LinuxArpScanner(runner=runner, neighbor_prober=prober, timeout_s=5.0)
        discovered = scanner.scan("wlan0")

        self.assertEqual(probes, [("wlan0", "192.168.1.8", "192.168.1.0/24", 5.0)])
        self.assertEqual([(item.mac, item.ipv4) for item in discovered], [("aa:bb:cc:dd:ee:01", "192.168.1.10")])
        self.assertIn((("ip", "-json", "neigh", "show", "dev", "wlan0"), 5.0), calls)
    def test_scanner_accepts_only_valid_unicast_mac_addresses(self):
        module = discovery_module()
        runner = RecordingRunner(scan_stdout=("192.168.1.10\taa:bb:cc:dd:ee:01\n" "192.168.1.11\t01:00:5e:00:00:01\n" "192.168.1.12\tnot-a-mac\n"))

        discovered = module.LinuxArpScanner(runner=runner).scan("wlan0")

        self.assertEqual([(item.mac, item.ipv4) for item in discovered], [("aa:bb:cc:dd:ee:01", "192.168.1.10")])


if __name__ == "__main__":
    unittest.main()
