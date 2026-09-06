#!/usr/bin/env python3
"""Explicit inventory for hosts authorized as MANAGED."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class UnknownManagedHostError(LookupError):
    """Raised when a host id is not registered in managed inventory."""


class HostNotManagedError(PermissionError):
    """Raised when a registered host is not enrolled as MANAGED."""


@dataclass(frozen=True)
class ManagedHost:
    host_id: str
    enrollment: str
    user: str
    host: str
    identity_file: Path
    known_hosts_file: Path
    platform: str
    allowed_reads: frozenset[str]
    connect_timeout_seconds: int = 5
    max_output_bytes: int = 65536

    def __post_init__(self) -> None:
        if not self.host_id.strip():
            raise ValueError("host_id is required")
        if not self.user.strip():
            raise ValueError("user is required")
        if not self.host.strip():
            raise ValueError("host is required")
        if not self.platform.strip():
            raise ValueError("platform is required")
        if self.connect_timeout_seconds <= 0:
            raise ValueError("connect_timeout_seconds must be positive")
        if self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")


class ManagedInventory:
    def __init__(self, hosts: list[ManagedHost] | tuple[ManagedHost, ...]):
        by_id: dict[str, ManagedHost] = {}
        for host in hosts:
            if host.host_id in by_id:
                raise ValueError(f"duplicate managed host id: {host.host_id}")
            by_id[host.host_id] = host
        self._by_id = by_id

    def require_managed(self, host_id: str) -> ManagedHost:
        try:
            host = self._by_id[host_id]
        except KeyError as exc:
            raise UnknownManagedHostError(host_id) from exc
        if host.enrollment != "MANAGED":
            raise HostNotManagedError(host_id)
        return host
