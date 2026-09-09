from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from uuid import UUID

from .action_plan import ActionStatus, ActionType, AtlasAction, PlanoAcaoAtlas

_TERMINAL = frozenset((ActionStatus.COMPLETED, ActionStatus.BLOCKED, ActionStatus.FAILED, ActionStatus.CANCELLED))
_SENSITIVE_KEYS = frozenset(("secret", "token", "password", "api_key", "apikey", "authorization"))


def _sanitize(value):
    if isinstance(value, dict) or hasattr(value, "items"):
        result = {}
        for key, item in dict(value).items():
            if str(key).lower() in _SENSITIVE_KEYS:
                continue
            result[str(key)] = _sanitize(item)
        return result
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    return value


def _action_dict(action: AtlasAction) -> dict:
    return {
        "action_id": action.action_id, "type": action.type.value, "target": action.target,
        "parameters": _sanitize(action.parameters), "status": action.status.value,
        "reason": action.reason, "created_at": action.created_at,
        "authorized_at": action.authorized_at, "started_at": action.started_at,
        "finished_at": action.finished_at,
    }


def _plan_dict(plan: PlanoAcaoAtlas) -> dict:
    return {
        "schema_version": 1, "plan_id": plan.plan_id, "stimulus_id": plan.stimulus_id,
        "created_at": plan.created_at, "objective": plan.objective,
        "confidence": plan.confidence, "response_text": plan.response_text,
        "requires_confirmation": plan.requires_confirmation,
        "policy_decision": plan.policy_decision,
        "actions": [_action_dict(action) for action in plan.actions],
    }


def _action_from_dict(data: dict) -> AtlasAction:
    UUID(str(data["action_id"]))
    created = AtlasAction.create(
        ActionType(data["type"]), target=data.get("target"),
        parameters=dict(data.get("parameters") or {}),
    )
    return replace(
        created, action_id=str(data["action_id"]), status=ActionStatus(data["status"]),
        reason=data.get("reason"), created_at=str(data["created_at"]),
        authorized_at=data.get("authorized_at"), started_at=data.get("started_at"),
        finished_at=data.get("finished_at"),
        parameters=MappingProxyType(dict(data.get("parameters") or {})),
    )


def _plan_from_dict(data: dict) -> PlanoAcaoAtlas:
    if data.get("schema_version") != 1:
        raise ValueError("unsupported action plan schema")
    return PlanoAcaoAtlas(
        plan_id=str(data["plan_id"]), stimulus_id=str(data["stimulus_id"]),
        created_at=str(data["created_at"]), objective=str(data["objective"]),
        confidence=float(data["confidence"]), response_text=data.get("response_text"),
        actions=tuple(_action_from_dict(item) for item in data["actions"]),
        requires_confirmation=bool(data.get("requires_confirmation", False)),
        policy_decision=data.get("policy_decision"),
    )


class ActionPlanStore:
    def __init__(self, current_path: Path, history_path: Path, *, max_history: int = 64,
                 max_bytes: int = 131072):
        if max_history <= 0 or max_bytes <= 0:
            raise ValueError("bounds must be > 0")
        self.current_path = Path(current_path)
        self.history_path = Path(history_path)
        self.max_history = int(max_history)
        self.max_bytes = int(max_bytes)

    def _atomic_write(self, path: Path, text: str) -> None:
        encoded = text.encode("utf-8")
        if len(encoded) > self.max_bytes:
            raise ValueError("serialized action plan exceeds max_bytes")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush(); os.fsync(handle.fileno())
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)

    def save_current(self, plan: PlanoAcaoAtlas) -> None:
        payload = json.dumps(_plan_dict(plan), ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")) + "\n"
        self._atomic_write(self.current_path, payload)

    def load_current(self) -> PlanoAcaoAtlas:
        payload = json.loads(self.current_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid current action plan")
        return _plan_from_dict(payload)

    def append_terminal(self, plan: PlanoAcaoAtlas) -> None:
        if any(action.status not in _TERMINAL for action in plan.actions):
            raise ValueError("history accepts only terminal plans")
        record = json.dumps(_plan_dict(plan), ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"))
        if len((record + "\n").encode("utf-8")) > self.max_bytes:
            raise ValueError("serialized action plan exceeds max_bytes")
        lines = []
        if self.history_path.is_file():
            lines = [line for line in self.history_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        lines.append(record)
        lines = lines[-self.max_history:]
        while lines and len(("\n".join(lines) + "\n").encode("utf-8")) > self.max_bytes:
            lines.pop(0)
        self._atomic_write(self.history_path, "\n".join(lines) + "\n")
