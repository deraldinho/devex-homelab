from __future__ import annotations

import json
import re

from .memory_model import MemoryRecord
from .memory_store import MemoryStore


class MemoryRetriever:
    def __init__(self, store: MemoryStore, *, max_items: int = 6, max_bytes: int = 2048):
        if max_items <= 0 or max_bytes <= 0:
            raise ValueError("limites de retrieval devem ser > 0")
        self._store = store
        self._max_items = max_items
        self._max_bytes = max_bytes

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {item for item in re.findall(r"[a-z0-9_-]+", text.lower()) if len(item) > 1}

    def _score(self, item: MemoryRecord, entity_id: str | None, terms: set[str]) -> float:
        score = 0.0
        if entity_id and item.entity_id == entity_id:
            score += 2.0
        overlap = len(self._tokens(item.content) & terms)
        score += min(2.0, overlap * 0.5)
        score += 0.8 * item.importance + 0.5 * item.confidence
        score += 0.2 * min(item.frequency, 5)
        score += 0.8 * item.criticality
        if item.protected or item.pinned:
            score += 0.5
        return score

    def retrieve(self, *, entity_id: str | None, query_terms=()) -> tuple[dict, ...]:
        terms = set()
        for term in query_terms:
            terms.update(self._tokens(str(term)))
        candidates = list(self._store.list(limit=200))
        candidates.sort(
            key=lambda item: (-self._score(item, entity_id, terms), item.created_at, item.memory_id)
        )
        selected: list[dict] = []
        for item in candidates:
            reduced = {
                "memory_id": item.memory_id,
                "layer": item.layer.value,
                "entity_id": item.entity_id,
                "content": item.content,
                "importance": item.importance,
                "confidence": item.confidence,
                "frequency": item.frequency,
            }
            trial = selected + [reduced]
            payload = json.dumps(trial, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            if len(payload) > self._max_bytes:
                continue
            selected.append(reduced)
            if len(selected) >= self._max_items:
                break
        return tuple(selected)
