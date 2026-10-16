"""Durable task/session binding. No network calls or implicit session creation."""
from contextlib import closing
import sqlite3
from atlas_native_workflow import connect

def bind_session(db, task_id, session_id, issuer):
    if not all(isinstance(v,str) and v.strip() for v in (task_id,session_id,issuer)):
        raise ValueError("nonempty binding fields required")
    with closing(connect(db)) as con:
        con.execute("BEGIN IMMEDIATE")
        exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='execution_receipts'").fetchone()
        if not exists:
            raise PermissionError("task must be claimed and in flight")
        row=con.execute("SELECT status FROM execution_receipts WHERE task_id=?",(task_id,)).fetchone()
        if row is None or row[0]!="IN_FLIGHT":
            raise PermissionError("task must be claimed and in flight")
        con.execute("""CREATE TABLE IF NOT EXISTS session_bindings(
          task_id TEXT PRIMARY KEY, session_id TEXT NOT NULL UNIQUE,
          issuer TEXT NOT NULL)""")
        existing=con.execute("SELECT session_id,issuer FROM session_bindings WHERE task_id=?",(task_id,)).fetchone()
        if existing is not None and existing!=(session_id,issuer):
            raise ValueError("session binding conflict")
        con.execute("INSERT OR IGNORE INTO session_bindings VALUES(?,?,?)",(task_id,session_id,issuer))
        persisted=con.execute("SELECT session_id,issuer FROM session_bindings WHERE task_id=?",(task_id,)).fetchone()
        if persisted != (session_id,issuer):
            raise ValueError("session already owned by another task")
        con.execute("COMMIT")
        return {"task_id":task_id,"session_id":session_id,"issuer":issuer}

def session_for_task(db,task_id):
    with closing(connect(db)) as con:
        exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='session_bindings'").fetchone()
        if not exists: return None
        row=con.execute("SELECT session_id,issuer FROM session_bindings WHERE task_id=?",(task_id,)).fetchone()
        return None if row is None else {"session_id":row[0],"issuer":row[1]}
