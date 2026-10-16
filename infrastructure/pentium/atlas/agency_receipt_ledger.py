"""CP28 durable local receipt ledger.

Stores facts about specialist work. Never executes actions or grants capabilities.
It is intentionally not wired to the production worker until release gates pass.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", flags=re.ASCII)
_TAG = re.compile(r"<[^>]+>")
_ACTION_MARKERS = ("<script", "javascript:", "ghp_", "sk-proj-", "bearer ")


class AgencyReceiptLedger:
    """One SQLite connection per caller. For concurrency use distinct instances.

    Idempotent inserts bind an immutable task/worker/trace to the unique key.
    Terminal receipts never transition back to active work.
    """

    VALID_STATES = frozenset(
        {"PENDING", "PROCESSING", "COMPLETED", "FAILED", "CANCELLED"}
    )
    MAX_SUMMARY_LEN = 500
    MAX_RETRIES = 10
    _ALLOWED = {
        "PENDING": frozenset({"PROCESSING", "FAILED", "CANCELLED"}),
        "PROCESSING": frozenset({"COMPLETED", "FAILED", "CANCELLED"}),
        "FAILED": frozenset({"PENDING"}),
        "COMPLETED": frozenset(),
        "CANCELLED": frozenset(),
    }

    def __init__(self, db_path: str):
        if not isinstance(db_path, str) or not db_path:
            raise ValueError("database_path_invalid")
        if db_path != ":memory:":
            path = Path(db_path)
            if not path.is_absolute() or ".." in path.parts or path.is_symlink():
                raise ValueError("database_path_untrusted")
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, timeout=15.0)
        self._conn.execute("PRAGMA busy_timeout=15000")
        if db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._create_table()

    def _create_table(self) -> None:
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS receipts (
                idempotency_key TEXT NOT NULL PRIMARY KEY,
                task_id TEXT NOT NULL,
                specialist_id TEXT NOT NULL,
                state TEXT NOT NULL
                  CHECK (state IN ('PENDING','PROCESSING','COMPLETED','FAILED','CANCELLED')),
                correlation_id TEXT,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                retry_count INTEGER NOT NULL DEFAULT 0 CHECK(retry_count >= 0),
                last_started_retry INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 3 CHECK(max_retries BETWEEN 0 AND 10),
                error_message TEXT
            )"""
        )
        self._conn.commit()

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _identifier(value: Any, field: str) -> str:
        if type(value) is not str or not _ID.fullmatch(value):
            raise ValueError(field + "_invalid")
        return value

    @classmethod
    def _validate_idempotency_key(cls, value: Any) -> None:
        cls._identifier(value, "idempotency_key")

    @classmethod
    def _validate_task_id(cls, value: Any) -> None:
        cls._identifier(value, "task_id")

    @classmethod
    def _validate_specialist_id(cls, value: Any) -> None:
        cls._identifier(value, "specialist_id")

    @classmethod
    def _validate_state(cls, value: Any) -> None:
        if type(value) is not str or value not in cls.VALID_STATES:
            raise ValueError("state_invalid")

    @classmethod
    def _sanitize(cls, value: Any, *, field: str, allow_empty: bool) -> str:
        if type(value) is not str:
            raise ValueError(field + "_invalid")
        lowered = value.lower()
        if any(token in lowered for token in _ACTION_MARKERS):
            raise ValueError(field + "_untrusted")
        clean = _TAG.sub("", value).replace("\x00", "").strip()
        if (not allow_empty and not clean) or len(clean) > cls.MAX_SUMMARY_LEN:
            raise ValueError(field + "_invalid_length")
        if any(ord(ch) < 32 and ch not in "\n\t" for ch in clean):
            raise ValueError(field + "_control_character")
        return clean

    @classmethod
    def _validate_summary(cls, value: Any) -> None:
        cls._sanitize(value, field="summary", allow_empty=False)

    @classmethod
    def _sanitize_summary(cls, value: Any) -> str:
        return cls._sanitize(value, field="summary", allow_empty=False)

    def _reject_untrusted(self, summary: str) -> None:
        self._sanitize_summary(summary)

    def insert(
        self,
        idempotency_key: str,
        task_id: str,
        specialist_id: str,
        correlation_id: Optional[str],
        summary: str,
        state: str = "PENDING",
        max_retries: int = 3,
    ) -> bool:
        self._validate_idempotency_key(idempotency_key)
        self._validate_task_id(task_id)
        self._validate_specialist_id(specialist_id)
        if correlation_id is not None:
            self._identifier(correlation_id, "correlation_id")
        self._validate_state(state)
        if state != "PENDING":
            raise ValueError("new_receipt_must_be_pending")
        if type(max_retries) is not int or not 0 <= max_retries <= self.MAX_RETRIES:
            raise ValueError("max_retries_invalid")
        clean = self._sanitize_summary(summary)
        now = self._timestamp()
        try:
            self._conn.execute(
                """INSERT INTO receipts
                   (idempotency_key,task_id,specialist_id,state,
                    correlation_id,summary,created_at,updated_at,
                    retry_count,max_retries,error_message)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (idempotency_key, task_id, specialist_id, "PENDING",
                 correlation_id, clean, now, now, 0, max_retries, None),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            self._conn.rollback()
            existing = self.get(idempotency_key)
            if existing is None:
                raise
            immutable = (
                existing["task_id"], existing["specialist_id"],
                existing["correlation_id"], existing["summary"],
                existing["max_retries"],
            )
            incoming = (task_id, specialist_id, correlation_id, clean, max_retries)
            if immutable != incoming:
                raise ValueError("idempotency_conflict")
            return False

    def get(self, idempotency_key: str) -> Optional[dict[str, Any]]:
        self._validate_idempotency_key(idempotency_key)
        fields = (
            "idempotency_key", "task_id", "specialist_id", "state",
            "correlation_id", "summary", "created_at", "updated_at",
            "retry_count", "max_retries", "error_message",
        )
        cursor = self._conn.execute(
            "SELECT " + ",".join(fields) +
            " FROM receipts WHERE idempotency_key=?", (idempotency_key,)
        )
        row = cursor.fetchone()
        return dict(zip(fields, row)) if row is not None else None

    def update_state(self, idempotency_key: str, new_state: str) -> bool:
        self._validate_idempotency_key(idempotency_key)
        self._validate_state(new_state)
        current = self.get(idempotency_key)
        if current is None:
            return False
        old = current["state"]
        if new_state not in self._ALLOWED[old]:
            raise ValueError("state_transition_forbidden")
        if old == "FAILED" and new_state == "PENDING":
            if current["retry_count"] <= 0:
                raise ValueError("retry_not_recorded")
        if old == "FAILED":
            cur = self._conn.execute(
                """UPDATE receipts
                   SET state=?,updated_at=?,last_started_retry=retry_count
                   WHERE idempotency_key=? AND state=? AND retry_count=?
                     AND retry_count > last_started_retry""",
                (new_state, self._timestamp(), idempotency_key,
                 old, current["retry_count"]),
            )
        else:
            cur = self._conn.execute(
                """UPDATE receipts SET state=?,updated_at=?
                   WHERE idempotency_key=? AND state=? AND retry_count=?""",
                (new_state, self._timestamp(), idempotency_key,
                 old, current["retry_count"]),
            )
        self._conn.commit()
        if cur.rowcount != 1:
            raise ValueError("concurrent_state_transition")
        return True

    def increment_retry(self, idempotency_key: str) -> bool:
        self._validate_idempotency_key(idempotency_key)
        cur = self._conn.execute(
            """UPDATE receipts SET retry_count=retry_count+1,updated_at=?
               WHERE idempotency_key=? AND state='FAILED'
                 AND retry_count < max_retries""",
            (self._timestamp(), idempotency_key),
        )
        self._conn.commit()
        return cur.rowcount == 1

    def set_error(self, idempotency_key: str, error_message: str) -> bool:
        self._validate_idempotency_key(idempotency_key)
        if type(error_message) is not str:
            raise ValueError("error_message_invalid")
        clean = self._sanitize(
            error_message[:self.MAX_SUMMARY_LEN],
            field="error_message", allow_empty=False,
        )
        current = self.get(idempotency_key)
        if current is None:
            return False
        if current["state"] not in ("PENDING", "PROCESSING"):
            raise ValueError("terminal_receipt_immutable")
        cur = self._conn.execute(
            """UPDATE receipts SET state='FAILED',error_message=?,updated_at=?
               WHERE idempotency_key=? AND state=?""",
            (clean, self._timestamp(), idempotency_key, current["state"]),
        )
        self._conn.commit()
        if cur.rowcount != 1:
            raise ValueError("concurrent_error_transition")
        return True

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
