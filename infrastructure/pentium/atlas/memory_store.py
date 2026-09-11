from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

from .episodic_model import (
    ClosureReason,
    EpisodeCategory,
    EpisodicEvidence,
    EpisodicSegment,
    MemoryProvenance,
    SegmentStatus,
)
from .memory_model import MemoryLayer, MemoryRecord


class MemoryStoreError(RuntimeError):
    pass


class MemoryStore:
    def __init__(self, path: Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._db = sqlite3.connect(self._path)
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA foreign_keys=ON")
            self._init_schema()
        except sqlite3.Error as exc:
            raise MemoryStoreError(str(exc)) from exc

    @property
    def path(self) -> Path:
        return self._path

    def schema_version(self) -> str:
        row = self._db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return str(row[0]) if row else "0"

    def _init_schema(self) -> None:
        self._db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
              memory_id TEXT PRIMARY KEY,
              layer TEXT NOT NULL,
              created_at TEXT NOT NULL,
              entity_id TEXT,
              content TEXT NOT NULL,
              importance REAL NOT NULL,
              confidence REAL NOT NULL,
              frequency INTEGER NOT NULL,
              origin TEXT NOT NULL,
              criticality REAL NOT NULL,
              pinned INTEGER NOT NULL,
              protected INTEGER NOT NULL,
              expires_at TEXT,
              dedupe_key TEXT
            )
        """)
        row = self._db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row is None:
            self._db.execute("INSERT INTO meta(key,value) VALUES('schema_version','1')")
            version = "1"
        else:
            version = str(row[0])
        if version not in {"1", "2"}:
            raise MemoryStoreError("memory schema_version incompatível")
        if version == "1":
            self._migrate_v1_to_v2()
        else:
            self._ensure_v2_schema()
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_mem_layer_entity ON memories(layer, entity_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_mem_dedupe ON memories(dedupe_key)")
        self._db.commit()

    def _migrate_v1_to_v2(self) -> None:
        with self._db:
            self._ensure_v2_schema(commit=False)
            self._db.execute("UPDATE meta SET value='2' WHERE key='schema_version'")

    def _ensure_v2_schema(self, *, commit: bool = True) -> None:
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS episodic_segments (
              segment_id TEXT PRIMARY KEY,
              generation_id TEXT NOT NULL,
              category TEXT NOT NULL,
              entity_id TEXT,
              semantic_key TEXT NOT NULL,
              opened_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              status TEXT NOT NULL,
              closure_reason TEXT,
              event_count INTEGER NOT NULL,
              byte_count INTEGER NOT NULL
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS episodic_evidence (
              event_id TEXT PRIMARY KEY,
              segment_id TEXT NOT NULL REFERENCES episodic_segments(segment_id) ON DELETE CASCADE,
              occurred_at TEXT NOT NULL,
              source TEXT NOT NULL,
              source_kind TEXT NOT NULL,
              content_reduced TEXT NOT NULL,
              reliability REAL NOT NULL,
              verified INTEGER NOT NULL,
              generation_id TEXT NOT NULL,
              dedupe_key TEXT,
              importance REAL NOT NULL,
              criticality REAL NOT NULL,
              entity_id TEXT
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS memory_provenance (
              segment_id TEXT PRIMARY KEY REFERENCES episodic_segments(segment_id),
              memory_id TEXT NOT NULL REFERENCES memories(memory_id),
              generation_id TEXT NOT NULL,
              sources TEXT NOT NULL,
              started_at TEXT NOT NULL,
              ended_at TEXT NOT NULL,
              evidence_count INTEGER NOT NULL
            )
        """)
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_episode_status ON episodic_segments(status, updated_at)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_episode_generation ON episodic_segments(generation_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_episode_entity ON episodic_segments(entity_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_evidence_segment ON episodic_evidence(segment_id, occurred_at)")
        if commit:
            self._db.commit()

    def save(self, record: MemoryRecord) -> None:
        try:
            self._db.execute("""
                INSERT OR REPLACE INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                record.memory_id, record.layer.value, record.created_at, record.entity_id,
                record.content, record.importance, record.confidence, record.frequency,
                record.origin, record.criticality, int(record.pinned), int(record.protected),
                record.expires_at, record.dedupe_key,
            ))
            self._db.commit()
        except sqlite3.Error as exc:
            raise MemoryStoreError(str(exc)) from exc

    def get(self, memory_id: str) -> MemoryRecord | None:
        row = self._db.execute("SELECT * FROM memories WHERE memory_id=?", (memory_id,)).fetchone()
        return self._memory_row(row) if row else None

    def list(self, *, limit: int = 100, layer: MemoryLayer | None = None,
             entity_id: str | None = None) -> tuple[MemoryRecord, ...]:
        if limit <= 0:
            raise ValueError("limit deve ser > 0")
        clauses, args = [], []
        if layer is not None:
            clauses.append("layer=?")
            args.append(layer.value)
        if entity_id is not None:
            clauses.append("entity_id=?")
            args.append(entity_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self._db.execute(
            f"SELECT * FROM memories{where} ORDER BY created_at DESC, memory_id LIMIT ?",
            (*args, limit),
        ).fetchall()
        return tuple(self._memory_row(row) for row in rows)

    def count(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM memories").fetchone()[0])

    def size_bytes(self) -> int:
        value = self._db.execute(
            "SELECT COALESCE(SUM(LENGTH(CAST(content AS BLOB))),0) FROM memories"
        ).fetchone()[0]
        return int(value or 0)

    def delete(self, memory_id: str) -> bool:
        cursor = self._db.execute("DELETE FROM memories WHERE memory_id=?", (memory_id,))
        self._db.commit()
        return cursor.rowcount > 0

    def consolidate(self, keeper: MemoryRecord, remove_ids) -> None:
        try:
            with self._db:
                self._write_memory(keeper)
                for memory_id in remove_ids:
                    if memory_id != keeper.memory_id:
                        self._db.execute("DELETE FROM memories WHERE memory_id=?", (memory_id,))
        except sqlite3.Error as exc:
            raise MemoryStoreError(str(exc)) from exc

    def save_segment(self, segment: EpisodicSegment) -> None:
        self._db.execute("""
            INSERT OR REPLACE INTO episodic_segments VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            segment.segment_id, segment.generation_id, segment.category.value,
            segment.entity_id, segment.semantic_key, segment.opened_at, segment.updated_at,
            segment.status.value,
            segment.closure_reason.value if segment.closure_reason else None,
            segment.event_count, segment.byte_count,
        ))
        self._db.commit()

    def get_segment(self, segment_id: str) -> EpisodicSegment | None:
        row = self._db.execute(
            "SELECT * FROM episodic_segments WHERE segment_id=?", (segment_id,)
        ).fetchone()
        return self._segment_row(row) if row else None

    def list_open_segments(self, limit: int = 100) -> tuple[EpisodicSegment, ...]:
        rows = self._db.execute(
            "SELECT * FROM episodic_segments WHERE status='open' ORDER BY updated_at,segment_id LIMIT ?",
            (limit,),
        ).fetchall()
        return tuple(self._segment_row(row) for row in rows)

    def list_closed_segments(self, limit: int = 100) -> tuple[EpisodicSegment, ...]:
        rows = self._db.execute(
            "SELECT * FROM episodic_segments WHERE status='closed' ORDER BY updated_at,segment_id LIMIT ?",
            (limit,),
        ).fetchall()
        return tuple(self._segment_row(row) for row in rows)

    def append_evidence(self, segment_id: str, evidence: EpisodicEvidence) -> bool:
        segment = self.get_segment(segment_id)
        if segment is None:
            raise MemoryStoreError("segmento inexistente")
        if segment.status is not SegmentStatus.OPEN:
            raise MemoryStoreError("segmento nao esta OPEN")
        if segment.generation_id != evidence.generation_id:
            raise MemoryStoreError("generation_id incompatível")
        payload_bytes = len(evidence.content_reduced.encode("utf-8"))
        with self._db:
            cursor = self._db.execute("""
                INSERT OR IGNORE INTO episodic_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                evidence.event_id, segment_id, evidence.occurred_at, evidence.source,
                evidence.source_kind, evidence.content_reduced, evidence.reliability,
                int(evidence.verified), evidence.generation_id, evidence.dedupe_key,
                evidence.importance, evidence.criticality, evidence.entity_id,
            ))
            if cursor.rowcount == 0:
                return False
            self._db.execute(
                "UPDATE episodic_segments SET updated_at=?,event_count=event_count+1,byte_count=byte_count+? WHERE segment_id=?",
                (evidence.occurred_at, payload_bytes, segment_id),
            )
        return True

    def list_evidence(self, segment_id: str) -> tuple[EpisodicEvidence, ...]:
        rows = self._db.execute(
            "SELECT event_id,occurred_at,source,source_kind,content_reduced,reliability,verified,generation_id,dedupe_key,importance,criticality,entity_id "
            "FROM episodic_evidence WHERE segment_id=? ORDER BY occurred_at,event_id",
            (segment_id,),
        ).fetchall()
        return tuple(
            EpisodicEvidence(
                row[0], row[1], row[2], row[3], row[4], row[5], bool(row[6]),
                row[7], row[8], row[9], row[10], row[11],
            )
            for row in rows
        )

    def close_segment(self, segment_id: str, reason: ClosureReason, updated_at: str) -> bool:
        segment = self.get_segment(segment_id)
        if segment is None:
            raise MemoryStoreError("segmento inexistente")
        if segment.status is SegmentStatus.CONSOLIDATED:
            return False
        if segment.status is SegmentStatus.CLOSED:
            return True
        self._db.execute(
            "UPDATE episodic_segments SET status='closed',closure_reason=?,updated_at=? WHERE segment_id=?",
            (reason.value, updated_at, segment_id),
        )
        self._db.commit()
        return True

    def get_provenance(self, segment_id: str) -> MemoryProvenance | None:
        row = self._db.execute(
            "SELECT segment_id,memory_id,generation_id,sources,started_at,ended_at,evidence_count "
            "FROM memory_provenance WHERE segment_id=?", (segment_id,),
        ).fetchone()
        if row is None:
            return None
        return MemoryProvenance(
            row[0], row[1], row[2], tuple(json.loads(row[3])), row[4], row[5], row[6]
        )

    def find_by_dedupe_key(self, dedupe_key: str | None) -> MemoryRecord | None:
        if not dedupe_key:
            return None
        row = self._db.execute(
            "SELECT * FROM memories WHERE dedupe_key=? ORDER BY created_at,memory_id LIMIT 1",
            (dedupe_key,),
        ).fetchone()
        return self._memory_row(row) if row else None

    def persist_consolidated(self, segment_id: str, record: MemoryRecord,
                             provenance: MemoryProvenance) -> bool:
        try:
            with self._db:
                row = self._db.execute(
                    "SELECT status FROM episodic_segments WHERE segment_id=?", (segment_id,),
                ).fetchone()
                if row is None:
                    raise MemoryStoreError("segmento inexistente")
                if row[0] == SegmentStatus.CONSOLIDATED.value:
                    return False
                if row[0] != SegmentStatus.CLOSED.value:
                    raise MemoryStoreError("segmento nao esta CLOSED")
                existing = self.find_by_dedupe_key(record.dedupe_key)
                if existing is None:
                    self._write_memory(record)
                    memory_id = record.memory_id
                else:
                    merged = replace(
                        existing,
                        frequency=existing.frequency + record.frequency,
                        importance=max(existing.importance, record.importance),
                        confidence=max(existing.confidence, record.confidence),
                        criticality=max(existing.criticality, record.criticality),
                        pinned=existing.pinned or record.pinned,
                        protected=existing.protected or record.protected,
                    )
                    self._db.execute(
                        "UPDATE memories SET frequency=?,importance=?,confidence=?,criticality=?,pinned=?,protected=? WHERE memory_id=?",
                        (merged.frequency, merged.importance, merged.confidence, merged.criticality,
                         int(merged.pinned), int(merged.protected), merged.memory_id),
                    )
                    memory_id = existing.memory_id
                bound = replace(provenance, memory_id=memory_id)
                self._db.execute(
                    "INSERT INTO memory_provenance VALUES (?,?,?,?,?,?,?)",
                    (bound.segment_id, bound.memory_id, bound.generation_id,
                     json.dumps(bound.sources, ensure_ascii=False), bound.started_at,
                     bound.ended_at, bound.evidence_count),
                )
                self._db.execute(
                    "UPDATE episodic_segments SET status='consolidated' WHERE segment_id=?",
                    (segment_id,),
                )
            return True
        except sqlite3.Error as exc:
            raise MemoryStoreError(str(exc)) from exc

    def close(self) -> None:
        self._db.close()

    def _write_memory(self, record: MemoryRecord) -> None:
        self._db.execute("""
            INSERT OR REPLACE INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            record.memory_id, record.layer.value, record.created_at, record.entity_id,
            record.content, record.importance, record.confidence, record.frequency,
            record.origin, record.criticality, int(record.pinned), int(record.protected),
            record.expires_at, record.dedupe_key,
        ))

    @staticmethod
    def _memory_row(row) -> MemoryRecord:
        return MemoryRecord(
            memory_id=row[0], layer=MemoryLayer(row[1]), created_at=row[2],
            entity_id=row[3], content=row[4], importance=row[5], confidence=row[6],
            frequency=row[7], origin=row[8], criticality=row[9], pinned=bool(row[10]),
            protected=bool(row[11]), expires_at=row[12], dedupe_key=row[13],
        )

    @staticmethod
    def _segment_row(row) -> EpisodicSegment:
        return EpisodicSegment(
            segment_id=row[0], generation_id=row[1], category=EpisodeCategory(row[2]),
            entity_id=row[3], semantic_key=row[4], opened_at=row[5], updated_at=row[6],
            status=SegmentStatus(row[7]),
            closure_reason=ClosureReason(row[8]) if row[8] else None,
            event_count=row[9], byte_count=row[10],
        )
