from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from .stimulus_bus import StimulusBus
from .stimulus_model import Stimulus, StimulusSeverity, compute_novelty, stable_fingerprint
from .stimulus_sources import SourceSnapshot, StimulusSource


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
    ):
        self._sources = {source.name: source for source in sources}
        if len(self._sources) != len(sources):
            raise ValueError("duplicate stimulus source name")
        self._bus = bus
        self._journal = journal
        self._clock = clock
        self._id_factory = id_factory
        self._failure_cooldown_seconds = failure_cooldown_seconds
        self._state = {name: _SourceState() for name in self._sources}
        self._errors: list[str] = []

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
    ) -> Stimulus:
        return Stimulus(
            stimulus_id=self._id_factory(),
            source=source,
            kind=kind,
            severity=severity,
            timestamp=self._timestamp(now),
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
        fingerprint = stable_fingerprint(payload)

        if state.fingerprint == fingerprint:
            self._bus.record_deduplicated()
            return None

        previous_fingerprint = state.fingerprint
        previous_status = state.status
        seen_count = state.seen_counts.get(fingerprint, 0)
        novelty = compute_novelty(seen_count)

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
            and now - state.last_failure_emitted_at < self._failure_cooldown_seconds
        ):
            self._bus.record_deduplicated()
            return None

        if state.active_correlation is None:
            state.active_correlation = self._id_factory()
        seen_count = state.seen_counts.get(fingerprint, 0)
        stimulus = self._make_stimulus(
            source=source_name,
            kind="source_error",
            severity=StimulusSeverity.WARNING,
            payload=payload,
            novelty=compute_novelty(seen_count),
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
            snapshot = source.poll()
        except Exception as exc:
            return self._handle_failure(source_name, exc, now)
        return self._handle_snapshot(source_name, snapshot, now)
