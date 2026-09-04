from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from .stimulus_model import StimulusSeverity


@dataclass(frozen=True)
class SourceSnapshot:
    source: str
    status: str
    severity: StimulusSeverity
    payload: Mapping[str, Any]


class StimulusSource(Protocol):
    name: str

    def poll(self) -> SourceSnapshot:
        ...


def _severity(status: str) -> StimulusSeverity:
    return StimulusSeverity.INFO if status == "healthy" else StimulusSeverity.WARNING


class PentiumSelfSource:
    name = "pentium.self"

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
        return SourceSnapshot(self.name, status, _severity(status), payload)


class CoreHealthSource:
    name = "core"

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
        return SourceSnapshot(self.name, status, _severity(status), payload)


class X99StatusSource:
    name = "x99"

    def __init__(self, collector: Callable[[], dict[str, Any]]):
        self._collector = collector

    def poll(self) -> SourceSnapshot:
        observed = self._collector()
        status = str(observed.get("status", "degraded"))
        allowed = ("status", "hostname", "uptime_seconds", "last_boot", "error")
        payload = {key: observed[key] for key in allowed if key in observed}
        payload.setdefault("status", status)
        return SourceSnapshot(self.name, status, _severity(status), payload)
