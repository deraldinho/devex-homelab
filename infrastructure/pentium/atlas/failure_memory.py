"""Atlas Sentry P0: isolated, typed failure lessons learned only after verified recovery.

No model calls, capability authority, tool dispatch, executor, user prompt
injection, or writes to MemoryStore. A trusted owner injects observations
and an independent verification callback. This module is *not* a remediation
engine: all returned lessons are untrusted, read-only advisory evidence.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from .health_supervisor import SupervisorSnapshot
from .health_supervisor_model import ComponentHealthState as State


class FailureMemoryError(RuntimeError):
    """Fail-closed recovery/verification invariant."""


_KIND_BY_HEALTH = {
    State.FAILED: "process_failure",
    State.DISCONNECTED: "disconnected",
    State.STALE: "stale",
    State.DEGRADED: "degraded",
}
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")
_IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_SECRET = re.compile(
    r"(?i)(?:bearer\s+\S+|(?:token|secret|password|api[_-]?key)\s*[:=]\s*\S+|"
    r"(?:sk-[a-z0-9_-]{8,}|nvapi-[a-z0-9_-]{8,}|ghp_[a-z0-9]{8,}))"
)
_INDIRECT_COMMAND = re.compile(
    r"(?i)(?:ignore previous instructions|ignore system policy|"
    r"bypass (?:security|approval|permissions)|role\s*:\s*system|\[system\])"
)


def _utc(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("timestamp_invalid")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp_invalid") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timezone_required")
    return dt.astimezone(timezone.utc).isoformat()


def _safe_text(value: str, name: str, limit: int) -> str:
    if (not isinstance(value, str) or not value.strip()
            or len(value) > limit or any(ord(ch) < 32 for ch in value)
            or _SECRET.search(value) or _INDIRECT_COMMAND.search(value)):
        raise ValueError(name + "_invalid")
    return value.strip()


def _refs(value: tuple[str, ...], *, required: bool = False) -> tuple[str, ...]:
    if (not isinstance(value, (tuple, list)) or len(value) > 8
            or (required and not value)
            or any(not isinstance(v, str) or not _REF.fullmatch(v)
                   or _SECRET.search(v) for v in value)):
        raise ValueError("evidence_refs_invalid")
    return tuple(dict.fromkeys(value))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FailureMemory:
    """Standalone SQLite playbook; never shares primary Atlas memory storage."""

    def __init__(self, path: Path):
        self.path = Path(path)
        if self.path.is_symlink():
            raise FailureMemoryError("refusing_symlink_database")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path), timeout=5)
        try:
            self._db.execute("PRAGMA foreign_keys=ON")
            version = self._db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise FailureMemoryError("unsupported_schema_version")
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript("""
            CREATE TABLE IF NOT EXISTS failure_incidents (
                incident_id TEXT PRIMARY KEY,
                component TEXT NOT NULL,
                kind TEXT NOT NULL,
                signature TEXT NOT NULL,
                opened_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('open','recovered')),
                healthy_streak INTEGER NOT NULL DEFAULT 0,
                resolved_at TEXT,
                evidence_json TEXT NOT NULL,
                recovery_evidence_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_failure_active
              ON failure_incidents(component,kind) WHERE state='open';
            CREATE TABLE IF NOT EXISTS failure_lessons (
                lesson_id TEXT PRIMARY KEY,
                source_incident_id TEXT NOT NULL UNIQUE
                  REFERENCES failure_incidents(incident_id),
                kind TEXT NOT NULL,
                signature TEXT NOT NULL,
                cause TEXT NOT NULL,
                correction TEXT NOT NULL,
                verification_refs_json TEXT NOT NULL,
                verified_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_lesson_lookup
              ON failure_lessons(kind, signature, expires_at);
            """)
            self._db.execute("PRAGMA user_version=1")
            self._db.commit()
        except BaseException:
            self._db.close()
            raise

    def close(self) -> None:
        self._db.close()

    @staticmethod
    def _incident(row) -> dict | None:
        if row is None:
            return None
        return {
            "incident_id": row[0], "component": row[1], "kind": row[2],
            "signature": row[3], "opened_at": row[4], "last_seen_at": row[5],
            "state": row[6], "healthy_streak": row[7],
            "resolved_at": row[8], "evidence_refs": tuple(json.loads(row[9])),
            "recovery_evidence_refs": tuple(json.loads(row[10])),
        }

    def get_incident(self, incident_id: str) -> dict | None:
        if not isinstance(incident_id, str) or not _IDENT.fullmatch(incident_id):
            return None
        row = self._db.execute("SELECT * FROM failure_incidents WHERE incident_id=?",
                               (incident_id,)).fetchone()
        return self._incident(row)

    def open_incidents(self) -> tuple[dict, ...]:
        rows = self._db.execute(
            "SELECT * FROM failure_incidents WHERE state='open' ORDER BY opened_at,incident_id"
        ).fetchall()
        return tuple(self._incident(row) for row in rows)

    def stats(self) -> dict:
        return {
            "open_incidents": self._db.execute(
                "SELECT COUNT(*) FROM failure_incidents WHERE state='open'"
            ).fetchone()[0],
            "recovered_incidents": self._db.execute(
                "SELECT COUNT(*) FROM failure_incidents WHERE state='recovered'"
            ).fetchone()[0],
            "lessons": self._db.execute("SELECT COUNT(*) FROM failure_lessons").fetchone()[0],
        }

    def observe_snapshot(self, snapshot: SupervisorSnapshot) -> tuple[dict, ...]:
        """Detect failures and verify service recovery through 2 fresh passes.

        The snapshot is produced by the existing independent health supervisor.
        A healthy transition is not evidence of a successful *agent repair*.
        That requires record_verified_lesson() and an external verifier.
        """
        if not isinstance(snapshot, SupervisorSnapshot):
            raise ValueError("supervisor_snapshot_required")
        at = _utc(snapshot.generated_at)
        result = []
        with self._db:
            for comp in snapshot.components:
                component = _safe_text(comp.component_id, "component", 128)
                evidence = _refs(comp.evidence_refs)
                # Durable high-watermark prevents replayed old failure snapshots
                # reopening incidents that were already verified as recovered.
                latest = self._db.execute(
                    "SELECT MAX(last_seen_at) FROM failure_incidents WHERE component=?",
                    (component,),
                ).fetchone()[0]
                if latest is not None and at <= latest:
                    continue
                if comp.state in _KIND_BY_HEALTH:
                    # Any renewed failure breaks the *entire* component's
                    # consecutive healthy sequence, regardless of failure kind.
                    self._db.execute(
                        """UPDATE failure_incidents SET healthy_streak=0,
                           recovery_evidence_json='[]',last_seen_at=?
                           WHERE component=? AND state='open' AND last_seen_at<?""",
                        (at, component, at),
                    )
                    kind = _KIND_BY_HEALTH[comp.state]
                    signature = component + ":" + kind
                    row = self._db.execute(
                        "SELECT * FROM failure_incidents WHERE component=? AND kind=? AND state='open'",
                        (component, kind),
                    ).fetchone()
                    old = self._incident(row)
                    if old:
                        if at <= old["last_seen_at"]:
                            continue
                        self._db.execute(
                            """UPDATE failure_incidents SET last_seen_at=?,healthy_streak=0,
                               recovery_evidence_json='[]' WHERE incident_id=?""",
                            (at, old["incident_id"]),
                        )
                        continue
                    incident_id = str(uuid4())
                    self._db.execute(
                        """INSERT INTO failure_incidents
                           (incident_id,component,kind,signature,opened_at,last_seen_at,
                            state,healthy_streak,resolved_at,evidence_json,recovery_evidence_json)
                           VALUES (?,?,?,?,?,?,'open',0,NULL,?,'[]')""",
                        (incident_id, component, kind, signature, at, at,
                         json.dumps(evidence)),
                    )
                    result.append({"incident_id": incident_id, "component": component,
                                   "kind": kind, "transition": "opened"})
                elif comp.state is State.HEALTHY:
                    rows = self._db.execute(
                        "SELECT * FROM failure_incidents WHERE component=? AND state='open'",
                        (component,),
                    ).fetchall()
                    for row in rows:
                        old = self._incident(row)
                        if at <= old["last_seen_at"]:
                            continue
                        # An empty health probe is not proof of recovery.
                        if not evidence:
                            continue
                        streak = old["healthy_streak"] + 1
                        refs = tuple(dict.fromkeys(
                            (*old["recovery_evidence_refs"], *evidence)))[:8]
                        recovered = streak >= 2
                        self._db.execute(
                            """UPDATE failure_incidents SET last_seen_at=?,healthy_streak=?,
                               recovery_evidence_json=?,state=?,resolved_at=?
                               WHERE incident_id=?""",
                            (at, streak, json.dumps(refs),
                             "recovered" if recovered else "open",
                             at if recovered else None, old["incident_id"]),
                        )
                        result.append({"incident_id": old["incident_id"],
                                       "component": component, "kind": old["kind"],
                                       "transition": "recovered" if recovered else "verifying"})
                # Unknown, paused or recovering does not prove success.
        return tuple(result)

    def record_verified_lesson(
        self, *, incident_id: str, cause: str, correction: str,
        verification_refs: tuple[str, ...], verifier,
        at: str | None = None,
    ) -> dict:
        """Only post-recovery independent verification can add an advisory.

        Caller must supply a trusted, deterministic verifier; no LLM result
        or snapshot alone can approve learning. The callback must return the
        literal bool True, and a failed callback never changes the playbook.
        """
        old = self.get_incident(incident_id)
        if old is None or old["state"] != "recovered" or old["healthy_streak"] < 2:
            raise FailureMemoryError("recovery_not_confirmed")
        existing = self._db.execute(
            "SELECT lesson_id FROM failure_lessons WHERE source_incident_id=?",
            (incident_id,),
        ).fetchone()
        if existing:
            return {"status": "already_stored", "lesson_id": existing[0],
                    "incident_id": incident_id}
        clean_cause = _safe_text(cause, "cause", 160)
        clean_correction = _safe_text(correction, "correction", 480)
        try:
            refs = _refs(verification_refs, required=True)
        except ValueError as exc:
            raise FailureMemoryError("independent_evidence_required") from exc
        if not callable(verifier):
            raise FailureMemoryError("independent_verifier_required")
        try:
            passed = verifier(dict(old), refs)
        except Exception as exc:
            raise FailureMemoryError("independent_verification_failed") from exc
        if passed is not True:
            raise FailureMemoryError("independent_verification_failed")
        now = _utc(at or _utc_now())
        if now < old["resolved_at"]:
            raise FailureMemoryError("verification_predates_recovery")
        expires = (datetime.fromisoformat(now) + timedelta(days=90)).isoformat()
        lesson_id = str(uuid4())
        with self._db:
            self._db.execute(
                """INSERT OR IGNORE INTO failure_lessons VALUES(?,?,?,?,?,?,?,?,?)""",
                (lesson_id, incident_id, old["kind"], old["signature"],
                 clean_cause, clean_correction, json.dumps(refs), now, expires),
            )
        stored = self._db.execute(
            "SELECT lesson_id FROM failure_lessons WHERE source_incident_id=?",
            (incident_id,),
        ).fetchone()
        return {"status": "stored" if stored[0] == lesson_id else "already_stored",
                "lesson_id": stored[0], "incident_id": incident_id}

    def advice_for_incident(
        self, incident_id: str, *, max_items: int = 2, max_bytes: int = 1024,
        at: str | None = None,
    ) -> tuple[dict, ...]:
        """Conditional retrieval ONLY for currently open, exactly-matching failures."""
        if type(max_items) is not int or not 1 <= max_items <= 5:
            raise ValueError("invalid_advice_count")
        if type(max_bytes) is not int or not 128 <= max_bytes <= 4096:
            raise ValueError("invalid_advice_budget")
        incident = self.get_incident(incident_id)
        if not incident or incident["state"] != "open":
            return ()
        now = _utc(at or _utc_now())
        rows = self._db.execute(
            """SELECT lesson_id,cause,correction,verification_refs_json
               FROM failure_lessons WHERE kind=? AND signature=? AND expires_at>?
               ORDER BY verified_at DESC,lesson_id LIMIT ?""",
            (incident["kind"], incident["signature"], now, max_items),
        ).fetchall()
        result = []
        for lesson_id, cause, correction, evidence in rows:
            try:
                # Disk content is still lower-trust than the policy boundary:
                # validate again at retrieval (including tampered DB rows).
                safe_cause = _safe_text(cause, "cause", 160)
                safe_correction = _safe_text(correction, "correction", 480)
                refs = _refs(json.loads(evidence), required=True)
            except (ValueError, TypeError):
                continue
            obj = {"lesson_id": lesson_id, "cause": safe_cause,
                   "correction": safe_correction, "verification_refs": list(refs),
                   "authority": "evidence_only"}
            trial = result + [obj]
            if len(json.dumps(trial, ensure_ascii=False).encode("utf-8")) > max_bytes:
                continue
            result.append(obj)
        return tuple(result)
