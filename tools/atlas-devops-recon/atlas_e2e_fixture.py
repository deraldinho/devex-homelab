"""CP12 synthetic e2e fixture: isolated end-to-end flow composition.

Composes the CP11 incident_pipeline, signed HMAC receiver, SQLite ledger,
autonomy gate, notification prepare, and an injected probe to demonstrate a
COMPLETE SYNTHETIC end-to-end flow in an isolated temp directory.

All inputs are explicit caller inputs: 32-byte HMAC key, policy dict, ledger
paths, and an optional probe callable.  No production key, secret or state path
is embedded or defaulted.  The pipeline stops at notification *prepare* — no
external sends, no OS execution, no network.

TDD verify: duplicate/restart replay idempotency, resolution, kill switch
with NO execution, tamper HMAC rejection, invalid key fail-closed, exact
counts for mission reservations and notifications, and zero external sends.
replay_fixture() recovers the persisted DB paths and observation snapshot
from the previous outcome (or accepts explicit probe/findings) and never
clears SQLite state.

Unknown outcome is handled explicitly; never promoted automatically.
Disposable 32-byte test key only; no actual secrets.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import tempfile

from incident_pipeline import run_pipeline as _run_pipeline
from autonomy_policy_gate import validate_policy
from durable_incidents import VALID_SOURCE
from signed_event_transport import sign, receive
from notification_outbox import prepare

_TEST_KEY = bytes(range(32))  # disposable 32-byte test key, never production


def _validate_key(key: bytes) -> bytes:
    """Validate that the key is exactly 32 bytes; raise otherwise."""
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("caller-provided 32-byte HMAC key required")
    return key


def _aware(now: datetime | None) -> datetime:
    """Ensure a timezone-aware UTC datetime; use fixed now if None."""
    if now is None:
        return datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone-aware time is required")
    return now


def _accepted_proposal(inbox_db, origin: str, event_id: str) -> bool:
    """Read-only check: has the authenticated receiver already accepted the
    PROPOSED state of this incident?"""
    db = Path(inbox_db)
    if not db.exists():
        return False
    con = sqlite3.connect(f"file:{db.resolve().as_posix()}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT 1 FROM inbox WHERE origin=? AND event_id=? AND state='PROPOSED'",
            (origin, event_id)).fetchone()
        return row is not None
    except sqlite3.OperationalError:
        return False
    finally:
        con.close()


def _totals(events: list[dict]) -> dict:
    """Compute deterministic machine-readable totals from event results.

    Handles all reservation/notification statuses including PAUSED (kill switch)
    and skipped (resolution/daily-limit) states. "skipped" is counted as
    "withheld" when it follows a DAILY_LIMIT/UNVERIFIED_EVENT reservation,
    but not when it follows a PAUSED kill-switch decision.
    """
    totals = {
        "events": len(events),
        "accepted": 0,
        "duplicate": 0,
        "deferred": 0,
        "missions_reserved": 0,
        "missions_already_reserved": 0,
        "missions_withheld": 0,
        "notifications_queued": 0,
        "notifications_existing": 0,
        "notifications_withheld": 0,
        "resolutions": 0,
    }
    for event in events:
        state = event.get("receiver", "")
        if state == "accepted":
            totals["accepted"] += 1
        elif state == "duplicate":
            totals["duplicate"] += 1
        elif state == "resolution_deferred":
            totals["deferred"] += 1

        if event.get("proposal_status") == "RESOLVED":
            if state == "accepted":
                totals["resolutions"] += 1
            continue

        mission = event.get("reservation", "")
        if mission == "RESERVED_READONLY":
            totals["missions_reserved"] += 1
        elif mission == "ALREADY_RESERVED":
            totals["missions_already_reserved"] += 1
        elif mission in ("DAILY_LIMIT", "BACKPRESSURE", "UNVERIFIED_EVENT"):
            totals["missions_withheld"] += 1
        # PAUSED, "skipped", and other non-attempt states are not counted as withheld

        note = event.get("notification", "")
        if note == "queued":
            totals["notifications_queued"] += 1
        elif note == "already_queued":
            totals["notifications_existing"] += 1
        elif mission in ("DAILY_LIMIT", "BACKPRESSURE", "UNVERIFIED_EVENT") and note == "skipped":
            # "skipped" after a withholding mission counts as withheld
            totals["notifications_withheld"] += 1
        elif note not in ("skipped",):
            # Any other non-queued status counts as withheld
            totals["notifications_withheld"] += 1
        # If mission is PAUSED/skipped and note is "skipped", don't count as withheld
    return totals


def run_fixture(
    *,
    key: bytes | None = None,
    policy: dict | None = None,
    findings: dict | None = None,
    probe: dict | callable | None = None,
    source: str = "x99_worker",
    now: datetime | None = None,
    ledger_db: str | Path | None = None,
    proposal_outbox: str | Path | None = None,
    inbox_db: str | Path | None = None,
    reservations_db: str | Path | None = None,
    notifications_db: str | Path | None = None,
) -> dict:
    """Full synthetic read-only end-to-end fixture.

    Returns a deterministic machine-readable JSON outcome dict with:
      - status: "pipeline_complete" or error status
      - source, opened, resolved, outbox_total
      - events: list of per-event result dicts
      - totals: machine-readable counts
      - execution_started, dispatch_performed, messages_sent: always False
      - kill_switch_decision: from policy if applicable
      - replay_count: number of distinct runs tracked internally
      - findings: the observed snapshot, persisted for replay_fixture()
      - ledger_path/proposal_outbox_path/inbox_db_path/reservations_db_path/
        notifications_db_path: the DB paths reused by replay_fixture()

    The pipeline stops at notification *prepare*.  No dispatch, no OS execution,
    no network, no external sends.

    Note: run_pipeline() internally calls reconcile(); this fixture does NOT
    call reconcile() separately to avoid double-initialisation.
    """
    key = _validate_key(key if key is not None else _TEST_KEY)
    if source not in VALID_SOURCE:
        raise ValueError("unapproved observer source")

    SCHEMA = "atlas.autonomy.policy.v2"
    if policy is None:
        policy = {
            "schema": SCHEMA,
            "enabled": True,
            "kill_switch": False,
            "mode": "observe_only",
            "auto_approve": False,
            "auto_write": False,
            "allowed_actions": ["diagnose_readonly"],
            "origins": ["x99_worker"],
            "kinds": ["worker_stale", "worker_duplicate"],
            "limits": {"daily_readonly_missions": 5, "max_concurrent": 2,
                       "max_total_cost_usd": 0},
        }
    else:
        validate_policy(policy)

    at = _aware(now)

    def _probe():
        if callable(probe):
            return probe()
        if isinstance(probe, dict):
            return probe
        if isinstance(findings, dict):
            # An explicit findings snapshot is a valid observation input when
            # the caller provides no probe.
            return findings
        raise ValueError("snapshot probe must yield a findings dict or callable")

    # Observe exactly once: after key/source/policy/time validation and before
    # any ledger or inbox state exists.  The snapshot is handed to the
    # pipeline as a static findings dict and persisted in the outcome, so
    # replay_fixture() can recover the same observation without re-probing.
    snapshot = _probe()

    # Set up DB paths: use provided paths or create temp directories
    if ledger_db is not None:
        ledger_db = Path(ledger_db)
    else:
        ledger_db = Path(tempfile.mkdtemp()) / "ledger.db"

    if proposal_outbox is not None:
        proposal_outbox = Path(proposal_outbox)
    else:
        proposal_outbox = Path(tempfile.mkdtemp()) / "proposals"

    if inbox_db is not None:
        inbox_db = Path(inbox_db)
    else:
        inbox_db = Path(tempfile.mkdtemp()) / "inbox.db"

    if reservations_db is not None:
        reservations_db = Path(reservations_db)
    else:
        reservations_db = Path(tempfile.mkdtemp()) / "reservations.db"

    if notifications_db is not None:
        notifications_db = Path(notifications_db)
    else:
        notifications_db = Path(tempfile.mkdtemp()) / "notifications.db"

    # Ensure parent directories exist
    for p in [ledger_db, proposal_outbox, inbox_db, reservations_db, notifications_db]:
        p.parent.mkdir(parents=True, exist_ok=True)

    # Set up proposal outbox directory
    proposal_outbox.mkdir(parents=True, exist_ok=True)

    # Run the full pipeline (run_pipeline internally calls reconcile)
    result = _run_pipeline(
        probe=snapshot,
        source=source,
        key=key,
        policy=policy,
        ledger_db=ledger_db,
        proposal_outbox=proposal_outbox,
        inbox_db=inbox_db,
        reservations_db=reservations_db,
        notifications_db=notifications_db,
        now=at,
    )

    events = result.get("events", [])
    totals = _totals(events) if events else {
        "events": 0,
        "accepted": 0,
        "duplicate": 0,
        "deferred": 0,
        "missions_reserved": 0,
        "missions_already_reserved": 0,
        "missions_withheld": 0,
        "notifications_queued": 0,
        "notifications_existing": 0,
        "notifications_withheld": 0,
        "resolutions": 0,
    }

    # Determine kill-switch decision from policy
    ks_decision = "MONITORING"
    if policy.get("kill_switch"):
        ks_decision = "PAUSED"

    outcome = {
        "status": result.get("status", "pipeline_complete"),
        "source": result.get("source", source),
        "opened": result.get("opened", []),
        "resolved": result.get("resolved", []),
        "outbox_total": result.get("outbox_total", 0),
        "events": events,
        "totals": totals,
        "execution_started": False,
        "dispatch_performed": False,
        "messages_sent": 0,
        "kill_switch_decision": ks_decision,
        "replay_count": 1,
        "findings": snapshot,
        "ledger_path": str(ledger_db),
        "proposal_outbox_path": str(proposal_outbox),
        "inbox_db_path": str(inbox_db),
        "reservations_db_path": str(reservations_db),
        "notifications_db_path": str(notifications_db),
    }

    return outcome


def replay_fixture(
    previous_outcome: dict,
    *,
    key: bytes | None = None,
    findings: dict | None = None,
    probe: dict | callable | None = None,
    now: datetime | None = None,
) -> dict:
    """Re-run the fixture on the persisted state of a previous outcome.

    The DB paths recorded in `previous_outcome` are reused verbatim, and the
    observation snapshot recorded in `previous_outcome["findings"]` is
    recovered so the replay reconciles against exactly the same findings and
    stays idempotent (no new mission, no duplicate notification, no state
    clearing).  An explicit `probe` or `findings` argument always overrides
    the persisted snapshot; if none exists, the documented default snapshot
    is used.  No SQLite DELETE and no state reset is ever performed."""
    key = _validate_key(key if key is not None else _TEST_KEY)
    if previous_outcome is None:
        previous_outcome = {}
    if not isinstance(previous_outcome, dict):
        raise ValueError("previous outcome dict is required")

    # Extract DB paths from previous outcome if available
    ledger_db = Path(previous_outcome["ledger_path"]) if previous_outcome and previous_outcome.get("ledger_path") else None
    proposal_outbox = Path(previous_outcome["proposal_outbox_path"]) if previous_outcome and previous_outcome.get("proposal_outbox_path") else None
    inbox_db = Path(previous_outcome["inbox_db_path"]) if previous_outcome and previous_outcome.get("inbox_db_path") else None
    reservations_db = Path(previous_outcome["reservations_db_path"]) if previous_outcome and previous_outcome.get("reservations_db_path") else None
    notifications_db = Path(previous_outcome["notifications_db_path"]) if previous_outcome and previous_outcome.get("notifications_db_path") else None

    # If no paths from prior outcome, create fresh temp dirs
    if not ledger_db:
        ledger_db = Path(tempfile.mkdtemp()) / "ledger.db"
    if not proposal_outbox:
        proposal_outbox = Path(tempfile.mkdtemp()) / "proposals"
    if not inbox_db:
        inbox_db = Path(tempfile.mkdtemp()) / "inbox.db"
    if not reservations_db:
        reservations_db = Path(tempfile.mkdtemp()) / "reservations.db"
    if not notifications_db:
        notifications_db = Path(tempfile.mkdtemp()) / "notifications.db"

    for p in [ledger_db, proposal_outbox, inbox_db, reservations_db, notifications_db]:
        p.parent.mkdir(parents=True, exist_ok=True)

    SCHEMA = "atlas.autonomy.policy.v2"
    policy = {
        "schema": SCHEMA,
        "enabled": True,
        "kill_switch": False,
        "mode": "observe_only",
        "auto_approve": False,
        "auto_write": False,
        "allowed_actions": ["diagnose_readonly"],
        "origins": ["x99_worker"],
        "kinds": ["worker_stale", "worker_duplicate"],
        "limits": {"daily_readonly_missions": 5, "max_concurrent": 2,
                   "max_total_cost_usd": 0},
    }

    at = _aware(now)

    # Recover the observation: explicit probe > explicit findings > persisted
    # snapshot from the previous outcome > documented default snapshot.  The
    # snapshot is observed exactly once and handed to the pipeline, which
    # reconciles the persisted ledger against it (no DELETE, no reset).
    if probe is None:
        recovered = (findings if findings is not None
                     else previous_outcome.get("findings"))
        if recovered is None:
            recovered = {"worker_stale": {"summary": "heartbeat lagging"}}
        probe = recovered

    def _probe():
        if callable(probe):
            return probe()
        if isinstance(probe, dict):
            return probe
        raise ValueError("snapshot probe must yield a findings dict or callable")

    snapshot = _probe()

    result = _run_pipeline(
        probe=snapshot,
        source="x99_worker",
        key=key,
        policy=policy,
        ledger_db=ledger_db,
        proposal_outbox=proposal_outbox,
        inbox_db=inbox_db,
        reservations_db=reservations_db,
        notifications_db=notifications_db,
        now=at,
    )

    events = result.get("events", [])
    totals = _totals(events) if events else {
        "events": 0,
        "accepted": 0,
        "duplicate": 0,
        "deferred": 0,
        "missions_reserved": 0,
        "missions_already_reserved": 0,
        "missions_withheld": 0,
        "notifications_queued": 0,
        "notifications_existing": 0,
        "notifications_withheld": 0,
        "resolutions": 0,
    }

    ks_decision = "MONITORING"
    if policy.get("kill_switch"):
        ks_decision = "PAUSED"

    outcome = {
        "status": result.get("status", "pipeline_complete"),
        "source": result.get("source", "x99_worker"),
        "opened": result.get("opened", []),
        "resolved": result.get("resolved", []),
        "outbox_total": result.get("outbox_total", 0),
        "events": events,
        "totals": totals,
        "execution_started": False,
        "dispatch_performed": False,
        "messages_sent": 0,
        "kill_switch_decision": ks_decision,
        "replay_count": previous_outcome.get("replay_count", 0) + 1 if previous_outcome else 1,
        "findings": snapshot,
        "ledger_path": str(ledger_db),
        "proposal_outbox_path": str(proposal_outbox),
        "inbox_db_path": str(inbox_db),
        "reservations_db_path": str(reservations_db),
        "notifications_db_path": str(notifications_db),
    }

    return outcome