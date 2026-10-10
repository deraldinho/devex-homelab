from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .state_model import TechnicalState


class ComponentHealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    STALE = "stale"
    DISCONNECTED = "disconnected"
    FAILED = "failed"
    RECOVERING = "recovering"
    PAUSED_INTENTIONALLY = "paused_intentionally"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HealthDimension:
    state: ComponentHealthState
    reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.state, ComponentHealthState):
            raise TypeError("state must be ComponentHealthState")
        object.__setattr__(self, "reason", str(self.reason).strip())


def _utc(value: str) -> str:
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("observed_at must include timezone")
    return instant.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class ComponentHealth:
    component_id: str
    host: str
    expected_state: str
    process_state: HealthDimension
    functional_state: HealthDimension
    freshness: HealthDimension
    dependency_state: HealthDimension
    observed_at: str
    evidence_refs: tuple[str, ...] = ()
    required: bool = True

    def __post_init__(self) -> None:
        for field_name in ("component_id", "host", "expected_state"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} must be non-empty")
            object.__setattr__(self, field_name, value)
        for field_name in ("process_state", "functional_state", "freshness", "dependency_state"):
            if not isinstance(getattr(self, field_name), HealthDimension):
                raise TypeError(f"{field_name} must be HealthDimension")
        object.__setattr__(self, "observed_at", _utc(self.observed_at))
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(str(item).strip() for item in self.evidence_refs if str(item).strip()),
        )


def map_technical_state(state: TechnicalState) -> ComponentHealthState:
    if state in {TechnicalState.HEALTHY, TechnicalState.ACTIVE, TechnicalState.RECOVERED}:
        return ComponentHealthState.HEALTHY
    if state in {TechnicalState.BUSY, TechnicalState.DEGRADED, TechnicalState.STRESSED}:
        return ComponentHealthState.DEGRADED
    if state is TechnicalState.CRITICAL:
        return ComponentHealthState.FAILED
    raise TypeError("state must be TechnicalState")
