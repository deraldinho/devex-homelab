from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable
import uuid


class SelfWorkState(str, Enum):
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    WORKING = "WORKING"
    REVIEWING = "REVIEWING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    ABANDONED = "ABANDONED"
    EXPIRED = "EXPIRED"
    BLOCKED = "BLOCKED"


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)

@dataclass(frozen=True)
class SelfWorkItem:
    item_id: str
    objective: str
    area: str
    state: SelfWorkState
    created_at: str
    updated_at: str
    valid_until: str
    operations_used: int = 0
    inferences_used: int = 0
    reason: str = ""

    @property
    def terminal(self) -> bool:
        return self.state in {
            SelfWorkState.COMPLETED,
            SelfWorkState.ABANDONED,
            SelfWorkState.EXPIRED,
            SelfWorkState.BLOCKED,
        }


class SelfWorkRuntime:
    def __init__(self, *, ttl_s: float = 300.0, max_operations: int = 20,
                 max_inferences: int = 2, id_factory: Callable[[], str] | None = None,
                 store: Any = None):
        if ttl_s <= 0 or max_operations <= 0 or max_inferences <= 0:
            raise ValueError("self work limits must be > 0")
        self._ttl_s = float(ttl_s)
        self._max_operations = int(max_operations)
        self._max_inferences = int(max_inferences)
        self._id_factory = id_factory or (lambda: str(uuid.uuid4()))
        self._store = store
        self._current: SelfWorkItem | None = None

    def restore_from_store(self, now: str) -> SelfWorkItem | None:
        if self._store is not None and self._current is None:
            active = self._store.load_active(now)
            if active is not None:
                self._current = active
                return active
        return None

    @property
    def current(self) -> SelfWorkItem | None:
        return self._current

    def propose(self, objective: str, area: str, *, now: str) -> SelfWorkItem:
        if self._current is not None:
            raise RuntimeError("self_work_already_active")
        instant = _utc(now)
        item = SelfWorkItem(
            self._id_factory(), objective.strip(), area.strip(), SelfWorkState.CANDIDATE,
            instant.isoformat(), instant.isoformat(),
            (instant + timedelta(seconds=self._ttl_s)).isoformat(),
        )
        if not item.objective or not item.area:
            raise ValueError("objective and area are required")
        self._current = item
        if self._store is not None:
            self._store.save_current(item)
        return item

    def _require_current(self) -> SelfWorkItem:
        if self._current is None:
            raise RuntimeError("self_work_missing")
        return self._current

    def _transition(self, state: SelfWorkState, *, now: str, terminal: bool = False,
                    reason: str | None = None) -> SelfWorkItem:
        current = self._require_current()
        updated = replace(
            current,
            state=state,
            updated_at=_utc(now).isoformat(),
            reason=current.reason if reason is None else str(reason),
        )
        self._current = None if terminal else updated
        if self._store is not None:
            if terminal:
                self._store.record_history(updated)
                self._store.save_current(None)
            else:
                self._store.save_current(updated)
        return updated

    def activate(self, *, now: str) -> SelfWorkItem:
        current = self._require_current()
        if current.state is not SelfWorkState.CANDIDATE:
            raise RuntimeError("self_work_not_candidate")
        return self._transition(SelfWorkState.ACTIVE, now=now)

    def begin_work(self, *, now: str) -> SelfWorkItem:
        current = self._require_current()
        if current.state not in {SelfWorkState.ACTIVE, SelfWorkState.PAUSED}:
            raise RuntimeError("self_work_not_startable")
        return self._transition(SelfWorkState.WORKING, now=now)

    def review(self, *, now: str) -> SelfWorkItem:
        if self._require_current().state is not SelfWorkState.WORKING:
            raise RuntimeError("self_work_not_working")
        return self._transition(SelfWorkState.REVIEWING, now=now)

    def complete(self, *, now: str) -> SelfWorkItem:
        if self._require_current().state is not SelfWorkState.REVIEWING:
            raise RuntimeError("self_work_not_reviewing")
        return self._transition(SelfWorkState.COMPLETED, now=now, terminal=True)

    def pause_for_human(self, *, now: str) -> SelfWorkItem:
        current = self._require_current()
        if current.state not in {SelfWorkState.ACTIVE, SelfWorkState.WORKING, SelfWorkState.REVIEWING}:
            return current
        return self._transition(SelfWorkState.PAUSED, now=now, reason="human_preempted")

    def resume_if_valid(self, *, now: str) -> SelfWorkItem:
        current = self._require_current()
        instant = _utc(now)
        if instant > _utc(current.valid_until):
            return self._transition(SelfWorkState.EXPIRED, now=now, terminal=True, reason="ttl_expired")
        if current.state is not SelfWorkState.PAUSED:
            raise RuntimeError("self_work_not_paused")
        return self._transition(SelfWorkState.WORKING, now=now, reason="")

    def record_operation(self, *, now: str) -> SelfWorkItem:
        current = self._require_current()
        used = current.operations_used + 1
        if used >= self._max_operations:
            updated = replace(current, operations_used=used)
            self._current = updated
            return self._transition(SelfWorkState.BLOCKED, now=now, terminal=True, reason="operation_budget_exceeded")
        updated = replace(current, operations_used=used, updated_at=_utc(now).isoformat())
        self._current = updated
        if self._store is not None:
            self._store.save_current(updated)
        return updated

    def record_inference(self, *, now: str) -> SelfWorkItem:
        current = self._require_current()
        used = current.inferences_used + 1
        if used >= self._max_inferences:
            updated = replace(current, inferences_used=used)
            self._current = updated
            return self._transition(SelfWorkState.BLOCKED, now=now, terminal=True, reason="inference_budget_exceeded")
        updated = replace(current, inferences_used=used, updated_at=_utc(now).isoformat())
        self._current = updated
        if self._store is not None:
            self._store.save_current(updated)
        return updated

    def abandon(self, *, now: str, reason: str) -> SelfWorkItem:
        return self._transition(SelfWorkState.ABANDONED, now=now, terminal=True, reason=reason)
