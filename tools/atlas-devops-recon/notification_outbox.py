"""CP11 durable notification outbox; no actual Discord destination is configured.

Exactly-once *observable*: on ambiguous send, stop for reconciliation, never
blindly retry. Sender callback must be explicitly supplied by approved gateway.
"""
from datetime import datetime,timezone
from pathlib import Path
import json
import re
import sqlite3
import hashlib
import threading
from signed_event_transport import compact

_schema_lock = threading.RLock()

def _db(path:Path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(str(path),isolation_level=None,timeout=10)
    con.row_factory=sqlite3.Row
    con.execute("PRAGMA busy_timeout=10000")
    with _schema_lock:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=FULL")
        con.execute("""CREATE TABLE IF NOT EXISTS notifications(
        id TEXT PRIMARY KEY,origin TEXT NOT NULL,event_id TEXT NOT NULL,
        status TEXT NOT NULL,summary TEXT NOT NULL,created_at TEXT NOT NULL,
        provider_receipt TEXT,attempts INTEGER NOT NULL DEFAULT 0
    )""")
    return con

def prepare(event:dict,*,db_path:Path,verified_inbox:Path)->dict:
    if event.get("schema")!="atlas.collective.proposal.v2":
        raise ValueError("unrecognized proposal")
    if event.get("auto_execute") is not False or event.get("status")!="PROPOSED":
        raise PermissionError("only diagnostic proposals can notify")
    incident=str(event.get("id") or "")
    if not re.fullmatch("[0-9a-f]{32}",incident):
        raise ValueError("invalid event identity")
    origin=event.get("origin")
    if origin not in {"x99_worker","pentium_services"}:
        raise PermissionError("unknown sender")
    # Only an accepted HMAC-verified event can request a notification.
    _safe_path=Path(verified_inbox).resolve().as_posix().replace("%","%25").replace("?","%3F").replace("#","%23")
    con_verify=sqlite3.connect(f"file:{_safe_path}?mode=ro",uri=True)
    try:
        row=con_verify.execute("SELECT payload_hash FROM inbox WHERE origin=? AND event_id=? AND state='PROPOSED'",
                               (origin,incident)).fetchone()
    finally:con_verify.close()
    if not row or row[0]!=hashlib.sha256(compact(event)).hexdigest():
        raise PermissionError("notification event lacks trusted receiver proof")
    digest=hashlib.sha256(f"{origin}:{incident}:notify".encode()).hexdigest()[:32]
    summary=str(event.get("summary") or "")[:350]
    if not summary:
        raise ValueError("empty notification")
    con=_db(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        old=con.execute("SELECT status FROM notifications WHERE id=?",(digest,)).fetchone()
        if old:
            con.execute("COMMIT")
            return {"status":"already_queued","id":digest,"delivery_status":old["status"]}
        con.execute("INSERT INTO notifications VALUES(?,?,?,?,?,?,?,?)",
                    (digest,origin,incident,"pending",summary,
                     datetime.now(timezone.utc).isoformat(),None,0))
        con.execute("COMMIT")
        return {"status":"queued","id":digest,"delivery_status":"pending"}
    except BaseException:
        if con.in_transaction:con.execute("ROLLBACK")
        raise
    finally:con.close()

def dispatch_one(*,db_path:Path,id:str,sender,explicit_enabled:bool=False)->dict:
    if not explicit_enabled:
        raise PermissionError("notification transport disabled until configured")
    con=_db(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        row=con.execute("SELECT * FROM notifications WHERE id=?",(id,)).fetchone()
        if row is None or row["status"]!="pending":
            con.execute("COMMIT")
            return {"status":"blocked_no_pending"}
        # Persist in-flight before making an external call. Timeouts are ambiguous,
        # and must not trigger duplicate sending.
        con.execute("UPDATE notifications SET status='in_flight',attempts=attempts+1 WHERE id=?",(id,))
        con.execute("COMMIT")
        try:
            result=sender({"idempotency_key":id,"summary":row["summary"],
                           "incident_id":row["event_id"],"origin":row["origin"]})
            receipt=str(result.get("receipt") or "")
            if not receipt or len(receipt)>200:
                raise ValueError("missing provider receipt")
        except Exception:
            return {"status":"NEEDS_RECONCILIATION","id":id}
        con.execute("UPDATE notifications SET status='delivered',provider_receipt=? WHERE id=?",
                    (receipt,id))
        return {"status":"delivered","id":id}
    finally:con.close()
