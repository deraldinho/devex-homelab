"""Atlas CP11 versioned proactive autonomy policy + durable reservation.

Only read-only diagnosis is reservable. Dispatch requires separate explicit
authorization after reservation. Kill switch stops new reservations immediately.
"""
from datetime import datetime,timezone
from pathlib import Path
import json
import sqlite3
from sqlite_uri_safety import readonly_uri
import hashlib
import threading

_schema_lock = threading.RLock()
from signed_event_transport import ALLOWED_ORIGINS,ALLOWED_KINDS,compact

SCHEMA="atlas.autonomy.policy.v2"
ALLOWED_ACTIONS={"diagnose_readonly"}

def validate_policy(policy:dict) ->dict:
    if not isinstance(policy,dict) or policy.get("schema")!=SCHEMA:
        raise ValueError("unknown autonomy policy")
    if policy.get("mode")!="observe_only":
        raise PermissionError("this checkpoint permits observe_only only")
    if type(policy.get("enabled")) is not bool or type(policy.get("kill_switch")) is not bool:
        raise ValueError("explicit enable and kill switch required")
    if type(policy.get("auto_approve")) is not bool or policy["auto_approve"]:
        raise PermissionError("auto-approval is forbidden")
    if type(policy.get("auto_write")) is not bool or policy["auto_write"]:
        raise PermissionError("automatic changes are forbidden")
    if not set(policy.get("allowed_actions",[]))<=ALLOWED_ACTIONS:
        raise PermissionError("forbidden action")
    if not set(policy.get("origins",[]))<=ALLOWED_ORIGINS or not set(policy.get("kinds",[]))<=ALLOWED_KINDS:
        raise PermissionError("unapproved event category")
    caps=policy.get("limits")
    if not isinstance(caps,dict):
        raise ValueError("limits required")
    for name,limit in [("daily_readonly_missions",12),("max_concurrent",3)]:
        v=caps.get(name)
        if type(v) is not int or not 1<=v<=limit:
            raise ValueError("unsafe resource cap: "+name)
    if caps.get("max_total_cost_usd")!=0:
        raise PermissionError("no paid inference in CP11")
    return policy

def decide(proposal:dict, policy:dict)->str:
    policy=validate_policy(policy)
    if policy["kill_switch"] or not policy["enabled"]:
        return "PAUSED"
    if proposal.get("schema")!="atlas.collective.proposal.v2" or proposal.get("auto_execute") is not False:
        return "DENIED"
    if proposal.get("status")!="PROPOSED" or proposal.get("origin") not in policy["origins"]:
        return "DENIED"
    if proposal.get("kind") not in policy["kinds"]:
        return "DENIED"
    if "diagnose_readonly" not in policy["allowed_actions"]:
        return "DENIED"
    return "ALLOW_READONLY_ONLY"

def reserve(proposal:dict,*,policy:dict,db_path:Path,inbox_path:Path,
            now:datetime|None=None)->dict:
    decision=decide(proposal,policy)
    if decision!="ALLOW_READONLY_ONLY":
        return {"status":decision,"execution_authorized":False}
    # The HMAC-verified receiver is authoritative; raw JSON is never sufficient.
    # Safe percent-encoding prevents reserved URI chars in the resolved path
    # from altering query mode=ro.
    inbox=sqlite3.connect(readonly_uri(inbox_path),uri=True)
    try:
        valid=inbox.execute("SELECT payload_hash FROM inbox WHERE origin=? AND event_id=? AND state='PROPOSED'",
                            (proposal["origin"],proposal["id"])).fetchone()
    finally:
        inbox.close()
    if not valid or valid[0]!=hashlib.sha256(compact(proposal)).hexdigest():
        return {"status":"UNVERIFIED_EVENT","execution_authorized":False}
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone required")
    date=now.astimezone(timezone.utc).date().isoformat()
    db_path=Path(db_path);db_path.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(str(db_path),timeout=10,isolation_level=None)
    try:
        con.execute("PRAGMA busy_timeout=10000")
        with _schema_lock:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=FULL")
            con.execute("""CREATE TABLE IF NOT EXISTS reservations(
            event_id TEXT PRIMARY KEY, origin TEXT NOT NULL, kind TEXT NOT NULL,
            utc_day TEXT NOT NULL, status TEXT NOT NULL,
            reserved_at TEXT NOT NULL
        )""")
        con.execute("BEGIN IMMEDIATE")
        old=con.execute("SELECT status FROM reservations WHERE event_id=?",
                        (proposal["id"],)).fetchone()
        if old:
            con.execute("COMMIT")
            return {"status":"ALREADY_RESERVED","execution_authorized":False}
        count=con.execute("SELECT COUNT(*) FROM reservations WHERE utc_day=?",(date,)).fetchone()[0]
        if count>=policy["limits"]["daily_readonly_missions"]:
            con.execute("COMMIT")
            return {"status":"DAILY_LIMIT","execution_authorized":False}
        active=con.execute("""SELECT COUNT(*) FROM reservations
                                WHERE status IN ('reserved','running')""").fetchone()[0]
        if active>=policy["limits"]["max_concurrent"]:
            con.execute("COMMIT")
            return {"status":"BACKPRESSURE","execution_authorized":False}
        con.execute("INSERT INTO reservations VALUES(?,?,?,?,?,?)",
                    (proposal["id"],proposal["origin"],proposal["kind"],date,
                     "reserved",now.isoformat()))
        con.execute("COMMIT")
        return {"status":"RESERVED_READONLY","execution_authorized":False,
                "requires_separate_dispatch":True}
    except BaseException:
        if con.in_transaction:con.execute("ROLLBACK")
        raise
    finally:
        con.close()
