from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol

from .network_discovery import LinuxArpScanner, NetworkDiscoveryError
from .presence_persistence import PresenceRepository
from .presence_registry import PresenceRegistry
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
            "self_healthy": bool(observed.get("self_healthy", status == "healthy")),
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
        registry: PresenceRegistry | None = None,
        repository: PresenceRepository | None = None,
    ):
        if registry is not None and repository is not None:
            raise ValueError("registry and repository are mutually exclusive")
        self._interface = interface
        self._scanner = scanner or LinuxArpScanner()
        self._clock = clock
        self._max_devices = max_devices
        self._repository = repository
        if registry is not None:
            if registry.max_devices != max_devices:
                raise ValueError("registry max_devices differs from source bound")
            self._registry = registry
        elif repository is not None:
            restored = repository.load(presence_window_s=presence_window_s)
            self._registry = restored or PresenceRegistry(
                presence_window_s=presence_window_s,
                max_devices=max_devices,
            )
        else:
            self._registry = PresenceRegistry(
                presence_window_s=presence_window_s,
                max_devices=max_devices,
            )

    def poll(self) -> SourceSnapshot:
        now = self._clock()
        neighbors = self._scanner.scan(self._interface)
        if len(neighbors) > self._max_devices:
            raise NetworkDiscoveryError("wifi presence snapshot exceeds bound")

        update = self._registry.observe(neighbors, now)
        if self._repository is not None:
            self._repository.save(self._registry)
        devices = [
            {
                "mac": item.mac,
                "ipv4": item.ipv4,
                "first_seen": _iso_utc(item.first_seen),
                "last_seen": _iso_utc(item.last_seen),
                "presence": item.presence,
                "zone": item.zone,
                "hostname": item.hostname,
                "vendor": item.vendor,
            }
            for item in update.devices
        ]
        events = [
            {
                "kind": event.kind,
                "mac": event.mac,
                "changed_fields": list(event.changed_fields),
            }
            for event in update.events
        ]
        fingerprint_devices = [
            {
                key: item[key]
                for key in ("mac", "ipv4", "presence", "zone", "hostname", "vendor")
            }
            for item in devices
        ]
        return SourceSnapshot(
            source=self.name,
            status="healthy",
            severity=StimulusSeverity.INFO,
            payload={
                "zone": "WIFI_OBSERVED",
                "devices": devices,
                "events": events,
            },
            observed_at=_iso_utc(now),
            fingerprint_payload={
                "zone": "WIFI_OBSERVED",
                "devices": fingerprint_devices,
            },
        )


class ManagedObservationSource:
    """Adapts bounded MANAGED READ results into ObservationRuntime snapshots."""

    required = False

    def __init__(self, host_id: str, reader, *, operations: tuple[str, ...]):
        if not host_id.strip():
            raise ValueError("host_id is required")
        if not operations or len(set(operations)) != len(operations):
            raise ValueError("operations must be non-empty and unique")
        self.host_id = host_id
        self.name = f"managed.{host_id}"
        self._reader = reader
        self._operations = tuple(operations)

    def poll(self) -> SourceSnapshot:
        reads = {
            operation: self._reader.read(self.host_id, operation)
            for operation in self._operations
        }
        degraded = any(
            str(result.get("status", "degraded")) != "healthy"
            for result in reads.values()
        )
        status = "degraded" if degraded else "healthy"
        payload = {
            "zone": "MANAGED",
            "host_id": self.host_id,
            "channel_status": status,
            "reads": reads,
        }
        return SourceSnapshot(
            source=self.name,
            status=status,
            severity=_severity(status, required=self.required),
            payload=payload,
            fingerprint_payload=payload,
        )
