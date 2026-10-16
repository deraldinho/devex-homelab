"""CP11 read-only supervisor observability: report facts, never take action.

Heartbeats for the Windows worker observer and the Linux systemd observer are
read through an injected provider seam, so nothing in this module probes a real
service. The durable SQLite ledger is opened with mode=ro and query_only=ON.
Live WAL changes must be visible: immutable=1 can produce false CLEAR alarms.
SQLite may manage WAL shared-memory sidecars, but this module never changes rows. The kill-switch
gate is a pure function of its own policy document: observations never flip it
and it never changes an observation. Only verifiable UTC instants are accepted;
naive, future, stale or duplicated detector data fails closed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
from sqlite_uri_safety import readonly_uri

SCHEMA = "atlas.supervisor.report.v1"
HEARTBEAT_SCHEMA = "atlas.supervisor.heartbeat.v1"
KILL_SWITCH_SCHEMA = "atlas.supervisor.killswitch.v1"
OBSERVERS = ("windows_worker_observer", "linux_systemd_observer")
STALE_WINDOW_SECONDS = 120
MAX_STALE_WINDOW_SECONDS = 86_400
_GATE_FIELDS = {"schema", "enabled", "kill_switch"}
_BEAT_FIELDS = {"schema", "observer", "detector", "sequence", "observed_at"}
_DETECTOR = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}\Z")


def _reference(now, field="now") -> datetime:
    if not isinstance(now, datetime):
        raise ValueError(field + ": datetime required")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError(field + ": naive timestamp rejected")
    return now.astimezone(timezone.utc)


def utc(value, *, now, field="timestamp") -> datetime:
    """Verifiable UTC instant: timezone-aware, and never ahead of *now*."""
    reference = _reference(now, field=field + " reference")
    when = value
    if isinstance(value, str):
        try:
            when = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError(field + ": unparseable timestamp") from None
    instant = _reference(when, field=field)
    if instant > reference:
        raise ValueError(field + ": future timestamp rejected")
    return instant


def _window(value):
    if type(value) not in (int, float) or not 0 < value <= MAX_STALE_WINDOW_SECONDS:
        raise ValueError("stale window must be within (0, %d] seconds"
                         % MAX_STALE_WINDOW_SECONDS)
    return value


def kill_switch_gate(policy) -> str:
    """Pure, clock-free kill switch; only the policy document decides."""
    if not isinstance(policy, dict):
        raise ValueError("kill-switch policy must be a mapping")
    if set(policy) != _GATE_FIELDS:
        raise ValueError("kill-switch policy must contain exactly "
                         + "/".join(sorted(_GATE_FIELDS)))
    if policy["schema"] != KILL_SWITCH_SCHEMA:
        raise ValueError("unknown kill-switch policy schema")
    if type(policy["enabled"]) is not bool or type(policy["kill_switch"]) is not bool:
        raise ValueError("explicit boolean flags required")
    if policy["kill_switch"] or not policy["enabled"]:
        return "PAUSED"
    return "MONITORING"


def assess_heartbeat(record, *, observer, now,
                     stale_window_seconds=STALE_WINDOW_SECONDS) -> dict:
    """Validate one detector sample and classify it HEALTHY or STALE."""
    window = _window(stale_window_seconds)
    if observer not in OBSERVERS:
        raise ValueError("unknown observer")
    if not isinstance(record, dict) or set(record) != _BEAT_FIELDS:
        raise ValueError("unexpected heartbeat fields")
    if record["schema"] != HEARTBEAT_SCHEMA:
        raise ValueError("unknown heartbeat schema")
    if record["observer"] != observer:
        raise ValueError("observer mismatch: expected " + str(observer))
    detector = record["detector"]
    sequence = record["sequence"]
    if not isinstance(detector, str) or _DETECTOR.fullmatch(detector) is None:
        raise ValueError("invalid detector id")
    if type(sequence) is not int or sequence < 0:
        raise ValueError("invalid detector sequence")
    reference = _reference(now)
    instant = utc(record["observed_at"], now=reference, field="observed_at")
    age = (reference - instant).total_seconds()
    return {"status": "STALE" if age > window else "HEALTHY",
            "observed_at": instant.isoformat(), "age_seconds": age,
            "detector": detector, "sequence": sequence,
            "stale_window_seconds": window}


def _records(provider, observer) -> list:
    provided = provider(observer)
    if provided is None:
        return []
    if isinstance(provided, dict):
        return [provided]
    if isinstance(provided, list) and all(isinstance(item, dict) for item in provided):
        return provided
    raise ValueError("provider must return dict, list of dicts or None for "
                     + observer)


def _alarms(db_path, *, now) -> dict:
    """Read live committed WAL changes via read-only SQL; never alter rows."""
    if db_path is None:
        return {"ledger_present": False, "open_alarms": None,
                "status": "UNKNOWN", "reason": "not_configured"}
    path = Path(db_path)
    if not path.is_file():
        return {"ledger_present": False, "open_alarms": None,
                "status": "UNKNOWN", "reason": "missing_ledger"}
    # A live WAL requires normal read-only mode; immutable=1 silently ignores it.
    # If SQLite cannot use the matching shm file, never claim the ledger CLEAR.
    wal = Path(str(path) + "-wal")
    shm = Path(str(path) + "-shm")
    try:
        active_wal = wal.is_file() and wal.stat().st_size > 0
    except OSError:
        return {"ledger_present": True, "open_alarms": None,
                "status": "UNKNOWN", "reason": "wal_status_unavailable"}
    if active_wal and not shm.is_file():
        return {"ledger_present": True, "open_alarms": None,
                "status": "UNKNOWN", "reason": "live_wal_without_shared_memory"}
    # With no nonempty WAL, immutable mode avoids creating SQLite sidecars.
    # With WAL + SHM present, mode=ro reads committed WAL records.
    options = "?mode=ro" if active_wal else "?mode=ro&immutable=1"
    try:
        con = sqlite3.connect(readonly_uri(path, immutable=not active_wal), uri=True, timeout=10)
    except sqlite3.Error:
        return {"ledger_present": True, "open_alarms": None,
                "status": "UNKNOWN", "reason": "open_failed"}
    try:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        schema = con.execute("""SELECT 1 FROM sqlite_master
                                WHERE type='table' AND name='incidents'""").fetchone()
        if schema is None:
            return {"ledger_present": True, "open_alarms": None, "status": "UNKNOWN",
                    "reason": "unexpected_ledger_schema"}
        rows = con.execute("""SELECT opened_at, updated_at FROM incidents
                              WHERE status='open' ORDER BY id""").fetchall()
    except sqlite3.Error:
        return {"ledger_present": True, "open_alarms": None,
                "status": "UNKNOWN", "reason": "read_failed"}
    finally:
        con.close()
    # A naive or future row is tamper evidence: reject the whole report.
    for row in rows:
        utc(row["opened_at"], now=now, field="incidents.opened_at")
        utc(row["updated_at"], now=now, field="incidents.updated_at")
    if rows:
        return {"ledger_present": True, "open_alarms": len(rows),
                "status": "ALARM", "reason": None}
    return {"ledger_present": True, "open_alarms": 0,
            "status": "CLEAR", "reason": None}


def observe(*, provider, policy, ledger_path=None, now=None,
            stale_window_seconds=STALE_WINDOW_SECONDS) -> dict:
    """Read-only snapshot: no service probe, no write, no message, no restart."""
    if not callable(provider):
        raise ValueError("observer provider callable required")
    window = _window(stale_window_seconds)
    mode = kill_switch_gate(policy)  # independent gate, evaluated first
    reference = _reference(now if now is not None else datetime.now(timezone.utc))
    beats = {}
    seen = set()
    for observer in OBSERVERS:
        records = _records(provider, observer)
        if not records:
            beats[observer] = {"status": "MISSING", "records": 0,
                               "observed_at": None, "age_seconds": None,
                               "detector": None, "sequence": None,
                               "stale_window_seconds": window}
            continue
        assessed = [assess_heartbeat(item, observer=observer, now=reference,
                                     stale_window_seconds=window)
                    for item in records]
        for item in assessed:
            key = (item["detector"], item["sequence"])
            if key in seen:
                raise ValueError("duplicate detector input rejected: %s#%d" % key)
            seen.add(key)
        oldest = max(assessed, key=lambda item: item["age_seconds"])
        beats[observer] = dict(oldest, records=len(assessed),
                               status=("STALE"
                                       if any(item["status"] == "STALE"
                                              for item in assessed)
                                       else "HEALTHY"))
    alarms = _alarms(ledger_path, now=reference)
    supervision = "HEALTHY"
    if any(entry["status"] != "HEALTHY" for entry in beats.values()) \
            or alarms["status"] != "CLEAR":
        supervision = "DEGRADED"
    return {"schema": SCHEMA, "generated_at": reference.isoformat(),
            "mode": mode, "supervision": supervision, "heartbeats": beats,
            "alarms": alarms,
            "kill_switch": {"schema": KILL_SWITCH_SCHEMA, "decision": mode,
                            "enabled": policy["enabled"],
                            "engaged": policy["kill_switch"],
                            "independent_of_observations": True},
            "read_only": True, "execution_started": False,
            "messages_sent": False, "services_restarted": False}
