from __future__ import annotations

import time
from typing import Callable

from .config_memory import MemoryConfig
from .episodic_adapters import evidence_from_incident
from .episodic_buffer import EpisodicBuffer
from .episodic_consolidator import EpisodicConsolidator
from .episodic_metrics import EpisodicMetrics
from .memory_manager import MemoryManager
from .memory_store import MemoryStore
from .pipeline_percepcao_correlacao import ResultadoPipelinePercepcaoCorrelacao


class EpisodicMemorySink:
    def __init__(
        self,
        store: MemoryStore,
        config: MemoryConfig,
        manager: MemoryManager,
        *,
        generation_id: str,
        id_factory: Callable[[], str],
        metrics: EpisodicMetrics | None = None,
        monotonic_clock: Callable[[], float] = time.perf_counter,
    ):
        if not generation_id or not generation_id.strip():
            raise ValueError("generation_id nao pode ser vazio")
        self._store = store
        self._config = config
        self._generation_id = generation_id.strip()
        self._metrics = metrics or EpisodicMetrics()
        self._clock = monotonic_clock
        self._buffer = EpisodicBuffer(
            store, config, id_factory=id_factory, metrics=self._metrics,
        )
        self._consolidator = EpisodicConsolidator(store, manager)

    @property
    def metrics(self) -> EpisodicMetrics:
        return self._metrics

    def __call__(self, result: ResultadoPipelinePercepcaoCorrelacao) -> None:
        if not result.aceito:
            return
        closed: list[str] = []
        for incident in result.incidentes:
            evidence, category, key, terminal = evidence_from_incident(
                incident, self._generation_id,
            )
            ingest = self._buffer.ingest(
                evidence, category, key, terminal=terminal,
            )
            closed.extend(ingest.closed_segment_ids)
        self._consolidate_ids(tuple(dict.fromkeys(closed)))

    def flush_idle(self, now: str) -> tuple[str, ...]:
        closed = self._buffer.close_idle(now)
        self._consolidate_ids(self._pending_closed_ids())
        return closed

    def recover(self, now: str) -> tuple[str, ...]:
        recovered = self._buffer.recover_previous_generation(
            self._generation_id, now,
        )
        self._consolidate_ids(self._pending_closed_ids())
        return recovered
    def _pending_closed_ids(self) -> tuple[str, ...]:
        limit = max(1, self._config.episodic_max_open_segments * 2)
        return tuple(
            segment.segment_id
            for segment in self._store.list_closed_segments(limit=limit)
        )

    def _consolidate_ids(self, segment_ids: tuple[str, ...]) -> None:
        for segment_id in segment_ids:
            started = self._clock()
            try:
                success = self._consolidator.consolidate(segment_id, "1970-01-01T00:00:00+00:00")
            except Exception:
                self._metrics.increment("consolidation_rejected_total")
                continue
            finally:
                elapsed_ms = max(0.0, (self._clock() - started) * 1000.0)
                self._metrics.set("consolidation_latency_ms", elapsed_ms)
            if success:
                self._metrics.increment("consolidation_success_total")
            else:
                self._metrics.increment("consolidation_rejected_total")
