from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping

from infrastructure.pentium.agent.managed_inventory import ManagedInventory
from infrastructure.pentium.agent.managed_read import ManagedReadOperation, ManagedReadService

from .health_probes import ProbeResult
from .health_supervisor_model import ComponentHealthState


def _utc_now(clock: Callable[[], datetime]) -> str:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class HostObservation:
    ok: bool
    host: str
    target: str
    platform: str
    state: ComponentHealthState
    observed_at: str
    reason: str
    evidence_refs: tuple[str, ...]
    raw_status: Mapping[str, object]


class PentiumHostAdapter:
    def __init__(
        self,
        probe: Callable[[str], ProbeResult],
        *,
        clock=lambda: datetime.now(timezone.utc),
    ):
        self._probe = probe
        self._clock = clock

    def observe(self, target: str) -> HostObservation:
        target = str(target).strip()
        if not target:
            raise ValueError("target must be non-empty")
        result = self._probe(target)
        return HostObservation(
            ok=result.ok,
            host="pentium",
            target=target,
            platform="linux",
            state=result.state,
            observed_at=result.observed_at or _utc_now(self._clock),
            reason=result.reason,
            evidence_refs=tuple(result.evidence_refs),
            raw_status={
                "reason": result.reason,
                "metrics": dict(result.metrics),
                "state": result.state.value,
            },
        )


class ManagedHostAdapter:
    def __init__(
        self,
        host_id: str,
        inventory: ManagedInventory,
        read_service: ManagedReadService,
        *,
        clock=lambda: datetime.now(timezone.utc),
    ):
        self._host_id = str(host_id).strip()
        self._inventory = inventory
        self._read_service = read_service
        self._clock = clock

    @staticmethod
    def _state(payload: Mapping[str, object]) -> tuple[bool, ComponentHealthState, str]:
        status = str(payload.get("status") or "").strip().lower()
        error = str(payload.get("error") or "").strip().lower()
        if status == "healthy":
            return True, ComponentHealthState.HEALTHY, "managed_read_healthy"
        if error in {"timeout", "ssh-failed"}:
            return False, ComponentHealthState.DISCONNECTED, error
        if status == "degraded":
            return False, ComponentHealthState.DEGRADED, error or "managed_read_degraded"
        return False, ComponentHealthState.UNKNOWN, error or "managed_read_unknown"

    def observe(self, target: str) -> HostObservation:
        host = self._inventory.require_managed(self._host_id)
        try:
            operation = ManagedReadOperation(str(target).strip())
        except ValueError as exc:
            raise ValueError(f"unsupported managed read operation: {target}") from exc

        payload = self._read_service.read(self._host_id, operation)
        ok, state, reason = self._state(payload)
        return HostObservation(
            ok=ok,
            host=self._host_id,
            target=operation.value,
            platform=host.platform.lower(),
            state=state,
            observed_at=_utc_now(self._clock),
            reason=reason,
            evidence_refs=(f"managed-read:{self._host_id}:{operation.value}",),
            raw_status=dict(payload),
        )
