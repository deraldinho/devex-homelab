from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Mapping
from uuid import UUID, uuid4


class ActionType(str, Enum):
    CHAT_REPLY = "CHAT_REPLY"
    LOOK_AT = "LOOK_AT"
    SET_EXPRESSION = "SET_EXPRESSION"
    SET_GESTURE = "SET_GESTURE"
    SET_POSTURE = "SET_POSTURE"
    SPEAK_TTS = "SPEAK_TTS"
    CAPABILITY_REQUEST = "CAPABILITY_REQUEST"
    WAIT = "WAIT"


class ActionStatus(str, Enum):
    PLANNED = "PLANNED"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

_PARAMETER_KEYS = {
    ActionType.CHAT_REPLY: frozenset(),
    ActionType.LOOK_AT: frozenset(("direction",)),
    ActionType.SET_EXPRESSION: frozenset(("expression", "intensity")),
    ActionType.SET_GESTURE: frozenset(("gesture", "arm")),
    ActionType.SET_POSTURE: frozenset(("posture",)),
    ActionType.SPEAK_TTS: frozenset(("voice",)),
    ActionType.CAPABILITY_REQUEST: frozenset(("capability", "arguments")),
    ActionType.WAIT: frozenset(("duration_ms",)),
}

_TRANSITIONS = {
    ActionStatus.PLANNED: frozenset((ActionStatus.AUTHORIZED, ActionStatus.BLOCKED, ActionStatus.CANCELLED)),
    ActionStatus.AUTHORIZED: frozenset((ActionStatus.EXECUTING, ActionStatus.BLOCKED, ActionStatus.CANCELLED)),
    ActionStatus.EXECUTING: frozenset((ActionStatus.COMPLETED, ActionStatus.FAILED, ActionStatus.CANCELLED)),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _aware(value: str) -> str:
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return instant.astimezone(timezone.utc).isoformat()


def _text(value: object, name: str, limit: int, *, empty: bool = False) -> str:
    text = str(value).strip()
    if not text and not empty:
        raise ValueError(f"{name} is required")
    if len(text) > limit:
        raise ValueError(f"{name} exceeds bound")
    return text

def _uuid_text(value: object, name: str) -> str:
    text = _text(value, name, 64)
    try:
        UUID(text)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"{name} must be UUID-like") from exc
    return text


def _safe_value(value: object, *, depth: int = 0) -> object:
    if depth > 2:
        raise ValueError("parameter nesting exceeds bound")
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _text(value, "parameter", 256, empty=True)
    if isinstance(value, dict):
        if len(value) > 16:
            raise ValueError("parameter object exceeds bound")
        return {str(k)[:64]: _safe_value(v, depth=depth + 1) for k, v in value.items()}
    raise ValueError("unsupported parameter value")


def _parameters(action_type: ActionType, values: Mapping[str, object] | None) -> Mapping[str, object]:
    raw = dict(values or {})
    unknown = set(raw) - _PARAMETER_KEYS[action_type]
    if unknown:
        raise ValueError(f"parameters not allowed for {action_type.value}: {sorted(unknown)}")
    return MappingProxyType({key: _safe_value(value) for key, value in raw.items()})


@dataclass(frozen=True)
class AtlasAction:
    action_id: str
    type: ActionType
    target: str | None
    parameters: Mapping[str, object]
    status: ActionStatus
    reason: str | None
    created_at: str
    authorized_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    @classmethod
    def create(cls, action_type: ActionType | str, *, target: str | None = None,
               parameters: Mapping[str, object] | None = None) -> "AtlasAction":
        kind = action_type if isinstance(action_type, ActionType) else ActionType(str(action_type))
        clean_target = None if target is None else _text(target, "target", 128)
        return cls(str(uuid4()), kind, clean_target, _parameters(kind, parameters),
                   ActionStatus.PLANNED, None, _now())


@dataclass(frozen=True)
class PlanoAcaoAtlas:
    plan_id: str
    stimulus_id: str
    created_at: str
    objective: str
    confidence: float
    response_text: str | None
    actions: tuple[AtlasAction, ...]
    requires_confirmation: bool = False
    policy_decision: str | None = None

    def __post_init__(self) -> None:
        _uuid_text(self.plan_id, "plan_id")
        _text(self.stimulus_id, "stimulus_id", 128)
        object.__setattr__(self, "created_at", _aware(self.created_at))
        object.__setattr__(self, "objective", _text(self.objective, "objective", 512))
        confidence = float(self.confidence)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence outside 0..1")
        object.__setattr__(self, "confidence", confidence)
        if self.response_text is not None:
            object.__setattr__(self, "response_text", _text(self.response_text, "response_text", 1024))
        if not self.actions:
            raise ValueError("actions are required")
        object.__setattr__(self, "actions", tuple(self.actions))

    def to_dict(self) -> dict:
        return {
            "schema_version": 1, "plan_id": self.plan_id, "stimulus_id": self.stimulus_id,
            "created_at": self.created_at, "objective": self.objective,
            "confidence": self.confidence, "response_text": self.response_text,
            "requires_confirmation": self.requires_confirmation, "policy_decision": self.policy_decision,
            "actions": [{"action_id": a.action_id, "type": a.type.value, "target": a.target,
                         "parameters": dict(a.parameters), "status": a.status.value, "reason": a.reason,
                         "created_at": a.created_at, "authorized_at": a.authorized_at,
                         "started_at": a.started_at, "finished_at": a.finished_at} for a in self.actions],
        }

    @classmethod
    def create(cls, *, stimulus_id: str, objective: str, confidence: float,
               response_text: str | None, actions) -> "PlanoAcaoAtlas":
        return cls(str(uuid4()), stimulus_id, _now(), objective, confidence,
                   response_text, tuple(actions))


def transition_action(action: AtlasAction, target_status: ActionStatus | str, *,
                      reason: str | None = None, at: str | None = None) -> AtlasAction:
    target = target_status if isinstance(target_status, ActionStatus) else ActionStatus(str(target_status))
    allowed = _TRANSITIONS.get(action.status, frozenset())
    if target not in allowed:
        raise ValueError(f"illegal action transition {action.status.value}->{target.value}")
    when = _aware(at or _now())
    fields = {"status": target, "reason": None if reason is None else _text(reason, "reason", 256)}
    if target is ActionStatus.AUTHORIZED:
        fields["authorized_at"] = when
    elif target is ActionStatus.EXECUTING:
        fields["started_at"] = when
    else:
        fields["finished_at"] = when
    return replace(action, **fields)
