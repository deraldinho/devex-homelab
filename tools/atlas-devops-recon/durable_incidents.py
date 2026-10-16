"""CP11 durable idempotent incident ledger. SQLite is the single source of truth.

Outbox JSON files are rebuildable projections. Never execute or approve proposals.
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import sqlite3
import tempfile
import threading

_schema_lock = threading.RLock()

SCHEMA = "atlas.collective.proposal.v2"
VALID_SOURCE = {"x99_worker", "pentium_services"}
VALID_KIND = {"worker_not_running", "worker_stale", "worker_duplicate",
              "atlas-cognitive", "atlas-dashboard", "atlas-observation", "atlas-discord"}


def canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def connect(path: Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    con = sqlite3.connect(str(path), isolation_level=None, timeout=10)
    con.row_factory=sqlite3.Row
    con.execute("PRAGMA busy_timeout=10000")
    with _schema_lock:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=FULL")
        con.executescript("""
        CREATE TABLE IF NOT EXISTS counters(
            source TEXT NOT NULL, kind TEXT NOT NULL, last_no INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(source,kind)
        );
        CREATE TABLE IF NOT EXISTS incidents(
            id TEXT PRIMARY KEY, source TEXT NOT NULL, kind TEXT NOT NULL,
            occurrence INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('open','resolved')),
            payload TEXT NOT NULL, opened_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(source,kind,occurrence)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS only_one_open
            ON incidents(source,kind) WHERE status='open';
    """)
    return con


def _validate(source, findings, at):
    if source not in VALID_SOURCE or not isinstance(findings,dict):
        raise ValueError("unapproved source or findings")
    if set(findings)-VALID_KIND or (source=="x99_worker" and set(findings)-{
        "worker_not_running","worker_stale","worker_duplicate"}):
        raise ValueError("unapproved incident kind")
    if source=="pentium_services" and set(findings)-{
        "atlas-cognitive","atlas-dashboard","atlas-observation","atlas-discord"}:
        raise ValueError("unapproved Pentium incident kind")
    if at.tzinfo is None:
        raise ValueError("timezone-aware time is required")
    for kind,details in findings.items():
        if not isinstance(details,dict):
            raise ValueError("invalid finding")
        if len(str(details.get("summary","")))>600:
            raise ValueError("finding summary oversized")


def _id(source: str, kind: str, sequence: int) -> str:
    return hashlib.sha256(f"atlas.cp11:{source}:{kind}:{sequence}".encode()).hexdigest()[:32]


def reconcile(db_path: Path, outbox: Path, *, source: str, findings: dict,
              at: datetime | None = None, fault=None) -> dict:
    """State transition atomically in DB, then materialize a restart-safe outbox.

    fault is a test-only hook for simulated process failure.
    """
    at = at or datetime.now(timezone.utc)
    _validate(source,findings,at)
    now = at.isoformat()
    con = connect(db_path)
    opened = []
    resolved = []
    try:
        con.execute("BEGIN IMMEDIATE")
        for kind in sorted(VALID_KIND):
            if (source=="x99_worker") != kind.startswith("worker_"):
                continue
            current=con.execute(
                "SELECT * FROM incidents WHERE source=? AND kind=? AND status='open'",
                (source,kind)).fetchone()
            if kind in findings:
                if current is None:
                    count=con.execute("SELECT last_no FROM counters WHERE source=? AND kind=?",
                                      (source,kind)).fetchone()
                    number=int(count["last_no"] if count else 0)+1
                    incident_id=_id(source,kind,number)
                    payload={
                        "schema":SCHEMA,"id":incident_id,"origin":source,"kind":kind,
                        "occurrence":number,"status":"PROPOSED","opened_at":now,
                        "summary":str(findings[kind].get("summary") or "Anomaly detected"),
                        "allowed_actions":["observe","diagnose","report"],
                        "auto_execute":False,"requires_approval_for_changes":True,
                    }
                    con.execute("""INSERT INTO counters(source,kind,last_no) VALUES(?,?,?)
                      ON CONFLICT(source,kind) DO UPDATE SET last_no=excluded.last_no""",
                      (source,kind,number))
                    con.execute("""INSERT INTO incidents(id,source,kind,occurrence,status,
                                 payload,opened_at,updated_at) VALUES(?,?,?,?,?,?,?,?)""",
                                 (incident_id,source,kind,number,"open",
                                  canonical(payload),now,now))
                    opened.append(incident_id)
            elif current is not None:
                payload=json.loads(current["payload"])
                payload["status"]="RESOLVED"
                payload["resolved_at"]=now
                con.execute("""UPDATE incidents SET status='resolved', payload=?,
                                 updated_at=? WHERE id=?""",
                             (canonical(payload),now,current["id"]))
                resolved.append(current["id"])
        if fault is not None:
            fault("before_commit")
        con.execute("COMMIT")
        if fault is not None:
            fault("after_commit")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    delivered = materialize(db_path, outbox, source=source, fault=fault)
    return {"status":"reconciled","source":source,"opened":opened,"resolved":resolved,
            "outbox_total":delivered,"execution_started":False}


def materialize(db_path: Path, outbox: Path, *, source: str, fault=None) -> int:
    """Reconstruct JSON projections from durable rows; safe after any crash."""
    if source not in VALID_SOURCE:
        raise ValueError("invalid source")
    outbox = Path(outbox)
    outbox.mkdir(parents=True, exist_ok=True)
    con=connect(db_path)
    try:
        rows=con.execute("SELECT id,payload FROM incidents WHERE source=? ORDER BY id",
                         (source,)).fetchall()
        for item in rows:
            target=outbox/(item["id"]+".json")
            payload=item["payload"]
            # Reject symlink targets before any content check or mutation.
            if target.is_symlink():
                raise PermissionError("outbox file is a symlink")
            if target.exists() and target.read_text(encoding="utf-8")==payload+"\n":
                continue
            # Each concurrent writer needs its own temporary file, even in one PID.
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",
                        dir=outbox,prefix=target.name+".",suffix=".tmp",
                        delete=False) as fh:
                    tmp_path=Path(fh.name)
                    fh.write(payload+"\n")
                    fh.flush()
                    os.fsync(fh.fileno())
                if target.is_symlink():
                    raise PermissionError("outbox file is a symlink")
                os.replace(tmp_path,target)
                tmp_path=None
                if fault is not None:
                    fault("after_projection")
            finally:
                if tmp_path is not None:
                    tmp_path.unlink(missing_ok=True)
        return len(rows)
    finally:
        con.close()


def list_open(db_path: Path,source: str) -> list[dict]:
    con=connect(db_path)
    try:
        return [json.loads(r[0]) for r in con.execute(
            "SELECT payload FROM incidents WHERE source=? AND status='open'",
            (source,)).fetchall()]
    finally:
        con.close()
