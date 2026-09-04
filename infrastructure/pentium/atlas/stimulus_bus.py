from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .stimulus_model import Stimulus, StimulusSeverity


@dataclass(frozen=True)
class PublishResult:
    accepted: bool
    dropped_stimulus_id: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class BusMetrics:
    published: int
    dropped: int
    critical_preserved: int


class StimulusBus:
    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._capacity = capacity
        self._queue: deque[Stimulus] = deque()
        self._published = 0
        self._dropped = 0
        self._critical_preserved = 0

    def publish(self, stimulus: Stimulus) -> PublishResult:
        if len(self._queue) < self._capacity:
            self._queue.append(stimulus)
            self._published += 1
            return PublishResult(True)

        noncritical_index = next(
            (
                index
                for index, queued in enumerate(self._queue)
                if queued.severity is not StimulusSeverity.CRITICAL
            ),
            None,
        )
        if noncritical_index is None and stimulus.severity is not StimulusSeverity.CRITICAL:
            self._dropped += 1
            self._critical_preserved += 1
            return PublishResult(False, stimulus.stimulus_id, "queue_all_critical")

        drop_index = noncritical_index if noncritical_index is not None else 0
        dropped = self._queue[drop_index]
        del self._queue[drop_index]
        if dropped.severity is not StimulusSeverity.CRITICAL and any(
            queued.severity is StimulusSeverity.CRITICAL for queued in self._queue
        ):
            self._critical_preserved += 1
        self._queue.append(stimulus)
        self._published += 1
        self._dropped += 1
        return PublishResult(True, dropped.stimulus_id, "overflow")

    def poll(self) -> Stimulus | None:
        if not self._queue:
            return None
        return self._queue.popleft()

    def metrics(self) -> BusMetrics:
        return BusMetrics(
            published=self._published,
            dropped=self._dropped,
            critical_preserved=self._critical_preserved,
        )
