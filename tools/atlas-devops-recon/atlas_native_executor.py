"""Governed Atlas review executor: bounded claim, receipt and reconciliation.

The worker interface is injected: this module never launches processes or
transmits data. Unknown outcomes remain IN_FLIGHT and are never replayed.
"""
from contextlib import closing
import hashlib
import json
import sqlite3
from pathlib import Path
from atlas_native_workflow import connect, inspect

TERMINAL = frozenset({"SUCCEEDED", "FAILED", "BLOCKED"})
def _table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS execution_receipts(
        task_id TEXT PRIMARY KEY, status TEXT NOT NULL,
        attempt INTEGER NOT NULL CHECK(attempt=1),
        result_hash TEXT, result TEXT)""")

def claim(db, task_id):
    with closing(connect(db)) as con:
        con.execute("BEGIN IMMEDIATE")
        _table(con)
        row=con.execute("""SELECT o.payload,m.project_root,m.fingerprint,m.status,o.status
            FROM review_outbox o JOIN missions m ON m.id=o.mission_id
            WHERE o.task_id=?""",(task_id,)).fetchone()
        if not row:
            raise KeyError("unknown task")
        payload,root,baseline,mission_status,outbox_status=row
        previous=con.execute("SELECT status FROM execution_receipts WHERE task_id=?",(task_id,)).fetchone()
        if previous:
            con.execute("COMMIT")
            return {"status":previous[0],"claimed":False}
        missing,current=inspect(root)
        if missing or current!=baseline:
            con.execute("UPDATE missions SET status='BLOCKED_BASELINE' WHERE id=?",
                        (json.loads(payload)["mission_id"],))
            con.execute("UPDATE review_outbox SET status='BLOCKED_DRIFT' WHERE task_id=?",(task_id,))
            con.execute("COMMIT")
            return {"status":"BLOCKED_DRIFT","claimed":False}
        if mission_status!="REVIEW_APPROVED" or outbox_status!="PENDING":
            raise PermissionError("review not eligible")
        con.execute("INSERT INTO execution_receipts(task_id,status,attempt) VALUES(?,'IN_FLIGHT',1)",(task_id,))
        con.execute("COMMIT")
        return {"status":"IN_FLIGHT","claimed":True,"payload":json.loads(payload)}

def finish(db,task_id,result):
    # Only the trusted caller who actually owns the worker may call finish.
    # Receipt authentication/OS sandboxing are external production gates.
    if not isinstance(result,dict) or result.get("status") not in TERMINAL:
        raise ValueError("result must have explicit terminal status")
    text=json.dumps(result,sort_keys=True,ensure_ascii=False)
    if len(text)>200000:
        raise ValueError("receipt too large")
    digest=hashlib.sha256(text.encode()).hexdigest()
    with closing(connect(db)) as con:
        con.execute("BEGIN IMMEDIATE")
        _table(con)
        row=con.execute("SELECT status,result_hash FROM execution_receipts WHERE task_id=?",(task_id,)).fetchone()
        if row is None:
            raise KeyError("task never claimed")
        if row[0] in TERMINAL:
            if row[1]!=digest:
                raise ValueError("conflicting terminal receipt")
            con.execute("COMMIT")
            return {"status":row[0],"idempotent":True}
        if row[0]!="IN_FLIGHT":
            raise ValueError("invalid transition")
        con.execute("UPDATE execution_receipts SET status=?,result_hash=?,result=? WHERE task_id=?",
                    (result["status"],digest,text,task_id))
        con.execute("COMMIT")
        return {"status":result["status"],"idempotent":False}

def status(db,task_id):
    with closing(connect(db)) as con:
        _table(con)
        row=con.execute("SELECT status,attempt,result_hash FROM execution_receipts WHERE task_id=?",(task_id,)).fetchone()
        return None if row is None else {"status":row[0],"attempt":row[1],"result_hash":row[2]}
