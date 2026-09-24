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


def probe_dns_latency(
    dns_server: str = "1.1.1.1",
    query_domain: str = "google.com",
    timeout_s: float = 2.0,
    resolver_fn: Callable[[str, str, float], tuple[bool, float, list[str]]] | None = None,
) -> dict[str, Any]:
    if resolver_fn is not None:
        ok, latency_ms, ips = resolver_fn(dns_server, query_domain, timeout_s)
        high_lat = bool(ok and latency_ms >= 150.0)
        return {
            "dns_server": dns_server,
            "query_domain": query_domain,
            "success": ok,
            "latency_ms": round(latency_ms, 2),
            "resolved_ips": ips,
            "status": "HEALTHY" if ok and not high_lat else ("DEGRADED" if ok else "DOWN"),
            "high_latency": high_lat,
        }

    t0 = time.monotonic()
    try:
        import socket
        addr_info = socket.getaddrinfo(query_domain, None, socket.AF_INET, socket.SOCK_STREAM)
        latency_ms = (time.monotonic() - t0) * 1000.0
        ips = sorted(list({item[4][0] for item in addr_info if item[4]}))
        ok = len(ips) > 0
        high_lat = latency_ms >= 150.0
        return {
            "dns_server": dns_server,
            "query_domain": query_domain,
            "success": ok,
            "latency_ms": round(latency_ms, 2),
            "resolved_ips": ips,
            "status": "HEALTHY" if ok and not high_lat else ("DEGRADED" if ok else "DOWN"),
            "high_latency": high_lat,
        }
    except Exception as exc:
        latency_ms = (time.monotonic() - t0) * 1000.0
        return {
            "dns_server": dns_server,
            "query_domain": query_domain,
            "success": False,
            "latency_ms": round(latency_ms, 2),
            "resolved_ips": [],
            "status": "DOWN",
            "high_latency": False,
            "error": str(exc),
        }


def probe_wan_traffic(
    router_host: str = "192.168.88.1",
    interface: str = "ether1",
    collector_fn: Callable[[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if collector_fn is not None:
        data = collector_fn(router_host, interface)
        return {
            "router_host": router_host,
            "interface": interface,
            "link_up": bool(data.get("link_up", True)),
            "rx_bytes": int(data.get("rx_bytes", 0)),
            "tx_bytes": int(data.get("tx_bytes", 0)),
            "rx_rate_kbps": float(data.get("rx_rate_kbps", 0.0)),
            "tx_rate_kbps": float(data.get("tx_rate_kbps", 0.0)),
            "status": str(data.get("status", "UP" if data.get("link_up", True) else "DOWN")),
        }

    import socket
    reachable = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.5)
            reachable = sock.connect_ex((router_host, 80)) == 0 or sock.connect_ex((router_host, 53)) == 0
    except Exception:
        reachable = False

    return {
        "router_host": router_host,
        "interface": interface,
        "link_up": reachable,
        "rx_bytes": 0,
        "tx_bytes": 0,
        "rx_rate_kbps": 0.0,
        "tx_rate_kbps": 0.0,
        "status": "UP" if reachable else "DOWN",
    }


def probe_dhcp_leases(
    router_host: str = "192.168.88.1",
    collector_fn: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if collector_fn is not None:
        data = collector_fn(router_host)
        leases = list(data.get("leases", []))
        active_count = sum(
            1
            for item in leases
            if isinstance(item, dict) and item.get("status", "bound") in ("bound", "active", "connected")
        )
        return {
            "router_host": router_host,
            "total_leases": len(leases),
            "active_leases_count": active_count,
            "static_count": int(data.get("static_count", 0)),
            "dynamic_count": int(data.get("dynamic_count", len(leases))),
            "leases": leases,
            "status": "HEALTHY" if active_count > 0 or data.get("reachable", True) else "DEGRADED",
        }

    return {
        "router_host": router_host,
        "total_leases": 0,
        "active_leases_count": 0,
        "static_count": 0,
        "dynamic_count": 0,
        "leases": [],
        "status": "HEALTHY",
    }


class MikroTikPerimeterSource:
    name = "mikrotik.perimeter"
    required = False

    def __init__(
        self,
        router_host: str = "192.168.88.1",
        wan_interface: str = "ether1",
        dns_target: str = "1.1.1.1",
        *,
        wan_prober: Callable[[str, str], dict[str, Any]] | None = None,
        dns_prober: Callable[[str, str, float], dict[str, Any]] | None = None,
        dhcp_prober: Callable[[str], dict[str, Any]] | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self.router_host = router_host
        self.wan_interface = wan_interface
        self.dns_target = dns_target
        self._wan_prober = wan_prober or (lambda h, iface: probe_wan_traffic(h, iface))
        self._dns_prober = dns_prober or (lambda dns, domain, timeout: probe_dns_latency(dns, domain, timeout))
        self._dhcp_prober = dhcp_prober or (lambda h: probe_dhcp_leases(h))
        self._clock = clock

    def poll(self) -> SourceSnapshot:
        now = self._clock()
        wan = self._wan_prober(self.router_host, self.wan_interface)
        dns = self._dns_prober(self.dns_target, "google.com", 2.0)
        dhcp = self._dhcp_prober(self.router_host)

        if wan.get("status") == "DOWN" or dns.get("status") == "DOWN":
            status = "critical" if wan.get("status") == "DOWN" and dns.get("status") == "DOWN" else "degraded"
        elif dns.get("high_latency") or dhcp.get("status") == "DEGRADED":
            status = "degraded"
        else:
            status = "healthy"

        observed_time = datetime.fromtimestamp(now, timezone.utc).isoformat()
        payload = {
            "zone": "PERIMETER",
            "router_host": self.router_host,
            "wan_traffic": wan,
            "dns_latency": dns,
            "dhcp_leases": dhcp,
            "status": status,
        }
        fingerprint_payload = {
            "zone": "PERIMETER",
            "wan_status": wan.get("status"),
            "dns_status": dns.get("status"),
            "dns_high_latency": dns.get("high_latency"),
            "dhcp_active_count": dhcp.get("active_leases_count"),
            "status": status,
        }

        return SourceSnapshot(
            source=self.name,
            status=status,
            severity=_severity(status, required=self.required),
            payload=payload,
            observed_at=observed_time,
            fingerprint_payload=fingerprint_payload,
        )

