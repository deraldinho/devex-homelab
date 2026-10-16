"""CP11 authenticated observer event transport. Receivers only queue diagnostic proposals.

HMAC-SHA256 validates provenance; SQLite enforces at-most-once acceptance.
No command interpretation, no tool invocation, and no automatic approvals.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import hmac
import json
import os
import re
import sqlite3
import uuid
import threading

_schema_lock = threading.RLock()

ALLOWED_ORIGINS={"x99_worker","pentium_services"}
ALLOWED_KINDS={"worker_not_running","worker_stale","worker_duplicate",
               "atlas-cognitive","atlas-dashboard","atlas-observation","atlas-discord"}
TTL_SECONDS=900


def compact(data) -> bytes:
    return json.dumps(data,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")


def _key(data:bytes):
    if not isinstance(data,bytes) or len(data)!=32:
        raise ValueError("32-byte HMAC key required")
    return data


def sign(proposal:dict, *, key:bytes, origin:str, now:datetime|None=None,
         nonce:str|None=None)->dict:
    """Sign a *proposal*, not authorization. No code execution capacity is encoded."""
    _key(key)
    if origin not in ALLOWED_ORIGINS:
        raise ValueError("unknown origin")
    if proposal.get("schema")!="atlas.collective.proposal.v2" or proposal.get("origin")!=origin:
        raise ValueError("unsupported proposal schema/origin")
    if proposal.get("kind") not in ALLOWED_KINDS or proposal.get("auto_execute") is not False:
        raise PermissionError("untrusted proposal operation")
    if proposal.get("status") not in {"PROPOSED","RESOLVED"}:
        raise ValueError("unsupported status")
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("naive timestamp")
    ident=str(proposal.get("id") or "")
    if not re.fullmatch(r"[0-9a-f]{32}",ident):
        raise ValueError("invalid incident ID")
    body={"schema":"atlas.observer.event.v1","origin":origin,"id":ident,
          "proposal":proposal,"issued_at":now.isoformat(),
          "nonce":nonce or os.urandom(16).hex()}
    body["signature"]=hmac.new(key,compact(body),hashlib.sha256).hexdigest()
    return body


def _validate(envelope:dict,key:bytes,at:datetime):
    _key(key)
    if not isinstance(envelope,dict) or envelope.get("schema")!="atlas.observer.event.v1":
        raise ValueError("unsupported event schema")
    signature=envelope.get("signature")
    if not isinstance(signature,str) or not re.fullmatch("[0-9a-f]{64}",signature):
        raise PermissionError("missing or invalid HMAC")
    body={k:v for k,v in envelope.items() if k!="signature"}
    if set(body)!={"schema","origin","id","proposal","issued_at","nonce"}:
        raise ValueError("unexpected event fields")
    desired=hmac.new(key,compact(body),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature,desired):
        raise PermissionError("HMAC mismatch")
    origin=body["origin"];proposal=body["proposal"]
    if origin not in ALLOWED_ORIGINS or not isinstance(proposal,dict):
        raise ValueError("invalid event source")
    if (proposal.get("schema")!="atlas.collective.proposal.v2"
        or proposal.get("id")!=body["id"] or proposal.get("origin")!=origin
        or proposal.get("kind") not in ALLOWED_KINDS
        or proposal.get("status") not in ("PROPOSED","RESOLVED")
        or proposal.get("auto_execute") is not False
        or proposal.get("requires_approval_for_changes") is not True
        or proposal.get("allowed_actions")!=["observe","diagnose","report"]):
        raise PermissionError("event requests disallowed capability")
    if origin=="x99_worker" and not proposal["kind"].startswith("worker_"):
        raise ValueError("source-kind mismatch")
    if origin=="pentium_services" and proposal["kind"].startswith("worker_"):
        raise ValueError("source-kind mismatch")
    if not re.fullmatch(r"[0-9a-f]{32}",str(body["nonce"])):
        raise ValueError("invalid nonce")
    when=datetime.fromisoformat(body["issued_at"])
    if when.tzinfo is None or at.tzinfo is None:
        raise ValueError("timestamp timezone required")
    if abs((at-when).total_seconds())>TTL_SECONDS:
        raise PermissionError("stale or future event")
    return body


def receive(envelope:dict,*,key:bytes,db_path:Path,now:datetime|None=None)->dict:
    body=_validate(envelope,key,now or datetime.now(timezone.utc))
    db_path=Path(db_path)
    db_path.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(str(db_path),isolation_level=None,timeout=10)
    try:
        con.execute("PRAGMA busy_timeout=10000")
        with _schema_lock:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=FULL")
            con.execute("""CREATE TABLE IF NOT EXISTS inbox(
            origin TEXT NOT NULL, event_id TEXT NOT NULL, payload_hash TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('PROPOSED','RESOLVED')),
            payload TEXT NOT NULL,received_at TEXT NOT NULL,
            PRIMARY KEY(origin,event_id,state))""")
        con.execute("BEGIN IMMEDIATE")
        payload_hash=hashlib.sha256(compact(body["proposal"])).hexdigest()
        existing=con.execute(
            "SELECT payload_hash FROM inbox WHERE origin=? AND event_id=? AND state=?",
            (body["origin"],body["id"],body["proposal"]["status"])).fetchone()
        if existing:
            if not hmac.compare_digest(existing[0],payload_hash):
                raise PermissionError("same incident/state different payload; reconciliation required")
            result="duplicate"
        else:
            # A resolution cannot create a new incident. No implicit approvals.
            if body["proposal"]["status"]=="RESOLVED":
                opened=con.execute("""SELECT 1 FROM inbox
                          WHERE origin=? AND event_id=? AND state='PROPOSED'""",
                          (body["origin"],body["id"])).fetchone()
                if not opened:
                    raise ValueError("resolution without matching proposal")
            con.execute("INSERT INTO inbox VALUES(?,?,?,?,?,?)",
                (body["origin"],body["id"],payload_hash,body["proposal"]["status"],
                 compact(body["proposal"]).decode("utf-8"),
                 (now or datetime.now(timezone.utc)).isoformat()))
            result="accepted"
        con.execute("COMMIT")
        return {"status":result,"id":body["id"],"origin":body["origin"],
                "execution_started":False,"ack":hashlib.sha256(
                    compact([body["origin"],body["id"],body["proposal"]["status"],payload_hash])
                    ).hexdigest()[:32]}
    except BaseException:
        if con.in_transaction:con.execute("ROLLBACK")
        raise
    finally:
        con.close()
