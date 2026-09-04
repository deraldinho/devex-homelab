from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TechnicalState(str, Enum):
    HEALTHY = "healthy"
    ACTIVE = "active"
    BUSY = "busy"
    DEGRADED = "degraded"
    STRESSED = "stressed"
    CRITICAL = "critical"
    RECOVERED = "recovered"


def _clamp_intensity(value: int) -> int:
    return max(0, min(4, int(value)))


@dataclass(frozen=True)
class Signal:
    source: str
    state: TechnicalState
    intensity: int
    required: bool = True
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "intensity", _clamp_intensity(self.intensity))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "state": self.state.value,
            "intensity": self.intensity,
            "required": self.required,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class GlobalAssessment:
    previous_state: TechnicalState | None
    state: TechnicalState
    intensity: int
    reasons: tuple[str, ...]
    recovered: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "intensity", _clamp_intensity(self.intensity))

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous_state": self.previous_state.value if self.previous_state else None,
            "state": self.state.value,
            "intensity": self.intensity,
            "reasons": list(self.reasons),
            "recovered": self.recovered,
        }


@dataclass(frozen=True)
class ReactionDecision:
    category: str
    reaction_id: str | None
    meme_id: str | None = None
    suppressed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "reaction_id": self.reaction_id,
            "meme_id": self.meme_id,
            "suppressed": self.suppressed,
        }
