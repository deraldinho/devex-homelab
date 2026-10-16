"""Native mission-to-agent outbox. No process or network execution.

Transactional, idempotent proposals for external governed executors.
A review approval does NOT authorize execution or deployment.
"""
from contextlib import closing
import hashlib
import json
import sqlite3
from pathlib import Path
from atlas_native_workflow import connect, inspect

ALLOWED_ROLES = frozenset({"architecture", "security", "qa", "reliability"})

def enqueue_readonly_review(db, mission_id: str, role: str):
    if role not in ALLOWED_ROLES:
        raise ValueError("unsupported read-only reviewer role")
    with closing(connect(db)) as con:
        con.execute("BEGIN IMMEDIATE")
        con.execute("""CREATE TABLE IF NOT EXISTS review_outbox(
            task_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL,
            role TEXT NOT NULL, fingerprint TEXT NOT NULL,
            payload TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('PENDING','BLOCKED_DRIFT')),
            UNIQUE(mission_id, role))""")
        row = con.execute("SELECT project_root, fingerprint, status FROM missions WHERE id=?", (mission_id,)).fetchone()
        if row is None:
            raise KeyError("mission not found")
        root, fingerprint, state = row
        if state != "REVIEW_APPROVED":
            raise PermissionError("mission not approved for review")
        missing, current = inspect(root)
        if missing or current != fingerprint:
            con.execute("UPDATE missions SET status='BLOCKED_BASELINE' WHERE id=?", (mission_id,))
            con.execute("UPDATE review_outbox SET status='BLOCKED_DRIFT' WHERE mission_id=?", (mission_id,))
            con.execute("COMMIT")
            return {"status":"BLOCKED_DRIFT", "execution_authorized":False}
        task_id = hashlib.sha256(f"{mission_id}:{role}:{fingerprint}".encode()).hexdigest()
        payload = {"schema":"atlas.review.request.v1", "task_id":task_id,
                   "mission_id":mission_id, "role":role, "project_root":root,
                   "fingerprint":fingerprint, "read_only":True,
                   "execution_authorized":False}
        con.execute("""INSERT OR IGNORE INTO review_outbox
            (task_id,mission_id,role,fingerprint,payload,status) VALUES (?,?,?,?,?,'PENDING')""",
            (task_id,mission_id,role,fingerprint,json.dumps(payload,sort_keys=True)))
        record = con.execute("SELECT task_id,status,payload FROM review_outbox WHERE mission_id=? AND role=?",
                             (mission_id,role)).fetchone()
        if record[0] != task_id or record[1] != "PENDING":
            raise ValueError("outbox conflict or drift")
        con.execute("COMMIT")
        return {"status":"PENDING","task_id":task_id,"payload":json.loads(record[2]),
                "execution_authorized":False}

def list_pending(db):
    with closing(connect(db)) as con:
        exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='review_outbox'").fetchone()
        if not exists:
            return []
        has_receipts = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='execution_receipts'"
        ).fetchone()
        if has_receipts:
            sql = """SELECT o.payload FROM review_outbox o
                     LEFT JOIN execution_receipts r ON r.task_id=o.task_id
                     WHERE o.status='PENDING' AND r.task_id IS NULL ORDER BY o.task_id"""
        else:
            sql = "SELECT payload FROM review_outbox WHERE status='PENDING' ORDER BY task_id"
        return [json.loads(row[0]) for row in con.execute(sql)]
