from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RecoveryRisk(str, Enum):
    READ = "read"
    SAFE_CONTROL = "safe_control"
    CONTROL = "control"
    RISKY_CONTROL = "risky_control"
    DESTRUCTIVE = "destructive"


class RecoveryState(str, Enum):
    PLANNED = "planned"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RECOVERED = "recovered"
    BLOCKED = "blocked"
    REFRESH_REQUIRED = "refresh_required"
    FAILED = "failed"
    ESCALATED = "escalated"
    COOLDOWN = "cooldown"


@dataclass(frozen=True)
class RecoveryPlan:
    recovery_id: str
    host: str
    target: str
    capability: str
    risk: RecoveryRisk
    reversible: bool
    expected_postconditions: tuple[str, ...]
    preconditions: tuple[str, ...] = ()
    max_attempts: int = 1
    cooldown_s: float = 300.0
    timeout_s: float = 15.0
    rollback_capability: str | None = None
    evidence_refs: tuple[str, ...] = ()
    generation_token: str | None = None
    requires_confirmation: bool = False

    def __post_init__(self) -> None:
        for name in ("recovery_id", "host", "target", "capability"):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"{name} must be non-empty")
            object.__setattr__(self, name, value)
        if not isinstance(self.risk, RecoveryRisk):
            raise TypeError("risk must be RecoveryRisk")
        postconditions = tuple(
            str(item).strip() for item in self.expected_postconditions if str(item).strip()
        )
        if not postconditions:
            raise ValueError("expected_postconditions must be non-empty")
        object.__setattr__(self, "expected_postconditions", postconditions)
        object.__setattr__(
            self,
            "preconditions",
            tuple(str(item).strip() for item in self.preconditions if str(item).strip()),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(str(item).strip() for item in self.evidence_refs if str(item).strip()),
        )
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be > 0")
        if float(self.cooldown_s) <= 0:
            raise ValueError("cooldown_s must be > 0")
        if float(self.timeout_s) <= 0:
            raise ValueError("timeout_s must be > 0")
        object.__setattr__(self, "cooldown_s", float(self.cooldown_s))
        object.__setattr__(self, "timeout_s", float(self.timeout_s))
        if self.rollback_capability is not None:
            value = str(self.rollback_capability).strip()
            object.__setattr__(self, "rollback_capability", value or None)
        if self.generation_token is not None:
            value = str(self.generation_token).strip()
            object.__setattr__(self, "generation_token", value or None)

    @property
    def recovery_key(self) -> str:
        return f"{self.host}:{self.capability}:{self.target}"


@dataclass(frozen=True)
class RecoveryResult:
    recovery_id: str
    state: RecoveryState
    attempts: int
    reason: str = ""
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.recovery_id).strip():
            raise ValueError("recovery_id must be non-empty")
        if not isinstance(self.state, RecoveryState):
            raise TypeError("state must be RecoveryState")
        if int(self.attempts) < 0:
            raise ValueError("attempts must be >= 0")
        object.__setattr__(self, "recovery_id", str(self.recovery_id).strip())
        object.__setattr__(self, "attempts", int(self.attempts))
        object.__setattr__(self, "reason", str(self.reason).strip())
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(str(item).strip() for item in self.evidence_refs if str(item).strip()),
        )
