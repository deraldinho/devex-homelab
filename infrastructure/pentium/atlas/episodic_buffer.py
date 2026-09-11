from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .config_memory import MemoryConfig
from .episodic_metrics import EpisodicMetrics
from .episodic_model import (
    ClosureReason,
    EpisodeCategory,
    EpisodicEvidence,
    EpisodicSegment,
    SegmentStatus,
)
from .memory_store import MemoryStore


@dataclass(frozen=True)
class EpisodicIngestResult:
    segment_id: str
    accepted: bool
    closed_segment_ids: tuple[str, ...] = ()


class EpisodicBuffer:
    def __init__(self, store: MemoryStore, config: MemoryConfig, *,
                 id_factory: Callable[[], str], metrics: EpisodicMetrics | None = None):
        self._store = store
        self._config = config
        self._id_factory = id_factory
        self._metrics = metrics or EpisodicMetrics()
    @property
    def metrics(self) -> EpisodicMetrics:
        return self._metrics

    def pending_bytes(self) -> int:
        total = sum(item.byte_count for item in self._store.list_open_segments(limit=10000))
        total += sum(item.byte_count for item in self._store.list_closed_segments(limit=10000))
        return total

    def _find_open(self, category: EpisodeCategory, entity_id: str | None,
                   semantic_key: str) -> EpisodicSegment | None:
        for item in self._store.list_open_segments(limit=self._config.episodic_max_open_segments + 1):
            if item.category is category and item.entity_id == entity_id and item.semantic_key == semantic_key:
                return item
        return None

    def _close_semantic_conflicts(self, category: EpisodeCategory, entity_id: str | None,
                                  semantic_key: str, now: str) -> tuple[str, ...]:
        closed = []
        for item in self._store.list_open_segments(limit=self._config.episodic_max_open_segments + 1):
            if item.category is category and item.entity_id == entity_id and item.semantic_key != semantic_key:
                self._store.close_segment(item.segment_id, ClosureReason.SEMANTIC_CHANGE, now)
                closed.append(item.segment_id)
        return tuple(closed)
    def _new_segment(self, evidence: EpisodicEvidence, category: EpisodeCategory,
                     semantic_key: str) -> EpisodicSegment:
        if len(self._store.list_open_segments(limit=self._config.episodic_max_open_segments + 1)) >= self._config.episodic_max_open_segments:
            raise OverflowError("max_open_segments excedido")
        segment = EpisodicSegment(
            self._id_factory(), evidence.generation_id, category, evidence.entity_id,
            semantic_key, evidence.occurred_at, evidence.occurred_at,
        )
        self._store.save_segment(segment)
        self._metrics.set("episodes_open", len(self._store.list_open_segments(limit=10000)))
        return segment

    def _close(self, segment_id: str, reason: ClosureReason, now: str) -> None:
        self._store.close_segment(segment_id, reason, now)
        self._metrics.increment("episodes_closed_total")
        if reason in {ClosureReason.GENERATION_FENCE, ClosureReason.RESTART_RECOVERY}:
            self._metrics.increment("generation_fence_total")
        self._metrics.set("episodes_open", len(self._store.list_open_segments(limit=10000)))

    def ingest(self, evidence: EpisodicEvidence, category: EpisodeCategory,
               semantic_key: str, *, terminal: bool = False) -> EpisodicIngestResult:
        payload_bytes = len(evidence.content_reduced.encode("utf-8"))
        if payload_bytes > self._config.episodic_max_bytes:
            raise OverflowError("evidencia excede max_bytes do segmento")
        if self.pending_bytes() + payload_bytes > self._config.episodic_max_pending_bytes:
            raise OverflowError("max_pending_bytes excedido")

        closed = list(self._close_semantic_conflicts(category, evidence.entity_id, semantic_key, evidence.occurred_at))
        segment = self._find_open(category, evidence.entity_id, semantic_key)
        if segment is not None and segment.generation_id != evidence.generation_id:
            self._close(segment.segment_id, ClosureReason.GENERATION_FENCE, evidence.occurred_at)
            closed.append(segment.segment_id)
            segment = None
        if segment is not None:
            if segment.event_count >= self._config.episodic_max_events:
                self._close(segment.segment_id, ClosureReason.MAX_EVENTS, evidence.occurred_at)
                closed.append(segment.segment_id)
                segment = None
            elif segment.byte_count + payload_bytes > self._config.episodic_max_bytes:
                self._close(segment.segment_id, ClosureReason.MAX_BYTES, evidence.occurred_at)
                closed.append(segment.segment_id)
                segment = None

        if segment is None:
            segment = self._new_segment(evidence, category, semantic_key)

        accepted = self._store.append_evidence(segment.segment_id, evidence)
        if not accepted:
            return EpisodicIngestResult(segment.segment_id, False, tuple(closed))

        self._metrics.increment("episode_events_total")
        self._metrics.increment("episode_bytes", payload_bytes)
        restored = self._store.get_segment(segment.segment_id)
        if terminal:
            self._close(segment.segment_id, ClosureReason.TERMINAL_EVENT, evidence.occurred_at)
            closed.append(segment.segment_id)
        elif restored is not None and restored.event_count >= self._config.episodic_max_events:
            self._close(segment.segment_id, ClosureReason.MAX_EVENTS, evidence.occurred_at)
            closed.append(segment.segment_id)
        elif restored is not None and restored.byte_count >= self._config.episodic_max_bytes:
            self._close(segment.segment_id, ClosureReason.MAX_BYTES, evidence.occurred_at)
            closed.append(segment.segment_id)
        return EpisodicIngestResult(segment.segment_id, True, tuple(closed))
    def close_idle(self, now: str) -> tuple[str, ...]:
        instant = datetime.fromisoformat(now)
        closed = []
        for segment in self._store.list_open_segments(limit=self._config.episodic_max_open_segments + 1):
            updated = datetime.fromisoformat(segment.updated_at)
            if (instant - updated).total_seconds() >= self._config.episodic_idle_timeout_s:
                self._close(segment.segment_id, ClosureReason.IDLE_TIMEOUT, now)
                closed.append(segment.segment_id)
        return tuple(closed)

    def recover_previous_generation(self, current_generation_id: str, now: str) -> tuple[str, ...]:
        recovered = []
        for segment in self._store.list_open_segments(limit=self._config.episodic_max_open_segments + 1):
            if segment.generation_id == current_generation_id:
                continue
            self._close(segment.segment_id, ClosureReason.RESTART_RECOVERY, now)
            recovered.append(segment.segment_id)
        return tuple(recovered)
