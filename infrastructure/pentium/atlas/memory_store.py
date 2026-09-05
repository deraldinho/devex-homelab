from __future__ import annotations

import sqlite3
from pathlib import Path

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

    def _init_schema(self) -> None:
        self._db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        row = self._db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row is not None and row[0] != "1":
            raise MemoryStoreError("memory schema_version incompatível")
        self._db.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version','1')")
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
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_mem_layer_entity ON memories(layer, entity_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_mem_dedupe ON memories(dedupe_key)")
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
        return self._row(row) if row else None

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
        return tuple(self._row(row) for row in rows)

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

    def close(self) -> None:
        self._db.close()

    @staticmethod
    def _row(row) -> MemoryRecord:
        return MemoryRecord(
            memory_id=row[0],
            layer=MemoryLayer(row[1]),
            created_at=row[2],
            entity_id=row[3],
            content=row[4],
            importance=row[5],
            confidence=row[6],
            frequency=row[7],
            origin=row[8],
            criticality=row[9],
            pinned=bool(row[10]),
            protected=bool(row[11]),
            expires_at=row[12],
            dedupe_key=row[13],
        )
