from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
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
from .memory_coherence_gate import same_evidence_claim
from .memory_ingress import IngressError, MemoryAttestation, OperatorInstruction


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
            self._db.execute("INSERT INTO meta(key,value) VALUES('schema_version','3')")
            version = "3"
        else:
            version = str(row[0])
        if version not in {"1", "2", "3"}:
            raise MemoryStoreError("memory schema_version incompatível")
        if version == "1":
            self._migrate_v1_to_v2()
            self._migrate_v2_to_v3()
        elif version == "2":
            self._migrate_v2_to_v3()
        else:
            self._ensure_v2_schema()
            self._ensure_v3_schema()
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_mem_layer_entity ON memories(layer, entity_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_mem_dedupe ON memories(dedupe_key)")
        # Operational receipts are deliberately NOT cognitive MemoryRecord entries.
        # Additive compatible table: v1/v2/v3 databases remain readable.
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS agency_failure_receipts (
                event_id TEXT PRIMARY KEY,
                schema_version INTEGER NOT NULL CHECK(schema_version=1),
                task_id TEXT NOT NULL,
                project TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                attempt INTEGER NOT NULL CHECK(attempt > 0),
                created_at TEXT NOT NULL
            )
        """)
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_agency_failure_task ON agency_failure_receipts(task_id,created_at)")
        # CP-MEM-P1: signed ingress attestations (additive, never cognitive
        # MemoryRecord entries) and separately stored operator instructions.
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS memory_attestations (
                subject_id TEXT PRIMARY KEY,
                schema_version INTEGER NOT NULL CHECK(schema_version=1),
                ingress TEXT NOT NULL,
                kind TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                nonce TEXT NOT NULL,
                signature TEXT NOT NULL
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS operator_instructions (
                instruction_id TEXT PRIMARY KEY,
                schema_version INTEGER NOT NULL CHECK(schema_version=1),
                operator_id TEXT NOT NULL,
                content TEXT NOT NULL,
                approved_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                signature TEXT NOT NULL
            )
        """)
        self._db.commit()

    def _migrate_v1_to_v2(self) -> None:
        with self._db:
            self._ensure_v2_schema(commit=False)
            self._db.execute("UPDATE meta SET value='2' WHERE key='schema_version'")

    def _migrate_v2_to_v3(self) -> None:
        with self._db:
            self._ensure_v2_schema(commit=False)
            self._ensure_v3_schema(commit=False)
            self._db.execute("UPDATE meta SET value='3' WHERE key='schema_version'")

    def _ensure_v3_schema(self, *, commit: bool = True) -> None:
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
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_entity_type ON entity_nodes(entity_type)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_entity_name ON entity_nodes(name)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_rel_source ON entity_relations(source_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_rel_target ON entity_relations(target_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_rel_type ON entity_relations(relation_type)")
        if commit:
            self._db.commit()

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
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS memory_links (
              source_id TEXT NOT NULL,
              target_id TEXT NOT NULL,
              relation TEXT NOT NULL,
              weight REAL NOT NULL DEFAULT 1.0,
              created_at TEXT NOT NULL,
              PRIMARY KEY (source_id, target_id, relation)
            )
        """)
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_episode_status ON episodic_segments(status, updated_at)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_episode_generation ON episodic_segments(generation_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_episode_entity ON episodic_segments(entity_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_evidence_segment ON episodic_evidence(segment_id, occurred_at)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_mem_links_target ON memory_links(target_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_mem_links_source ON memory_links(source_id)")

        existing_cols = {row[1] for row in self._db.execute("PRAGMA table_info(memories)").fetchall()}
        for col, col_type in [
            ("message_id", "TEXT"),
            ("reply_to_id", "TEXT"),
            ("thread_id", "TEXT"),
            ("channel_id", "TEXT"),
            ("tags", "TEXT"),
        ]:
            if col not in existing_cols:
                self._db.execute(f"ALTER TABLE memories ADD COLUMN {col} {col_type}")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_mem_msg_id ON memories(message_id)")

        if commit:
            self._db.commit()

    def save(self, record: MemoryRecord) -> None:
        try:
            tags_json = json.dumps(list(record.tags)) if getattr(record, "tags", ()) else None
            self._db.execute("""
                INSERT OR REPLACE INTO memories (
                    memory_id, layer, created_at, entity_id, content, importance,
                    confidence, frequency, origin, criticality, pinned, protected,
                    expires_at, dedupe_key, message_id, reply_to_id, thread_id, channel_id, tags
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                record.memory_id, record.layer.value, record.created_at, record.entity_id,
                record.content, record.importance, record.confidence, record.frequency,
                record.origin, record.criticality, int(record.pinned), int(record.protected),
                record.expires_at, record.dedupe_key,
                getattr(record, "message_id", None),
                getattr(record, "reply_to_id", None),
                getattr(record, "thread_id", None),
                getattr(record, "channel_id", None),
                tags_json,
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
        self._db.execute("DELETE FROM memory_attestations WHERE subject_id=?", (memory_id,))
        self._db.commit()
        return cursor.rowcount > 0

    def consolidate(self, keeper: MemoryRecord, remove_ids) -> None:
        try:
            with self._db:
                self._write_memory(keeper)
                for memory_id in remove_ids:
                    if memory_id != keeper.memory_id:
                        self._db.execute("DELETE FROM memories WHERE memory_id=?", (memory_id,))
                        self._db.execute(
                            "DELETE FROM memory_attestations WHERE subject_id=?", (memory_id,))
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

    def find_matching_claim(self, record: MemoryRecord) -> MemoryRecord | None:
        """Match actual source/content/type, never dedupe_key alone."""
        if not record.dedupe_key:
            return None
        rows = self._db.execute(
            "SELECT * FROM memories WHERE dedupe_key=? ORDER BY created_at,memory_id",
            (record.dedupe_key,),
        ).fetchall()
        for row in rows:
            existing = self._memory_row(row)
            if same_evidence_claim(existing, record):
                return existing
        return None

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
                existing = self.find_matching_claim(record)
                if existing is None:
                    self._write_memory(record)
                    memory_id = record.memory_id
                else:
                    merged = replace(
                        existing,
                        frequency=existing.frequency + record.frequency,
                        importance=min(existing.importance, record.importance),
                        confidence=min(existing.confidence, record.confidence),
                        criticality=min(existing.criticality, record.criticality),
                        pinned=existing.pinned,
                        protected=existing.protected,
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

    def link_memories(self, source_id: str, target_id: str, relation: str, weight: float = 1.0, created_at: str | None = None) -> None:
        if not source_id or not target_id or not relation:
            return
        if created_at is None:
            from datetime import datetime, timezone
            created_at = datetime.now(timezone.utc).isoformat()
        try:
            self._db.execute("""
                INSERT OR REPLACE INTO memory_links (source_id, target_id, relation, weight, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (str(source_id).strip(), str(target_id).strip(), str(relation).strip(), float(weight), str(created_at)))
            self._db.commit()
        except sqlite3.Error as exc:
            raise MemoryStoreError(str(exc)) from exc

    def get_by_message_id(self, message_id: str) -> MemoryRecord | None:
        if not message_id:
            return None
        row = self._db.execute("SELECT * FROM memories WHERE message_id=? LIMIT 1", (str(message_id).strip(),)).fetchone()
        return self._memory_row(row) if row else None

    def get_connected_thread(self, message_id: str, max_depth: int = 6) -> tuple[MemoryRecord, ...]:
        if not message_id:
            return ()
        visited = set()
        current_id = str(message_id).strip()
        records = []

        for _ in range(max_depth):
            if not current_id or current_id in visited:
                break
            visited.add(current_id)
            rec = self.get_by_message_id(current_id)
            if rec is not None:
                records.append(rec)
                current_id = rec.reply_to_id
            else:
                row = self._db.execute(
                    "SELECT target_id FROM memory_links WHERE source_id=? AND relation IN ('reply_of', 'reply_to') LIMIT 1",
                    (current_id,)
                ).fetchone()
                current_id = row[0] if row else None

        records.reverse()
        return tuple(records)

    def get_associated_memories(self, identifier: str, relation: str | None = None, limit: int = 10) -> tuple[MemoryRecord, ...]:
        if not identifier:
            return ()
        query = "SELECT target_id FROM memory_links WHERE source_id=?"
        params = [str(identifier).strip()]
        if relation:
            query += " AND relation=?"
            params.append(str(relation).strip())
        query += " ORDER BY weight DESC LIMIT ?"
        params.append(limit)

        target_ids = [r[0] for r in self._db.execute(query, tuple(params)).fetchall()]
        results = []
        for tid in target_ids:
            rec = self.get(tid) or self.get_by_message_id(tid)
            if rec and rec not in results:
                results.append(rec)
        return tuple(results)

    def record_agency_failure_receipt(
        self, *, event_id: str, task_id: str, project: str,
        reason_code: str, attempt: int, created_at: str,
    ) -> bool:
        """Persist only code-derived failure metadata; never prompts or exception bodies.

        True means inserted. Exact replay is False; conflicting replay raises.
        Intentionally separate from memories/episodic evidence and LLM retrieval.
        """
        identifier = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
        project_pattern = re.compile(r"[a-z0-9][a-z0-9-]{0,79}")
        if (not isinstance(event_id, str) or not identifier.fullmatch(event_id)
                or not isinstance(task_id, str) or not identifier.fullmatch(task_id)
                or not isinstance(project, str) or not project_pattern.fullmatch(project)):
            raise ValueError("failure_receipt_identifier_invalid")
        if (task_id.lower().startswith(("ghp_", "github_pat_", "sk-", "nvapi-"))
                or event_id.lower().startswith(("ghp_", "github_pat_", "sk-", "nvapi-"))):
            raise ValueError("failure_receipt_secret_identifier")
        if reason_code not in {"worker_unavailable", "invalid_worker_result"}:
            raise ValueError("failure_receipt_reason_invalid")
        if type(attempt) is not int or not 1 <= attempt <= 10000:
            raise ValueError("failure_receipt_attempt_invalid")
        if not isinstance(created_at, str):
            raise ValueError("failure_receipt_timestamp_invalid")
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if dt.tzinfo is None or dt.utcoffset() is None:
                raise ValueError("failure_receipt_timezone_required")
            at = dt.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError) as exc:
            raise ValueError("failure_receipt_timestamp_invalid") from exc
        value = (event_id, 1, task_id, project, reason_code, attempt, at)
        try:
            with self._db:
                cursor = self._db.execute(
                    """INSERT OR IGNORE INTO agency_failure_receipts
                    (event_id,schema_version,task_id,project,reason_code,attempt,created_at)
                    VALUES (?,?,?,?,?,?,?)""", value)
                if cursor.rowcount:
                    return True
                existing = self._db.execute(
                    """SELECT event_id,schema_version,task_id,project,reason_code,attempt,created_at
                    FROM agency_failure_receipts WHERE event_id=?""",
                    (event_id,),
                ).fetchone()
                if tuple(existing or ()) != value:
                    raise MemoryStoreError("failure_receipt_conflicting_replay")
                return False
        except sqlite3.Error as exc:
            raise MemoryStoreError("failure_receipt_storage_unavailable") from exc

    def list_agency_failure_receipts(
        self, *, task_id: str | None = None, limit: int = 100,
    ) -> tuple[dict[str, object], ...]:
        """Operational diagnostics only: never included in cognitive retrieval."""
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("failure_receipt_limit_invalid")
        if task_id is not None and (not isinstance(task_id, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", task_id)):
            raise ValueError("failure_receipt_task_id_invalid")
        where = " WHERE task_id=?" if task_id is not None else ""
        args = (task_id, limit) if task_id is not None else (limit,)
        try:
            rows = self._db.execute(
                """SELECT event_id,schema_version,task_id,project,reason_code,attempt,created_at
                   FROM agency_failure_receipts""" + where + " ORDER BY created_at DESC,event_id LIMIT ?",
                args,
            ).fetchall()
        except sqlite3.Error as exc:
            raise MemoryStoreError("failure_receipt_read_unavailable") from exc
        keys = ("event_id", "schema_version", "task_id", "project",
                "reason_code", "attempt", "created_at")
        return tuple(dict(zip(keys, row)) for row in rows)

    def prune_agency_failure_receipts(
        self, *, before_utc: str, max_delete: int = 1000,
    ) -> int:
        """Explicit bounded retention. No automatic deletion of audit evidence."""
        if type(max_delete) is not int or not 1 <= max_delete <= 1000:
            raise ValueError("failure_receipt_prune_limit_invalid")
        if not isinstance(before_utc, str):
            raise ValueError("failure_receipt_retention_date_invalid")
        try:
            instant = datetime.fromisoformat(before_utc.replace("Z", "+00:00"))
            if instant.tzinfo is None or instant.utcoffset() is None:
                raise ValueError("timezone_required")
            cutoff = instant.astimezone(timezone.utc).isoformat()
        except ValueError as exc:
            raise ValueError("failure_receipt_retention_date_invalid") from exc
        try:
            with self._db:
                deleted = self._db.execute(
                    """DELETE FROM agency_failure_receipts WHERE event_id IN
                       (SELECT event_id FROM agency_failure_receipts
                        WHERE created_at < ? ORDER BY created_at,event_id LIMIT ?)""",
                    (cutoff, max_delete),
                )
                return deleted.rowcount
        except sqlite3.Error as exc:
            raise MemoryStoreError("failure_receipt_prune_unavailable") from exc

    def save_attestation(self, attestation: MemoryAttestation) -> bool:
        """Persist a signed ingress attestation, keyed by its subject memory.

        True means inserted. Exact replay is False; conflicting replay raises.
        Signature verification belongs to the trusted ingress, not the store.
        """
        if not isinstance(attestation, MemoryAttestation):
            raise MemoryStoreError("attestation_invalid")
        value = (
            attestation.subject_id, attestation.schema_version, attestation.ingress,
            attestation.kind, attestation.content_sha256, attestation.issued_at,
            attestation.nonce, attestation.signature,
        )
        try:
            with self._db:
                cursor = self._db.execute(
                    """INSERT OR IGNORE INTO memory_attestations
                    (subject_id,schema_version,ingress,kind,content_sha256,issued_at,nonce,signature)
                    VALUES (?,?,?,?,?,?,?,?)""", value)
                if cursor.rowcount:
                    return True
                existing = self._db.execute(
                    """SELECT subject_id,schema_version,ingress,kind,content_sha256,issued_at,nonce,signature
                    FROM memory_attestations WHERE subject_id=?""",
                    (attestation.subject_id,),
                ).fetchone()
                if tuple(existing or ()) != value:
                    raise MemoryStoreError("attestation_conflicting_replay")
                return False
        except sqlite3.Error as exc:
            raise MemoryStoreError("attestation_store_unavailable") from exc

    def get_attestation(self, memory_id: str) -> MemoryAttestation | None:
        """Load a stored attestation. A corrupt row is treated as absent."""
        if not isinstance(memory_id, str) or not memory_id:
            return None
        row = self._db.execute(
            """SELECT schema_version,ingress,subject_id,kind,content_sha256,issued_at,nonce,signature
            FROM memory_attestations WHERE subject_id=?""", (memory_id,),
        ).fetchone()
        if row is None:
            return None
        try:
            return MemoryAttestation(
                schema_version=row[0], ingress=row[1], subject_id=row[2], kind=row[3],
                content_sha256=row[4], issued_at=row[5], nonce=row[6], signature=row[7],
            )
        except (IngressError, ValueError):
            return None

    def save_operator_instruction(self, instruction: OperatorInstruction) -> bool:
        """Persist an operator-approved instruction in its own, non-cognitive table.

        The caller (OperatorAuthority) is responsible for verifying the signed
        approval before reaching this method. Exact replay is False; conflicting
        replay raises.
        """
        if not isinstance(instruction, OperatorInstruction):
            raise MemoryStoreError("operator_instruction_invalid")
        value = (
            instruction.instruction_id, instruction.schema_version, instruction.operator_id,
            instruction.content, instruction.approved_at, instruction.created_at,
            instruction.signature,
        )
        try:
            with self._db:
                cursor = self._db.execute(
                    """INSERT OR IGNORE INTO operator_instructions
                    (instruction_id,schema_version,operator_id,content,approved_at,created_at,signature)
                    VALUES (?,?,?,?,?,?,?)""", value)
                if cursor.rowcount:
                    return True
                existing = self._db.execute(
                    """SELECT instruction_id,schema_version,operator_id,content,approved_at,created_at,signature
                    FROM operator_instructions WHERE instruction_id=?""",
                    (instruction.instruction_id,),
                ).fetchone()
                if tuple(existing or ()) != value:
                    raise MemoryStoreError("operator_instruction_conflicting_replay")
                return False
        except sqlite3.Error as exc:
            raise MemoryStoreError("operator_instruction_store_unavailable") from exc

    def get_operator_instruction(self, instruction_id: str) -> OperatorInstruction | None:
        if not isinstance(instruction_id, str) or not instruction_id:
            return None
        row = self._db.execute(
            """SELECT schema_version,instruction_id,operator_id,content,approved_at,created_at,signature
            FROM operator_instructions WHERE instruction_id=?""", (instruction_id,),
        ).fetchone()
        return self._instruction_row(row) if row else None

    def list_operator_instructions(self, limit: int = 100) -> tuple[OperatorInstruction, ...]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("operator_instruction_limit_invalid")
        rows = self._db.execute(
            """SELECT schema_version,instruction_id,operator_id,content,approved_at,created_at,signature
            FROM operator_instructions ORDER BY approved_at DESC,instruction_id LIMIT ?""",
            (limit,),
        ).fetchall()
        return tuple(self._instruction_row(row) for row in rows)

    @staticmethod
    def _instruction_row(row) -> OperatorInstruction:
        return OperatorInstruction(
            schema_version=row[0], instruction_id=row[1], operator_id=row[2],
            content=row[3], approved_at=row[4], created_at=row[5], signature=row[6],
        )

    def close(self) -> None:
        self._db.close()

    def _write_memory(self, record: MemoryRecord) -> None:
        tags_json = json.dumps(list(record.tags)) if getattr(record, "tags", ()) else None
        self._db.execute("""
            INSERT OR REPLACE INTO memories (
                memory_id, layer, created_at, entity_id, content, importance,
                confidence, frequency, origin, criticality, pinned, protected,
                expires_at, dedupe_key, message_id, reply_to_id, thread_id, channel_id, tags
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            record.memory_id, record.layer.value, record.created_at, record.entity_id,
            record.content, record.importance, record.confidence, record.frequency,
            record.origin, record.criticality, int(record.pinned), int(record.protected),
            record.expires_at, record.dedupe_key,
            getattr(record, "message_id", None),
            getattr(record, "reply_to_id", None),
            getattr(record, "thread_id", None),
            getattr(record, "channel_id", None),
            tags_json,
        ))

    @staticmethod
    def _memory_row(row) -> MemoryRecord:
        tags = ()
        if len(row) > 18 and row[18]:
            try:
                tags = tuple(json.loads(row[18]))
            except Exception:
                pass
        return MemoryRecord(
            memory_id=row[0], layer=MemoryLayer(row[1]), created_at=row[2],
            entity_id=row[3], content=row[4], importance=row[5], confidence=row[6],
            frequency=row[7], origin=row[8], criticality=row[9], pinned=bool(row[10]),
            protected=bool(row[11]), expires_at=row[12], dedupe_key=row[13],
            message_id=row[14] if len(row) > 14 else None,
            reply_to_id=row[15] if len(row) > 15 else None,
            thread_id=row[16] if len(row) > 16 else None,
            channel_id=row[17] if len(row) > 17 else None,
            tags=tags,
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
