from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol

from .network_discovery import LinuxArpScanner, NetworkDiscoveryError
from .stimulus_model import StimulusSeverity


@dataclass(frozen=True)
class SourceSnapshot:
    source: str
    status: str
    severity: StimulusSeverity
    payload: Mapping[str, Any]
    observed_at: str | None = None
    fingerprint_payload: Mapping[str, Any] | None = None


class StimulusSource(Protocol):
    name: str

    def poll(self) -> SourceSnapshot:
        ...


def _severity(status: str, *, required: bool) -> StimulusSeverity:
    normalized = status.strip().lower()
    if normalized == "healthy":
        return StimulusSeverity.INFO
    if normalized == "critical":
        return StimulusSeverity.CRITICAL
    if required and normalized in {"unavailable", "offline", "error"}:
        return StimulusSeverity.CRITICAL
    return StimulusSeverity.WARNING


def _observed_at(observed: Mapping[str, Any]) -> str | None:
    value = observed.get("observed_at") or observed.get("checked_at")
    return value if isinstance(value, str) and value else None


class PentiumSelfSource:
    name = "pentium.self"
    required = True

    def __init__(self, collector: Callable[[], dict[str, Any]]):
        self._collector = collector

    def poll(self) -> SourceSnapshot:
        observed = self._collector()
        status = str(observed.get("status", "degraded"))
        checks = {
            str(name): bool(value.get("ok"))
            for name, value in observed.get("checks", {}).items()
            if isinstance(value, dict)
        }
        metrics = observed.get("metrics", {})
        payload = {
            "status": status,
            "checks": checks,
            "metrics": {
                key: metrics[key]
                for key in ("memory_available_mb", "disk_free_percent")
                if key in metrics
            },
        }
        return SourceSnapshot(
            self.name, status, _severity(status, required=self.required), payload, _observed_at(observed)
        )

class CoreHealthSource:
    name = "core"
    required = True

    def __init__(self, collector: Callable[[], dict[str, Any]]):
        self._collector = collector

    def poll(self) -> SourceSnapshot:
        observed = self._collector()
        node = next(
            (item for item in observed.get("nodes", []) if item.get("name") == "core"),
            {},
        )
        status = str(node.get("status", observed.get("status", "degraded")))
        payload = {
            key: node.get(key)
            for key in (
                "status",
                "tailscale_online",
                "ipv4_matches",
                "ssh_reachable",
            )
            if key in node
        }
        payload.setdefault("status", status)
        return SourceSnapshot(
            self.name, status, _severity(status, required=self.required), payload, _observed_at(observed)
        )

class X99StatusSource:
    name = "x99"
    required = False

    def __init__(self, collector: Callable[[], dict[str, Any]]):
        self._collector = collector

    def poll(self) -> SourceSnapshot:
        observed = self._collector()
        status = str(observed.get("status", "degraded"))
        allowed = ("status", "hostname", "uptime_seconds", "last_boot", "error")
        payload = {key: observed[key] for key in allowed if key in observed}
        payload.setdefault("status", status)
        return SourceSnapshot(
            self.name, status, _severity(status, required=self.required), payload, _observed_at(observed)
        )


@dataclass
class _WifiPresenceRecord:
    mac: str
    ipv4: str
    first_seen: float
    last_seen: float


def _iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


class WifiPresenceSource:
    name = "wifi.presence"
    required = False

    def __init__(
        self,
        interface: str,
        *,
        scanner=None,
        clock: Callable[[], float] = time.time,
        presence_window_s: float = 180.0,
        max_devices: int = 256,
    ):
        self._interface = interface
        self._scanner = scanner or LinuxArpScanner()
        self._clock = clock
        self._presence_window_s = presence_window_s
        self._max_devices = max_devices
        self._devices: dict[str, _WifiPresenceRecord] = {}

    def poll(self) -> SourceSnapshot:
        now = self._clock()
        neighbors = self._scanner.scan(self._interface)
        if len(neighbors) > self._max_devices:
            raise NetworkDiscoveryError("wifi presence snapshot exceeds bound")
        for neighbor in neighbors:
            current = self._devices.get(neighbor.mac)
            if current is None:
                self._devices[neighbor.mac] = _WifiPresenceRecord(
                    mac=neighbor.mac,
                    ipv4=neighbor.ipv4,
                    first_seen=now,
                    last_seen=now,
                )
            else:
                current.ipv4 = neighbor.ipv4
                current.last_seen = now


        expired = [
            mac
            for mac, item in self._devices.items()
            if now - item.last_seen > self._presence_window_s
        ]
        for mac in expired:
            del self._devices[mac]

        devices = [
            {
                "mac": item.mac,
                "ipv4": item.ipv4,
                "first_seen": _iso_utc(item.first_seen),
                "last_seen": _iso_utc(item.last_seen),
                "presence": "present",
                "zone": "WIFI_OBSERVED",
            }
            for item in sorted(self._devices.values(), key=lambda item: (item.mac, item.ipv4))
        ]
        fingerprint_devices = [
            {key: item[key] for key in ("mac", "ipv4", "presence", "zone")}
            for item in devices
        ]
        return SourceSnapshot(
            source=self.name,
            status="healthy",
            severity=StimulusSeverity.INFO,
            payload={"zone": "WIFI_OBSERVED", "devices": devices},
            observed_at=_iso_utc(now),
            fingerprint_payload={"zone": "WIFI_OBSERVED", "devices": fingerprint_devices},
        )
