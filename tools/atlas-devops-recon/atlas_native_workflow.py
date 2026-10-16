"""Durable native workflow for Atlas checkpoint reviews (stdlib-only, read-only).

This component schedules deterministic review states; it deliberately does not
launch OpenCode, run shell, send notifications, or authorize deployment.
"""
import hashlib
from contextlib import closing
import json
import sqlite3
from pathlib import Path

REQUIRED = ("trusted_cross_host_clock.py", "test_trusted_cross_host_clock.py",
            "system_supervision.py", "sqlite_uri_safety.py")
STATES = ("BLOCKED_BASELINE", "REVIEW_PENDING", "REVIEW_APPROVED",
          "REVIEW_DENIED")

def inspect(root):
    root = Path(root).resolve(strict=True)
    missing = [n for n in REQUIRED if not (root / n).is_file()]
    fingerprint = hashlib.sha256(
        json.dumps([(n, hashlib.sha256((root / n).read_bytes()).hexdigest())
                    for n in REQUIRED if (root / n).is_file()], sort_keys=True).encode()
    ).hexdigest()
    return missing, fingerprint

def connect(db):
    db = Path(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db), isolation_level=None, timeout=10)
    con.execute("PRAGMA busy_timeout=10000")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    con.execute("""CREATE TABLE IF NOT EXISTS missions(
        id TEXT PRIMARY KEY, project_root TEXT NOT NULL, fingerprint TEXT NOT NULL,
        missing TEXT NOT NULL, status TEXT NOT NULL,
        execution_authorized INTEGER NOT NULL DEFAULT 0 CHECK(execution_authorized=0))""")
    return con

def submit(db, mission_id, root):
    if not isinstance(mission_id, str) or not mission_id.strip():
        raise ValueError("mission id required")
    missing, fingerprint = inspect(root)
    root = str(Path(root).resolve(strict=True))
    with closing(connect(db)) as con:
        con.execute("BEGIN IMMEDIATE")
        existing = con.execute("SELECT project_root, fingerprint, missing, status FROM missions WHERE id=?",
                               (mission_id,)).fetchone()
        if existing:
            if existing[0] != root or existing[1] != fingerprint:
                con.execute("ROLLBACK")
                raise ValueError("mission id collision or baseline drift")
            con.execute("COMMIT")
            return {"mission_id":mission_id, "status":existing[3], "missing":json.loads(existing[2]),
                    "execution_authorized":False}
        status = "BLOCKED_BASELINE" if missing else "REVIEW_PENDING"
        con.execute("INSERT INTO missions (id, project_root, fingerprint, missing, status) VALUES (?,?,?,?,?)",
                    (mission_id, root, fingerprint, json.dumps(missing), status))
        con.execute("COMMIT")
        return {"mission_id":mission_id, "status":status, "missing":missing, "execution_authorized":False}

def decide(db, mission_id, approved):
    if type(approved) is not bool:
        raise TypeError("approved must be boolean")
    with closing(connect(db)) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT project_root, fingerprint, status FROM missions WHERE id=?",
                          (mission_id,)).fetchone()
        if row is None:
            con.execute("ROLLBACK")
            raise KeyError("unknown mission")
        if row[2] == "REVIEW_PENDING":
            missing, fingerprint = inspect(row[0])
            if missing or fingerprint != row[1]:
                con.execute("UPDATE missions SET status='BLOCKED_BASELINE' WHERE id=?", (mission_id,))
                status = "BLOCKED_BASELINE"
            else:
                status = "REVIEW_APPROVED" if approved else "REVIEW_DENIED"
                con.execute("UPDATE missions SET status=? WHERE id=?", (status, mission_id))
        else:
            status = row[2]
        con.execute("COMMIT")
        return {"mission_id":mission_id,"status":status,"execution_authorized":False}
