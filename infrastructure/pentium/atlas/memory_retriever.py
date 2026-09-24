from __future__ import annotations

import json
import re
from typing import Any

from .memory_model import MemoryRecord
from .memory_store import MemoryStore


class MemoryRetriever:
    """Recuperador semântico de memórias e contexto relacional.

    Combina scoring de relevância, navegação em grafo de entidades,
    preferências do operador e limites de tokens/bytes.
    """

    def __init__(
        self,
        store: MemoryStore,
        *,
        graph: Any | None = None,
        preference_tracker: Any | None = None,
        max_items: int = 6,
        max_bytes: int = 2048,
    ):
        if max_items <= 0 or max_bytes <= 0:
            raise ValueError("limites de retrieval devem ser > 0")
        self._store = store
        self._graph = graph
        self._preference_tracker = preference_tracker
        self._max_items = max_items
        self._max_bytes = max_bytes

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {item for item in re.findall(r"[a-z0-9_-]+", text.lower()) if len(item) > 1}

    def _score(
        self,
        item: MemoryRecord,
        entity_id: str | None,
        terms: set[str],
        neighbor_ids: set[str] | None = None,
    ) -> float:
        score = 0.0
        if entity_id and item.entity_id == entity_id:
            score += 2.0
        elif neighbor_ids and item.entity_id in neighbor_ids:
            score += 1.0  # Grafo de proximidade

        overlap = len(self._tokens(item.content) & terms)
        score += min(2.0, overlap * 0.5)
        score += 0.8 * item.importance + 0.5 * item.confidence
        score += 0.2 * min(item.frequency, 5)
        score += 0.8 * item.criticality
        if item.protected or item.pinned:
            score += 0.5

        if self._preference_tracker is not None:
            for term in terms:
                weight = self._preference_tracker.get_preference("topic", term)
                if weight > 0.3:
                    score += 0.3
                    break

        return score

    def retrieve_graph_context(
        self,
        entity_id: str | None = None,
        *,
        query_terms=(),
        limit: int = 5,
    ) -> tuple[dict, ...]:
        """Recupera entidades contextuais do grafo para enriquecer inferência."""
        if self._graph is None:
            return ()

        entities: list[Any] = []
        seen_ids: set[str] = set()

        if entity_id:
            e = self._graph.get_entity(entity_id)
            if e is not None:
                entities.append(e)
                seen_ids.add(e.entity_id)
            for neighbor in self._graph.query_neighbors(entity_id, depth=1, max_results=limit):
                if neighbor.entity_id not in seen_ids:
                    entities.append(neighbor)
                    seen_ids.add(neighbor.entity_id)

        for term in query_terms:
            if len(entities) >= limit:
                break
            for found in self._graph.search_entities(str(term), limit=limit):
                if found.entity_id not in seen_ids:
                    entities.append(found)
                    seen_ids.add(found.entity_id)
                if len(entities) >= limit:
                    break

        results = []
        for ent in entities[:limit]:
            results.append({
                "entity_id": ent.entity_id,
                "type": ent.entity_type.value,
                "name": ent.name,
                "description": ent.description,
                "importance": ent.importance,
            })
        return tuple(results)

    def retrieve(
        self,
        *,
        entity_id: str | None = None,
        query_terms=(),
        message_id: str | None = None,
        reply_to_id: str | None = None,
        include_entities: bool = False,
    ) -> tuple[dict, ...]:
        terms = set()
        for term in query_terms:
            terms.update(self._tokens(str(term)))

        # 0. Descobrir vizinhos pelo grafo relacional se disponível
        neighbor_ids: set[str] = set()
        if self._graph is not None and entity_id:
            try:
                for neighbor in self._graph.query_neighbors(entity_id, depth=1):
                    neighbor_ids.add(neighbor.entity_id)
            except Exception:
                pass

        # 1. Recuperar árvore de conversa conectada pelo ID da mensagem (Thread Traversal)
        prioritized: list[MemoryRecord] = []
        if reply_to_id:
            prioritized.extend(self._store.get_connected_thread(reply_to_id))
        elif message_id:
            prioritized.extend(self._store.get_connected_thread(message_id))

        # 2. Recuperar memórias associadas no grafo relacional v2/v3
        ref_id = message_id or reply_to_id
        if ref_id:
            for assoc in self._store.get_associated_memories(ref_id, limit=5):
                if assoc not in prioritized:
                    prioritized.append(assoc)

        # 3. Candidatos gerais scored por relevância, entidade e vizinhança
        candidates = list(self._store.list(limit=200))
        candidates.sort(
            key=lambda item: (
                -self._score(item, entity_id, terms, neighbor_ids),
                item.created_at,
                item.memory_id,
            )
        )

        combined: list[MemoryRecord] = list(prioritized)
        for item in candidates:
            if item not in combined:
                combined.append(item)

        selected: list[dict] = []

        # Opcionalmente injeta entidades de grafo no topo
        if include_entities and self._graph is not None:
            for ent_ctx in self.retrieve_graph_context(entity_id, query_terms=query_terms, limit=3):
                item_dict = {
                    "memory_id": f"entity:{ent_ctx['entity_id']}",
                    "layer": "graph_entity",
                    "entity_id": ent_ctx["entity_id"],
                    "content": f"[{ent_ctx['type']}] {ent_ctx['name']}: {ent_ctx['description']}",
                    "importance": ent_ctx["importance"],
                    "confidence": 1.0,
                    "frequency": 1,
                }
                trial = selected + [item_dict]
                payload = json.dumps(trial, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                if len(payload) <= self._max_bytes:
                    selected.append(item_dict)

        for item in combined:
            reduced = {
                "memory_id": item.memory_id,
                "layer": item.layer.value,
                "entity_id": item.entity_id,
                "content": item.content,
                "importance": item.importance,
                "confidence": item.confidence,
                "frequency": item.frequency,
            }
            if getattr(item, "message_id", None):
                reduced["message_id"] = item.message_id
            if getattr(item, "reply_to_id", None):
                reduced["reply_to_id"] = item.reply_to_id

            trial = selected + [reduced]
            payload = json.dumps(trial, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            if len(payload) > self._max_bytes:
                continue
            selected.append(reduced)
            if len(selected) >= self._max_items:
                break
        return tuple(selected)
