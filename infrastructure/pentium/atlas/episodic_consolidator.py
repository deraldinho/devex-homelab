from __future__ import annotations

from .episodic_model import MemoryProvenance, SegmentStatus
from .memory_manager import MemoryManager
from .memory_model import MemoryLayer, MemoryRecord
from .memory_store import MemoryStore, MemoryStoreError


class EpisodicConsolidator:
    def __init__(self, store: MemoryStore, manager: MemoryManager):
        self._store = store
        self._manager = manager

    def consolidate(self, segment_id: str, now: str) -> bool:
        segment = self._store.get_segment(segment_id)
        if segment is None:
            raise MemoryStoreError("segmento inexistente")
        if segment.status is SegmentStatus.CONSOLIDATED:
            return False
        if segment.status is not SegmentStatus.CLOSED:
            raise MemoryStoreError("segmento nao esta CLOSED")
        items = self._store.list_evidence(segment_id)
        if not items:
            raise ValueError("segmento sem evidencias")
        if any(item.generation_id != segment.generation_id for item in items):
            raise ValueError("segmento mistura generations")

        ordered = tuple(sorted(items, key=lambda item: (item.occurred_at, item.event_id)))
        content = self._content(ordered)
        confidence = self._confidence(ordered)
        record = MemoryRecord(
            memory_id=f"episode:{segment.segment_id}",
            layer=MemoryLayer.EPISODIC,
            created_at=segment.updated_at,
            entity_id=segment.entity_id,
            content=content,
            importance=max(item.importance for item in ordered),
            confidence=confidence,
            frequency=1,
            origin=f"episodic:{segment.category.value}",
            criticality=max(item.criticality for item in ordered),
            dedupe_key=segment.semantic_key,
        )
        provenance = MemoryProvenance(
            segment_id=segment.segment_id,
            memory_id=record.memory_id,
            generation_id=segment.generation_id,
            sources=tuple(item.source for item in ordered),
            started_at=ordered[0].occurred_at,
            ended_at=ordered[-1].occurred_at,
            evidence_count=len(ordered),
        )
        return self._manager.remember_consolidated(segment, record, provenance, now)

    @staticmethod
    def _content(items) -> str:
        unique = []
        seen = set()
        for item in items:
            if item.content_reduced in seen:
                continue
            seen.add(item.content_reduced)
            unique.append(item.content_reduced)
        return "; ".join(unique)[:1024]

    @staticmethod
    def _confidence(items) -> float:
        verified = [item.reliability for item in items if item.verified]
        if not verified:
            return 0.0
        weight = sum(verified)
        if weight <= 0:
            return 0.0
        return sum(value * value for value in verified) / weight
