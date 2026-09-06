#!/usr/bin/env python3
"""Composition root for Atlas dual-zone observation I1."""

from __future__ import annotations

from collections.abc import Mapping

try:
    from agent.managed_read import ManagedReadOperation
except ImportError:
    from infrastructure.pentium.agent.managed_read import ManagedReadOperation

from .observation_runtime import ObservationRuntime, SourceSchedule
from .stimulus_sources import ManagedObservationSource


class _ManagedReadAdapter:
    def __init__(self, service):
        self._service = service

    def read(self, host_id: str, operation: str):
        return self._service.read(host_id, ManagedReadOperation(operation))


def build_dual_zone_runtime(
    *,
    wifi_source,
    managed_read_service,
    managed_hosts: Mapping[str, tuple[str, ...]],
    bus,
    journal,
    schedule: Mapping[str, SourceSchedule],
) -> ObservationRuntime:
    if not managed_hosts:
        raise ValueError("managed_hosts must be non-empty")

    adapter = _ManagedReadAdapter(managed_read_service)
    managed_sources = [
        ManagedObservationSource(host_id, adapter, operations=tuple(operations))
        for host_id, operations in managed_hosts.items()
    ]
    sources = [wifi_source, *managed_sources]
    source_names = {source.name for source in sources}
    if set(schedule) != source_names:
        raise ValueError("schedule sources must exactly match I1 sources")

    return ObservationRuntime(
        sources=sources,
        bus=bus,
        journal=journal,
        schedule=schedule,
    )
