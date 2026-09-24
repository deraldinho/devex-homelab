from __future__ import annotations

import json
import random
from collections import deque
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from .stimulus_bus import StimulusBus
from .stimulus_model import Stimulus, StimulusSeverity, novelty_score, stable_fingerprint
from .stimulus_sources import SourceSnapshot, StimulusSource


@dataclass(frozen=True)
class SourcePolicy:
    interval_s: float
    timeout_s: float
    max_backoff_s: float
    cooldown_s: float

    def __post_init__(self) -> None:
        if self.interval_s <= 0 or self.timeout_s <= 0:
            raise ValueError("interval_s and timeout_s must be > 0")
        if self.max_backoff_s < self.interval_s:
            raise ValueError("max_backoff_s must be >= interval_s")
        if self.cooldown_s < 0:
            raise ValueError("cooldown_s must be >= 0")


@dataclass(frozen=True)
class SourceSchedule:
    interval_seconds: float
    timeout_seconds: float
    max_backoff_seconds: float
    jitter_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0 or self.timeout_seconds <= 0:
            raise ValueError("interval_seconds and timeout_seconds must be > 0")
        if self.max_backoff_seconds < self.interval_seconds:
            raise ValueError("max_backoff_seconds must be >= interval_seconds")
        if self.jitter_seconds < 0:
            raise ValueError("jitter_seconds must be >= 0")


def load_observation_config(path: Path) -> dict[str, SourceSchedule]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("observation config schema_version must be 1")
    sources = payload.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("observation config must contain sources")
    schedules: dict[str, SourceSchedule] = {}
    for name, item in sources.items():
        if not isinstance(item, dict):
            raise ValueError(f"source {name!r} schedule must be an object")
        try:
            schedules[str(name)] = SourceSchedule(
                float(item["interval_seconds"]),
                float(item["timeout_seconds"]),
                float(item["max_backoff_seconds"]),
                float(item.get("jitter_seconds", 0.0)),
            )
        except KeyError as exc:
            raise ValueError(f"source {name!r} schedule missing {exc.args[0]}") from exc
    return schedules


def load_observation_policies(path: Path) -> dict[str, SourcePolicy]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("observation config schema_version must be 1")
    sources = payload.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("observation config must contain sources")
    policies: dict[str, SourcePolicy] = {}
    for name, item in sources.items():
        if not isinstance(item, dict):
            raise ValueError(f"source {name!r} policy must be an object")
        try:
            policies[str(name)] = SourcePolicy(
                float(item["interval_seconds"]),
                float(item["timeout_seconds"]),
                float(item["max_backoff_seconds"]),
                float(item["cooldown_seconds"]),
            )
        except KeyError as exc:
            raise ValueError(
                f"source {name!r} policy missing {exc.args[0]}"
            ) from exc
    return policies


class _BoundedPollSupervisor:
    def __init__(self, source_names):
        self._executors = {
            name: ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"atlas-{name}")
            for name in source_names
        }
        self._active = {}

    def poll(self, source: StimulusSource, timeout: float) -> SourceSnapshot:
        future = self._active.get(source.name)
        if future is not None and not future.done():
            raise TimeoutError(f"source {source.name} poll already in flight")
        if future is None:
            future = self._executors[source.name].submit(source.poll)
            self._active[source.name] = future
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError as exc:
            raise TimeoutError(f"source {source.name} poll timed out") from exc
        finally:
            if future.done():
                self._active.pop(source.name, None)

    def close(self) -> None:
        for executor in self._executors.values():
            executor.shutdown(wait=False, cancel_futures=True)


@dataclass
class _SourceState:
    fingerprint: str | None = None
    status: str | None = None
    seen_counts: dict[str, int] = field(default_factory=dict)
    active_correlation: str | None = None
    last_failure_fingerprint: str | None = None
    last_failure_emitted_at: float | None = None


class ObservationRuntime:
    def __init__(
        self,
        *,
        sources: list[StimulusSource],
        bus: StimulusBus,
        journal: Callable[[Stimulus], None],
        clock: Callable[[], float] = time.time,
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
        failure_cooldown_seconds: float = 60.0,
        policies: Mapping[str, SourcePolicy] | None = None,
        schedule: Mapping[str, SourceSchedule] | None = None,
        monotonic_clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        poll_runner: Callable[[StimulusSource, float], SourceSnapshot] | None = None,
        jitter_fn: Callable[[float], float] = lambda maximum: random.uniform(0.0, maximum),
        accepted_stimulus_sink: Callable[[Stimulus], None] | None = None,
        error_capacity: int = 64,
    ):
        self._sources = {source.name: source for source in sources}
        if len(self._sources) != len(sources):
            raise ValueError("duplicate stimulus source name")
        self._bus = bus
        self._journal = journal
        self._clock = clock
        self._id_factory = id_factory
        if policies is not None and schedule is not None:
            raise ValueError("policies and schedule are mutually exclusive")
        default_schedule = SourceSchedule(30.0, 5.0, 300.0, 0.0)
        if policies is not None:
            if set(policies) != set(self._sources):
                raise ValueError("policy sources must exactly match runtime sources")
            self._schedule = {
                name: SourceSchedule(
                    policy.interval_s, policy.timeout_s, policy.max_backoff_s, 0.0
                )
                for name, policy in policies.items()
            }
            self._failure_cooldown_by_source = {
                name: policy.cooldown_s for name, policy in policies.items()
            }
        else:
            self._schedule = dict(
                schedule or {name: default_schedule for name in self._sources}
            )
            if set(self._schedule) != set(self._sources):
                raise ValueError("schedule sources must exactly match runtime sources")
            self._failure_cooldown_by_source = {
                name: failure_cooldown_seconds for name in self._sources
            }
        self._monotonic_clock = monotonic_clock
        self._sleeper = sleeper
        self._poll_supervisor = None
        if poll_runner is None:
            self._poll_supervisor = _BoundedPollSupervisor(self._sources)
            self._poll_runner = self._poll_supervisor.poll
        else:
            self._poll_runner = poll_runner
        self._jitter_fn = jitter_fn
        self._next_due = {name: 0.0 for name in self._sources}
        self._consecutive_failures = {name: 0 for name in self._sources}
        self._state = {name: _SourceState() for name in self._sources}
        if not isinstance(error_capacity, int) or error_capacity <= 0:
            raise ValueError("error_capacity must be integer > 0")
        self._errors = deque(maxlen=error_capacity)
        self._accepted_stimulus_sink = accepted_stimulus_sink

    def errors(self) -> tuple[str, ...]:
        return tuple(self._errors)

    def _timestamp(self, now: float) -> str:
        return datetime.fromtimestamp(now, timezone.utc).isoformat()

    def _publish(self, stimulus: Stimulus) -> None:
        result = self._bus.publish(stimulus)
        if not result.accepted:
            return
        try:
            self._journal(stimulus)
        except Exception as exc:
            self._errors.append(f"journal:{type(exc).__name__}")
        if self._accepted_stimulus_sink is not None:
            try:
                self._accepted_stimulus_sink(stimulus)
            except Exception as exc:
                self._errors.append(f"accepted_sink:{type(exc).__name__}")

    def _make_stimulus(
        self,
        *,
        source: str,
        kind: str,
        severity: StimulusSeverity,
        payload: dict,
        novelty: float,
        correlation_id: str,
        previous_fingerprint: str | None,
        current_fingerprint: str,
        now: float,
        observed_at: str | None = None,
    ) -> Stimulus:
        return Stimulus(
            stimulus_id=self._id_factory(),
            source=source,
            kind=kind,
            severity=severity,
            timestamp=observed_at or self._timestamp(now),
            payload=payload,
            novelty=novelty,
            correlation_id=correlation_id,
            previous_fingerprint=previous_fingerprint,
            current_fingerprint=current_fingerprint,
        )

    def _handle_snapshot(
        self,
        source_name: str,
        snapshot: SourceSnapshot,
        now: float,
    ) -> Stimulus | None:
        state = self._state[source_name]
        payload = dict(snapshot.payload)
        payload["status"] = snapshot.status
        fingerprint_payload = dict(snapshot.fingerprint_payload or snapshot.payload)
        fingerprint_payload["status"] = snapshot.status
        fingerprint = stable_fingerprint(fingerprint_payload)

        if state.fingerprint == fingerprint:
            self._bus.record_deduplicated()
            return None

        previous_fingerprint = state.fingerprint
        previous_status = state.status
        seen_count = state.seen_counts.get(fingerprint, 0)
        novelty = novelty_score(previous_fingerprint, fingerprint, seen_count)

        if previous_fingerprint is None:
            kind = "baseline_observed"
            correlation_id = self._id_factory()
            if snapshot.status != "healthy":
                state.active_correlation = correlation_id
        elif previous_status != "healthy" and snapshot.status == "healthy":
            kind = "recovered"
            correlation_id = state.active_correlation or self._id_factory()
        elif snapshot.status != "healthy":
            kind = "status_changed"
            if state.active_correlation is None:
                state.active_correlation = self._id_factory()
            correlation_id = state.active_correlation
        else:
            kind = "status_changed"
            correlation_id = self._id_factory()

        severity = (
            StimulusSeverity.NOTICE
            if kind == "recovered"
            else snapshot.severity
        )
        stimulus = self._make_stimulus(
            source=source_name,
            kind=kind,
            severity=severity,
            payload=payload,
            novelty=novelty,
            correlation_id=correlation_id,
            previous_fingerprint=previous_fingerprint,
            current_fingerprint=fingerprint,
            now=now,
            observed_at=snapshot.observed_at,
        )

        state.fingerprint = fingerprint
        state.status = snapshot.status
        state.seen_counts[fingerprint] = seen_count + 1
        state.last_failure_fingerprint = None
        state.last_failure_emitted_at = None
        self._publish(stimulus)
        if kind == "recovered":
            state.active_correlation = None
        return stimulus

    def _handle_failure(
        self,
        source_name: str,
        exc: Exception,
        now: float,
    ) -> Stimulus | None:
        state = self._state[source_name]
        payload = {"status": "error", "error_type": type(exc).__name__}
        fingerprint = stable_fingerprint(payload)
        if (
            state.last_failure_fingerprint == fingerprint
            and state.last_failure_emitted_at is not None
            and now - state.last_failure_emitted_at < self._failure_cooldown_by_source[source_name]
        ):
            self._bus.record_deduplicated()
            return None

        if state.active_correlation is None:
            state.active_correlation = self._id_factory()
        seen_count = state.seen_counts.get(fingerprint, 0)
        failure_severity = (
            StimulusSeverity.CRITICAL
            if bool(getattr(self._sources[source_name], "required", False))
            else StimulusSeverity.WARNING
        )
        stimulus = self._make_stimulus(
            source=source_name,
            kind="source_error",
            severity=failure_severity,
            payload=payload,
            novelty=novelty_score(state.fingerprint, fingerprint, seen_count),
            correlation_id=state.active_correlation,
            previous_fingerprint=state.fingerprint,
            current_fingerprint=fingerprint,
            now=now,
        )
        state.fingerprint = fingerprint
        state.status = "error"
        state.seen_counts[fingerprint] = seen_count + 1
        state.last_failure_fingerprint = fingerprint
        state.last_failure_emitted_at = now
        self._publish(stimulus)
        return stimulus

    def run_once(self, source_name: str) -> Stimulus | None:
        source = self._sources[source_name]
        now = self._clock()
        try:
            snapshot = self._poll_runner(
                source, self._schedule[source_name].timeout_seconds
            )
        except Exception as exc:
            return self._handle_failure(source_name, exc, now)
        return self._handle_snapshot(source_name, snapshot, now)

    def run_scheduled_cycle(self) -> float:
        now = self._monotonic_clock()
        due_names = [
            name for name in self._sources if self._next_due[name] <= now
        ]
        for name in due_names:
            self.run_once(name)
            schedule = self._schedule[name]
            failed = self._state[name].status == "error"
            if failed:
                self._consecutive_failures[name] += 1
                exp = min(self._consecutive_failures[name], 10)
                delay = min(
                    schedule.interval_seconds * (2 ** exp),
                    schedule.max_backoff_seconds,
                )
            else:
                self._consecutive_failures[name] = 0
                delay = schedule.interval_seconds
            jitter = (
                self._jitter_fn(schedule.jitter_seconds)
                if schedule.jitter_seconds > 0
                else 0.0
            )
            self._next_due[name] = self._monotonic_clock() + delay + jitter

        current = self._monotonic_clock()
        return min(max(0.0, due - current) for due in self._next_due.values())

    def close(self) -> None:
        if self._poll_supervisor is not None:
            self._poll_supervisor.close()

    def run_forever(self, stop_event) -> None:
        try:
            while not stop_event.is_set():
                delay = self.run_scheduled_cycle()
                if stop_event.is_set():
                    break
                self._sleeper(max(0.001, delay))
        finally:
            self.close()
