"""Atlas Memory Graph — Grafo de entidades e relações tipadas.

Camada de conhecimento estruturado acima do MemoryStore.
Persiste entidades (nós) e relações (arestas dirigidas) em SQLite,
permitindo busca por vizinhança, caminho e tipo.

Entidades representam conceitos permanentes do homelab:
projetos, nós, repositórios, decisões, padrões e preferências.

Relações representam conexões semânticas entre entidades.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Mapping


class EntityType(str, Enum):
    PROJECT = "project"
    NODE = "node"
    REPOSITORY = "repository"
    DECISION = "decision"
    PATTERN = "pattern"
    PREFERENCE = "preference"
    PERSON = "person"
    SERVICE = "service"
    INCIDENT = "incident"


class RelationType(str, Enum):
    OWNS = "owns"
    DEPENDS_ON = "depends_on"
    DECIDED_BY = "decided_by"
    PATTERN_OF = "pattern_of"
    PREFERS = "prefers"
    RUNS_ON = "runs_on"
    MONITORS = "monitors"
    CAUSED_BY = "caused_by"
    RESOLVED_BY = "resolved_by"
    RELATED_TO = "related_to"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc(value: str) -> str:
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("timestamp deve possuir timezone")
    return instant.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class Entity:
    """Nó no grafo de conhecimento."""
    entity_id: str
    entity_type: EntityType
    name: str
    description: str = ""
    properties: Mapping[str, str] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    importance: float = 0.5
    pinned: bool = False

    def __post_init__(self) -> None:
        if not self.entity_id or not self.entity_id.strip():
            raise ValueError("entity_id nao pode ser vazio")
        if not isinstance(self.entity_type, EntityType):
            raise ValueError("entity_type invalido")
        if not self.name or not self.name.strip():
            raise ValueError("name nao pode ser vazio")
        if not 0.0 <= self.importance <= 1.0:
            raise ValueError("importance deve estar entre 0 e 1")
        object.__setattr__(self, "entity_id", self.entity_id.strip())
        object.__setattr__(self, "name", self.name.strip())
        ts = self.created_at or _utc_now()
        object.__setattr__(self, "created_at", _utc(ts))
        us = self.updated_at or ts
        object.__setattr__(self, "updated_at", _utc(us))


@dataclass(frozen=True)
class Relation:
    """Aresta dirigida no grafo de conhecimento."""
    source_id: str
    target_id: str
    relation_type: RelationType
    weight: float = 1.0
    properties: Mapping[str, str] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.source_id or not self.target_id:
            raise ValueError("source_id e target_id nao podem ser vazios")
        if not isinstance(self.relation_type, RelationType):
            raise ValueError("relation_type invalido")
        if not 0.0 <= self.weight <= 10.0:
            raise ValueError("weight deve estar entre 0 e 10")
        ts = self.created_at or _utc_now()
        object.__setattr__(self, "created_at", _utc(ts))


class MemoryGraphError(RuntimeError):
    pass


class MemoryGraph:
    """Grafo de entidades e relações persistido em SQLite.

    Opera sobre um banco SQLite dedicado (separado do memory.sqlite3)
    para manter a fronteira do grafo de conhecimento independente
    da store de memórias episódicas/semânticas.
    """

    def __init__(self, path: Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._db = sqlite3.connect(self._path)
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA foreign_keys=ON")
            self._init_schema()
        except sqlite3.Error as exc:
            raise MemoryGraphError(str(exc)) from exc

    def _init_schema(self) -> None:
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS entity_nodes (
                entity_id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                properties TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                importance REAL NOT NULL DEFAULT 0.5,
                pinned INTEGER NOT NULL DEFAULT 0
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS entity_relations (
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                properties TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                PRIMARY KEY (source_id, target_id, relation_type)
            )
        """)
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_entity_type ON entity_nodes(entity_type)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_entity_name ON entity_nodes(name)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_rel_source ON entity_relations(source_id)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_rel_target ON entity_relations(target_id)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_rel_type ON entity_relations(relation_type)"
        )
        self._db.commit()

    # --- Entity CRUD ---

    def add_entity(self, entity: Entity) -> None:
        """Insere ou atualiza uma entidade no grafo."""
        props_json = json.dumps(
            dict(entity.properties), ensure_ascii=False, sort_keys=True
        )
        try:
            self._db.execute("""
                INSERT INTO entity_nodes
                    (entity_id, entity_type, name, description, properties,
                     created_at, updated_at, importance, pinned)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    properties=excluded.properties,
                    updated_at=excluded.updated_at,
                    importance=excluded.importance,
                    pinned=excluded.pinned
            """, (
                entity.entity_id, entity.entity_type.value, entity.name,
                entity.description, props_json, entity.created_at,
                entity.updated_at, entity.importance, int(entity.pinned),
            ))
            self._db.commit()
        except sqlite3.Error as exc:
            raise MemoryGraphError(str(exc)) from exc

    def get_entity(self, entity_id: str) -> Entity | None:
        row = self._db.execute(
            "SELECT * FROM entity_nodes WHERE entity_id=?", (entity_id,)
        ).fetchone()
        return self._entity_row(row) if row else None

    def list_entities(
        self,
        *,
        entity_type: EntityType | None = None,
        limit: int = 100,
    ) -> tuple[Entity, ...]:
        if limit <= 0:
            raise ValueError("limit deve ser > 0")
        if entity_type is not None:
            rows = self._db.execute(
                "SELECT * FROM entity_nodes WHERE entity_type=? "
                "ORDER BY importance DESC, updated_at DESC LIMIT ?",
                (entity_type.value, limit),
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT * FROM entity_nodes "
                "ORDER BY importance DESC, updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(self._entity_row(r) for r in rows)

    def delete_entity(self, entity_id: str) -> bool:
        """Remove entidade e todas as relações conectadas."""
        try:
            with self._db:
                self._db.execute(
                    "DELETE FROM entity_relations WHERE source_id=? OR target_id=?",
                    (entity_id, entity_id),
                )
                cursor = self._db.execute(
                    "DELETE FROM entity_nodes WHERE entity_id=?", (entity_id,)
                )
            return cursor.rowcount > 0
        except sqlite3.Error as exc:
            raise MemoryGraphError(str(exc)) from exc

    def search_entities(self, query: str, *, limit: int = 20) -> tuple[Entity, ...]:
        """Busca por substring no nome ou descrição da entidade."""
        if not query or not query.strip():
            return ()
        pattern = f"%{query.strip()}%"
        rows = self._db.execute(
            "SELECT * FROM entity_nodes "
            "WHERE name LIKE ? OR description LIKE ? "
            "ORDER BY importance DESC, updated_at DESC LIMIT ?",
            (pattern, pattern, limit),
        ).fetchall()
        return tuple(self._entity_row(r) for r in rows)

    # --- Relation CRUD ---

    def add_relation(self, relation: Relation) -> None:
        """Insere ou atualiza uma relação no grafo."""
        props_json = json.dumps(
            dict(relation.properties), ensure_ascii=False, sort_keys=True
        )
        try:
            self._db.execute("""
                INSERT INTO entity_relations
                    (source_id, target_id, relation_type, weight, properties, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, target_id, relation_type) DO UPDATE SET
                    weight=excluded.weight,
                    properties=excluded.properties
            """, (
                relation.source_id, relation.target_id,
                relation.relation_type.value, relation.weight,
                props_json, relation.created_at,
            ))
            self._db.commit()
        except sqlite3.Error as exc:
            raise MemoryGraphError(str(exc)) from exc

    def get_relations(
        self,
        entity_id: str,
        *,
        direction: str = "outgoing",
        relation_type: RelationType | None = None,
        limit: int = 50,
    ) -> tuple[Relation, ...]:
        """Retorna relações de uma entidade.

        direction: 'outgoing' (source=entity), 'incoming' (target=entity), 'both'.
        """
        results = []
        if direction in ("outgoing", "both"):
            q = "SELECT * FROM entity_relations WHERE source_id=?"
            args: list = [entity_id]
            if relation_type is not None:
                q += " AND relation_type=?"
                args.append(relation_type.value)
            q += " ORDER BY weight DESC LIMIT ?"
            args.append(limit)
            results.extend(self._relation_row(r) for r in self._db.execute(q, args).fetchall())
        if direction in ("incoming", "both"):
            q = "SELECT * FROM entity_relations WHERE target_id=?"
            args = [entity_id]
            if relation_type is not None:
                q += " AND relation_type=?"
                args.append(relation_type.value)
            q += " ORDER BY weight DESC LIMIT ?"
            args.append(limit)
            results.extend(self._relation_row(r) for r in self._db.execute(q, args).fetchall())
        return tuple(results)

    def remove_relation(
        self, source_id: str, target_id: str, relation_type: RelationType
    ) -> bool:
        cursor = self._db.execute(
            "DELETE FROM entity_relations WHERE source_id=? AND target_id=? AND relation_type=?",
            (source_id, target_id, relation_type.value),
        )
        self._db.commit()
        return cursor.rowcount > 0

    # --- Graph Queries ---

    def query_neighbors(
        self,
        entity_id: str,
        *,
        depth: int = 1,
        relation_type: RelationType | None = None,
        max_results: int = 50,
    ) -> tuple[Entity, ...]:
        """Retorna entidades vizinhas até `depth` saltos de distância."""
        if depth < 1:
            raise ValueError("depth deve ser >= 1")
        visited: set[str] = {entity_id}
        frontier: set[str] = {entity_id}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for node_id in frontier:
                for rel in self.get_relations(
                    node_id, direction="both", relation_type=relation_type, limit=max_results
                ):
                    neighbor = rel.target_id if rel.source_id == node_id else rel.source_id
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.add(neighbor)
            frontier = next_frontier
            if not frontier:
                break

        visited.discard(entity_id)
        entities = []
        for nid in sorted(visited):
            e = self.get_entity(nid)
            if e is not None:
                entities.append(e)
            if len(entities) >= max_results:
                break
        return tuple(entities)

    def query_path(
        self,
        source_id: str,
        target_id: str,
        *,
        max_depth: int = 4,
    ) -> tuple[str, ...] | None:
        """Busca BFS para encontrar caminho mais curto entre duas entidades.

        Retorna tupla de entity_ids formando o caminho, ou None se não encontrado.
        """
        if source_id == target_id:
            return (source_id,)

        visited: set[str] = {source_id}
        parents: dict[str, str] = {}
        frontier: list[str] = [source_id]

        for _ in range(max_depth):
            next_frontier: list[str] = []
            for node_id in frontier:
                for rel in self.get_relations(node_id, direction="both", limit=100):
                    neighbor = rel.target_id if rel.source_id == node_id else rel.source_id
                    if neighbor in visited:
                        continue
                    visited.add(neighbor)
                    parents[neighbor] = node_id
                    if neighbor == target_id:
                        path: list[str] = [target_id]
                        current = target_id
                        while current in parents:
                            current = parents[current]
                            path.append(current)
                        path.reverse()
                        return tuple(path)
                    next_frontier.append(neighbor)
            frontier = next_frontier
            if not frontier:
                break
        return None

    def entity_count(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM entity_nodes").fetchone()[0])

    def relation_count(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM entity_relations").fetchone()[0])

    def close(self) -> None:
        self._db.close()

    # --- Row converters ---

    @staticmethod
    def _entity_row(row) -> Entity:
        props = {}
        try:
            props = json.loads(row[4]) if row[4] else {}
        except (json.JSONDecodeError, TypeError):
            pass
        return Entity(
            entity_id=row[0],
            entity_type=EntityType(row[1]),
            name=row[2],
            description=row[3] or "",
            properties=props,
            created_at=row[5],
            updated_at=row[6],
            importance=row[7],
            pinned=bool(row[8]),
        )

    @staticmethod
    def _relation_row(row) -> Relation:
        props = {}
        try:
            props = json.loads(row[4]) if row[4] else {}
        except (json.JSONDecodeError, TypeError):
            pass
        return Relation(
            source_id=row[0],
            target_id=row[1],
            relation_type=RelationType(row[2]),
            weight=row[3],
            properties=props,
            created_at=row[5],
        )

    def close(self) -> None:
        """Fecha a conexao com o banco SQLite."""
        self._db.close()

