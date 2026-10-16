"""CP11 read-only end-to-end incident pipeline.

Chain: injected observer snapshot -> durable incident ledger -> HMAC signed
event -> authenticated receiver -> autonomy policy decision -> reservation ->
trusted notification outbox *prepare*.

Integration only: every stage delegates to the existing audited CP11 modules
(durable_incidents, signed_event_transport, autonomy_policy_gate,
notification_outbox). Hard guarantees of this module:

- The observation source is a caller-injected probe (a fake/isolated snapshot
  in tests). This module never spawns processes, never touches OS tasks or
  services, and never calls any endpoint.
- The 32-byte HMAC key and every database path are explicit caller inputs.
  No production key, secret or state path is embedded or defaulted here.
- Replays are idempotent: a duplicate event yields no new mission reservation
  and no duplicate notification (receiver, reservation and outbox all dedupe).
- Nothing is executed or sent: the pipeline stops at notification *prepare*.
  The dispatch/transport API is deliberately unreachable from this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3

from autonomy_policy_gate import decide, reserve, validate_policy
from durable_incidents import VALID_SOURCE, reconcile
from notification_outbox import prepare
from signed_event_transport import receive, sign

_MISSION_OK = {"RESERVED_READONLY", "ALREADY_RESERVED"}


def _validate_key(key: bytes) -> bytes:
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("caller-provided 32-byte HMAC key required")
    return key


def _aware(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone-aware time is required")
    return now


def _accepted_proposal(inbox_db, origin: str, event_id: str) -> bool:
    """Read-only check: has the authenticated receiver already accepted the
    PROPOSED state of this incident? Used only to decide whether a resolution
    envelope can be delivered; receive() still performs full validation."""
    inbox_db = Path(inbox_db)
    if not inbox_db.exists():
        return False
    con = None
    try:
        _safe_path=inbox_db.resolve().as_posix().replace("%","%25").replace("?","%3F").replace("#","%23")
        con = sqlite3.connect(f"file:{_safe_path}?mode=ro",
                              uri=True)
        row = con.execute("""SELECT 1 FROM inbox
                             WHERE origin=? AND event_id=? AND state='PROPOSED'""",
                          (origin, event_id)).fetchone()
        return row is not None
    except sqlite3.OperationalError as exc:
        message = str(exc).lower()
        if "no such table" in message:
            return False
        raise sqlite3.OperationalError(str(exc)) from exc
    except sqlite3.Error as exc:
        message = str(exc).lower()
        if "no such table" in message:
            return False
        raise sqlite3.OperationalError(
            "inaccessible or corrupt inbox state: %s" % exc) from exc
    finally:
        if con is not None:
            con.close()


def ingest_event(envelope: dict, *, key: bytes, policy: dict, inbox_db,
                 reservations_db, notifications_db,
                 now: datetime | None = None) -> dict:
    """Authenticated receiver -> decision -> reservation -> notification
    prepare, for one already-signed envelope. Idempotent under replay."""
    _validate_key(key)
    at = _aware(now)
    validate_policy(policy)
    receiver = receive(envelope, key=key, db_path=Path(inbox_db), now=at)
    proposal = envelope["proposal"]  # structurally validated by receive()
    base = {"id": receiver["id"], "origin": receiver["origin"],
            "proposal_status": proposal["status"],
            "receiver": receiver["status"], "ack": receiver["ack"],
            "execution_authorized": False, "execution_started": False,
            "dispatch_performed": False, "messages_sent": 0}
    if proposal["status"] != "PROPOSED":
        # A resolution only closes ledger state; it never mints a mission or
        # a notification, no matter how often it is replayed.
        return dict(base, decision="NOT_APPLICABLE", reservation="skipped",
                    notification="skipped")
    decision = decide(proposal, policy)
    reservation = reserve(proposal, policy=policy, db_path=Path(reservations_db),
                          inbox_path=Path(inbox_db), now=at)
    if reservation["status"] not in _MISSION_OK:
        return dict(base, decision=decision,
                    reservation=reservation["status"], notification="skipped")
    note = prepare(proposal, db_path=Path(notifications_db),
                   verified_inbox=Path(inbox_db))
    return dict(base, decision=decision, reservation=reservation["status"],
                notification=note["status"])


def _deferred_resolution(proposal: dict) -> dict:
    return {"id": str(proposal.get("id") or ""), "origin": proposal.get("origin"),
            "proposal_status": "RESOLVED", "receiver": "resolution_deferred",
            "ack": None, "decision": "NOT_APPLICABLE", "reservation": "skipped",
            "notification": "skipped", "execution_authorized": False,
            "execution_started": False, "dispatch_performed": False,
            "messages_sent": 0}


def _totals(events: list[dict]) -> dict:
    totals = {"events": len(events), "accepted": 0, "duplicate": 0,
              "deferred": 0, "missions_reserved": 0,
              "missions_already_reserved": 0, "missions_withheld": 0,
              "notifications_queued": 0, "notifications_existing": 0,
              "notifications_withheld": 0, "resolutions": 0}
    for event in events:
        state = event["receiver"]
        if state in ("accepted", "duplicate"):
            totals[state] += 1
        elif state == "resolution_deferred":
            totals["deferred"] += 1
        if event["proposal_status"] == "RESOLVED":
            if state == "accepted":
                totals["resolutions"] += 1
            continue
        mission = event["reservation"]
        if mission == "RESERVED_READONLY":
            totals["missions_reserved"] += 1
        elif mission == "ALREADY_RESERVED":
            totals["missions_already_reserved"] += 1
        else:
            totals["missions_withheld"] += 1
        note = event["notification"]
        if note == "queued":
            totals["notifications_queued"] += 1
        elif note == "already_queued":
            totals["notifications_existing"] += 1
        else:
            totals["notifications_withheld"] += 1
    return totals


def run_pipeline(*, probe, source: str, key: bytes, policy: dict, ledger_db,
                 proposal_outbox, inbox_db, reservations_db, notifications_db,
                 now: datetime | None = None) -> dict:
    """Full read-only chain. `probe` is a zero-argument callable returning a
    findings dict, or a static findings dict snapshot. All storage paths and
    the HMAC key are caller-provided; validation fails closed *before* the
    probe observes anything, so a misconfigured run never touches state."""
    _validate_key(key)
    if source not in VALID_SOURCE:
        raise ValueError("unapproved observer source")
    validate_policy(policy)
    at = _aware(now)
    findings = probe() if callable(probe) else probe
    if not isinstance(findings, dict):
        raise ValueError("snapshot probe must yield a findings dict")
    ledger_db = Path(ledger_db)
    proposal_outbox = Path(proposal_outbox)
    record = reconcile(ledger_db, proposal_outbox, source=source,
                       findings=findings, at=at)
    events: list[dict] = []
    for item in sorted(proposal_outbox.glob("*.json")):
        proposal = json.loads(item.read_text(encoding="utf-8"))
        if proposal.get("origin") != source:
            continue
        if (proposal.get("status") == "RESOLVED"
                and not _accepted_proposal(inbox_db, source,
                                           proposal.get("id"))):
            # Never abort the observation loop on an orphan resolution; the
            # ledger already holds the truth and no action can derive from it.
            events.append(_deferred_resolution(proposal))
            continue
        envelope = sign(proposal, key=key, origin=source, now=at)
        events.append(ingest_event(envelope, key=key, policy=policy,
                                   inbox_db=inbox_db,
                                   reservations_db=reservations_db,
                                   notifications_db=notifications_db, now=at))
    return {"status": "pipeline_complete", "source": source,
            "opened": record["opened"], "resolved": record["resolved"],
            "outbox_total": record["outbox_total"], "events": events,
            "totals": _totals(events), "execution_started": False,
            "dispatch_performed": False, "messages_sent": 0}
