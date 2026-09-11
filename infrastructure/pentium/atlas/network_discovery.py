from __future__ import annotations

import ipaddress
import json
import re
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence


_MAC_RE = re.compile(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$")


def _normalize_mac(value: str) -> str | None:
    candidate = value.strip().lower()
    if not _MAC_RE.fullmatch(candidate):
        return None
    if int(candidate[:2], 16) & 1:
        return None
    if candidate in {"00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"}:
        return None
    return candidate


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


CommandRunner = Callable[[Sequence[str], float], CommandResult]


class NetworkDiscoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class InterfaceNetwork:
    interface: str
    address: ipaddress.IPv4Address
    network: ipaddress.IPv4Network


@dataclass(frozen=True)
class DiscoveredNeighbor:
    mac: str
    ipv4: str


NeighborProber = Callable[[InterfaceNetwork, float], None]


def _prime_neighbor_table(scoped: InterfaceNetwork, timeout_s: float) -> None:
    """Trigger bounded L2 neighbor resolution without requiring raw-socket privilege."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((str(scoped.address), 0))
        sock.setblocking(False)
        for address in scoped.network.hosts():
            if address == scoped.address:
                continue
            try:
                sock.sendto(b"\x00", (str(address), 9))
            except OSError:
                continue
    finally:
        sock.close()
    time.sleep(min(0.25, max(0.05, timeout_s / 10.0)))


def _run_command(argv: Sequence[str], timeout_s: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )


class LinuxArpScanner:
    def __init__(
        self,
        *,
        runner: CommandRunner = _run_command,
        timeout_s: float = 10.0,
        max_addresses: int = 512,
        max_devices: int = 256,
        neighbor_prober: NeighborProber = _prime_neighbor_table,
    ):
        self._runner = runner
        self._timeout_s = timeout_s
        self._max_addresses = max_addresses
        self._max_devices = max_devices
        self._neighbor_prober = neighbor_prober

    def _interface_network(self, interface: str) -> InterfaceNetwork:
        result = self._runner(
            ["ip", "-json", "-4", "addr", "show", "dev", interface],
            self._timeout_s,
        )
        if result.returncode != 0:
            raise NetworkDiscoveryError("failed to read interface IPv4 configuration")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise NetworkDiscoveryError("invalid iproute2 JSON") from exc
        addresses: list[InterfaceNetwork] = []
        for item in payload if isinstance(payload, list) else []:
            if item.get("ifname") != interface:
                continue
            for addr in item.get("addr_info", []):
                if addr.get("family") != "inet":
                    continue
                try:
                    address = ipaddress.IPv4Address(addr["local"])
                    prefixlen = int(addr["prefixlen"])
                    network = ipaddress.IPv4Network(f"{address}/{prefixlen}", strict=False)
                except (KeyError, TypeError, ValueError, ipaddress.AddressValueError) as exc:
                    raise NetworkDiscoveryError("invalid interface IPv4 address") from exc
                addresses.append(InterfaceNetwork(interface, address, network))
        if len(addresses) != 1:
            raise NetworkDiscoveryError("interface must expose exactly one IPv4 address")
        if addresses[0].network.num_addresses > self._max_addresses:
            raise NetworkDiscoveryError("directly connected network exceeds discovery bound")
        return addresses[0]

    def _scan_neighbor_table(self, scoped: InterfaceNetwork) -> tuple[DiscoveredNeighbor, ...]:
        self._neighbor_prober(scoped, self._timeout_s)
        result = self._runner(
            ["ip", "-json", "neigh", "show", "dev", scoped.interface],
            self._timeout_s,
        )
        if result.returncode != 0:
            raise NetworkDiscoveryError("failed to read local neighbor table")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise NetworkDiscoveryError("invalid neighbor-table JSON") from exc

        discovered: dict[tuple[str, str], DiscoveredNeighbor] = {}
        for item in payload if isinstance(payload, list) else []:
            try:
                address = ipaddress.IPv4Address(str(item.get("dst", "")))
            except ipaddress.AddressValueError:
                continue
            if address not in scoped.network:
                continue
            mac = _normalize_mac(str(item.get("lladdr", "")))
            if mac is None:
                continue
            key = (mac, str(address))
            discovered[key] = DiscoveredNeighbor(mac=mac, ipv4=str(address))
            if len(discovered) > self._max_devices:
                raise NetworkDiscoveryError("discovered device count exceeds bound")
        return tuple(sorted(discovered.values(), key=lambda item: (int(ipaddress.IPv4Address(item.ipv4)), item.mac)))
    def scan(self, interface: str) -> tuple[DiscoveredNeighbor, ...]:
        scoped = self._interface_network(interface)
        try:
            result = self._runner(
                [
                    "arp-scan",
                    f"--interface={interface}",
                    "--plain",
                    "--ignoredups",
                    "--retry=1",
                    str(scoped.network),
                ],
                self._timeout_s,
            )
        except FileNotFoundError:
            return self._scan_neighbor_table(scoped)
        if result.returncode != 0:
            raise NetworkDiscoveryError("arp-scan failed")
        discovered: dict[tuple[str, str], DiscoveredNeighbor] = {}
        for raw_line in result.stdout.splitlines():
            parts = raw_line.strip().split()
            if len(parts) < 2:
                continue
            try:
                address = ipaddress.IPv4Address(parts[0])
            except ipaddress.AddressValueError:
                continue
            if address not in scoped.network:
                continue
            mac = _normalize_mac(parts[1])
            if mac is None:
                continue
            key = (mac, str(address))
            discovered[key] = DiscoveredNeighbor(mac=mac, ipv4=str(address))
            if len(discovered) > self._max_devices:
                raise NetworkDiscoveryError("discovered device count exceeds bound")

        return tuple(
            sorted(
                discovered.values(),
                key=lambda item: (int(ipaddress.IPv4Address(item.ipv4)), item.mac),
            )
        )
