from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from .episodic_model import EpisodicSegment, MemoryProvenance
from .memory_model import MemoryLayer, MemoryRecord
from .memory_coherence_gate import review_promotion, same_evidence_claim
from .memory_store import MemoryStore


class MemoryPressure(str, Enum):
    NORMAL = "normal"
    CLEANUP = "cleanup"
    CONSOLIDATE = "consolidate"
    EVICT = "evict"
    FULL = "full"


@dataclass(frozen=True)
class MemoryPolicy:
    max_records: int
    max_bytes: int
    cleanup_ratio: float = 0.70
    consolidate_ratio: float = 0.85
    evict_ratio: float = 0.95

    def __post_init__(self) -> None:
        if self.max_records <= 0 or self.max_bytes <= 0:
            raise ValueError("limites de memoria devem ser > 0")
        if not 0 < self.cleanup_ratio < self.consolidate_ratio < self.evict_ratio < 1:
            raise ValueError("limites de pressao invalidos")

    def classify(self, ratio: float) -> MemoryPressure:
        if ratio >= 1.0:
            return MemoryPressure.FULL
        if ratio >= self.evict_ratio:
            return MemoryPressure.EVICT
        if ratio >= self.consolidate_ratio:
            return MemoryPressure.CONSOLIDATE
        if ratio >= self.cleanup_ratio:
            return MemoryPressure.CLEANUP
        return MemoryPressure.NORMAL

@dataclass(frozen=True)
class MemoryMaintenanceResult:
    pressure_before: MemoryPressure
    pressure_after: MemoryPressure
    ratio_before: float
    ratio_after: float
    removed_ids: tuple[str, ...]
    consolidated: int = 0


class MemoryManager:
    def __init__(self, store: MemoryStore, policy: MemoryPolicy, *, ingress=None):
        self._store = store
        self._policy = policy
        self._ingress = ingress

    def pressure_ratio(self) -> float:
        return max(
            self._store.count() / self._policy.max_records,
            self._store.size_bytes() / self._policy.max_bytes,
        )

    def remember(self, record: MemoryRecord, now: str, *, attestation=None) -> bool:
        if record.dedupe_key:
            for existing in self._store.list(limit=max(100, self._policy.max_records * 2)):
                if same_evidence_claim(existing, record):
                    merged = replace(
                        existing,
                        frequency=existing.frequency + record.frequency,
                        # Recurrence can raise frequency, never confidence or
                        # protection, without an independent evidence verifier.
                        importance=min(existing.importance, record.importance),
                        confidence=min(existing.confidence, record.confidence),
                        criticality=min(existing.criticality, record.criticality),
                        pinned=existing.pinned,
                        protected=existing.protected,
                    )
                    self._store.save(merged)
                    return True
        current = self._policy.classify(self.pressure_ratio())
        if current is MemoryPressure.FULL and not (record.protected or record.pinned):
            return False
        self._store.save(record)
        if attestation is not None:
            self._store.save_attestation(attestation)
        return True

    def remember_consolidated(self, segment: EpisodicSegment, record: MemoryRecord,
                              provenance: MemoryProvenance, now: str) -> bool:
        if segment.segment_id != provenance.segment_id:
            raise ValueError("provenance nao corresponde ao segmento")
        existing = self._store.find_matching_claim(record)
        current = self._policy.classify(self.pressure_ratio())
        if current is MemoryPressure.FULL and existing is None and not (record.protected or record.pinned):
            return False
        return self._store.persist_consolidated(segment.segment_id, record, provenance)

    def maintain(self, now: str) -> MemoryMaintenanceResult:
        ratio_before = self.pressure_ratio()
        pressure_before = self._policy.classify(ratio_before)
        removed: list[str] = []
        consolidated = 0
        promoted_ids: set[str] = set()

        if pressure_before is not MemoryPressure.NORMAL:
            removed.extend(self._remove_expired(now))

        ratio = self.pressure_ratio()
        pressure = self._policy.classify(ratio)
        if pressure in {MemoryPressure.CONSOLIDATE, MemoryPressure.EVICT, MemoryPressure.FULL}:
            consolidated = self._consolidate_duplicates()
            promoted_ids = set(self._promote_recurrent())

        ratio = self.pressure_ratio()
        pressure = self._policy.classify(ratio)
        if pressure in {MemoryPressure.EVICT, MemoryPressure.FULL}:
            removed.extend(self._evict_until(self._policy.consolidate_ratio, now, promoted_ids))

        ratio_after = self.pressure_ratio()
        return MemoryMaintenanceResult(
            pressure_before,
            self._policy.classify(ratio_after),
            ratio_before,
            ratio_after,
            tuple(removed),
            consolidated,
        )

    def _remove_expired(self, now: str) -> list[str]:
        instant = datetime.fromisoformat(now)
        removed: list[str] = []
        for item in self._store.list(limit=max(100, self._policy.max_records * 2)):
            if item.expires_at is None or item.protected or item.pinned:
                continue
            if datetime.fromisoformat(item.expires_at) <= instant and self._store.delete(item.memory_id):
                removed.append(item.memory_id)
        return removed

    def _consolidate_duplicates(self) -> int:
        groups: dict[tuple, list[MemoryRecord]] = {}
        for item in self._store.list(limit=max(100, self._policy.max_records * 2)):
            if not item.dedupe_key:
                continue
            # A dedupe key is caller-supplied: never aggregate confidence
            # between unrelated content, origins, tags or semantic layers.
            identity = (item.dedupe_key, item.origin, item.content,
                        item.entity_id, item.layer, item.tags,
                        item.pinned, item.protected)
            groups.setdefault(identity, []).append(item)
        consolidated = 0
        for items in groups.values():
            if len(items) < 2:
                continue
            keeper = items[0]
            merged = replace(
                keeper,
                frequency=sum(item.frequency for item in items),
                # No participant may use a shared dedupe key to increase
                # the group's authority, certainty or retention protection.
                importance=min(item.importance for item in items),
                confidence=min(item.confidence for item in items),
                criticality=min(item.criticality for item in items),
                pinned=keeper.pinned,
                protected=keeper.protected,
            )
            self._store.consolidate(merged, tuple(item.memory_id for item in items[1:]))
            consolidated += len(items) - 1
        return consolidated

    def _promote_recurrent(self) -> tuple[str, ...]:
        promoted: list[str] = []
        for item in self._store.list(limit=max(100, self._policy.max_records * 2)):
            if not (item.layer is MemoryLayer.EPISODIC and item.dedupe_key
                    and item.frequency >= 3 and item.confidence >= 0.7):
                continue
            verdict = None
            if self._ingress is not None:
                attestation = self._store.get_attestation(item.memory_id)
                if attestation is not None:
                    verdict = self._ingress.verify(item, attestation)
            if review_promotion(item, verdict=verdict).allowed:
                self._store.save(replace(item, layer=MemoryLayer.SEMANTIC))
                promoted.append(item.memory_id)
        return tuple(promoted)

    def _retention_score(self, item: MemoryRecord, now: str) -> float:
        age_s = max(0.0, (datetime.fromisoformat(now) - datetime.fromisoformat(item.created_at)).total_seconds())
        recency = 1.0 / (1.0 + age_s / 86400.0)
        frequency = min(1.0, item.frequency / 5.0)
        return (
            0.30 * item.importance
            + 0.20 * item.confidence
            + 0.15 * frequency
            + 0.20 * item.criticality
            + 0.15 * recency
        )

    def _evict_until(self, target_ratio: float, now: str, excluded_ids=()) -> list[str]:
        removed: list[str] = []
        candidates = [
            item for item in self._store.list(limit=max(100, self._policy.max_records * 2))
            if not item.protected and not item.pinned and item.memory_id not in excluded_ids
        ]
        candidates.sort(key=lambda item: (self._retention_score(item, now), item.created_at, item.memory_id))
        for item in candidates:
            if self.pressure_ratio() < target_ratio:
                break
            if self._store.delete(item.memory_id):
                removed.append(item.memory_id)
        return removed
