"""Atlas shadow pre-flight adapter: strictly observe-only composition of CP11
system_supervision (plus the pure validators of incident_pipeline) as a safe
pre-flight observer. Never executes commands, sends messages, alters services,
uses privileged paths, or auto-fixes.

Hard purity contract of this module:
- incident_pipeline.run_pipeline() is NEVER called. It mutates the durable
  ledger and materialises proposal-outbox/inbox/reservations/notifications
  databases, including relative-path writes. Ledger and WAL state are read
  exclusively through system_supervision.observe() (read-only SQL).
- Clock skew is derived from trusted host instants (the machine clock through
  trusted_host_now()), never from a UTC timezone offset: a +00:00 offset proves
  nothing about clock agreement.
- All state is caller-supplied; no production key, secret or state path is
  embedded or defaulted. The bridge observes and reports — it never writes
  autonomy.
"""

import sys
from datetime import datetime, timezone

import system_supervision as ss
import incident_pipeline

# ---------------------------------------------------------------------------
# Failure-close reason codes (clear, machine-readable)
# ---------------------------------------------------------------------------

REASON_OK = "OK"
REASON_UTC_SKEW = "UTC_SKEW"
REASON_MISSING_HEARTBEAT = "MISSING_HEARTBEAT"
REASON_STALE_HEARTBEAT = "STALE_HEARTBEAT"
REASON_FUTURE_HEARTBEAT = "FUTURE_HEARTBEAT"
REASON_MALFORMED_HEARTBEAT = "MALFORMED_HEARTBEAT"
REASON_DISABLED_POLICY = "DISABLED_POLICY"
REASON_KILL_SWITCH = "KILL_SWITCH"
REASON_UNKNOWN_WAL = "UNKNOWN_WAL"
REASON_MISSING_KEY = "MISSING_KEY"
REASON_UNKNOWN_WAL_STATUS = "UNKNOWN_WAL_STATUS"


# ---------------------------------------------------------------------------
# Helper: UTC-skew check against the trusted host clock.  Fails closed when
# the claimed observation instant cannot be verified against the host instant
# or drifts from it beyond the historical x99 / Pentium tolerance (~2 min).
# Skew is ALWAYS measured between verifiable UTC instants; a UTC timezone
# offset is never used as skew evidence.
# ---------------------------------------------------------------------------

SKEW_TOLERANCE_SECONDS = 120


def trusted_host_now() -> datetime:
    """The single trusted host instant (UTC): the machine's own clock.

    This is the only reference the skew check trusts. Detector heartbeats,
    ledger rows and caller-supplied timestamps are never skew evidence.
    """
    return datetime.now(timezone.utc)


def _utc_instant(value) -> datetime | None:
    """Return *value* as a UTC instant, or None when it is unverifiable
    (not a datetime, naive, or without a usable UTC offset)."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def utc_skew_seconds(now, *, host_now: datetime | None = None) -> float | None:
    """Clock skew in seconds between the claimed observation instant and the
    trusted host instant.  None means "unverifiable" and must fail closed."""
    claimed = _utc_instant(now)
    host = _utc_instant(trusted_host_now() if host_now is None else host_now)
    if claimed is None or host is None:
        return None
    return abs((claimed - host).total_seconds())


def check_utc_skew(now: datetime, *, tolerance_seconds: int = SKEW_TOLERANCE_SECONDS) -> tuple[bool, str]:
    """Return (ok, reason).

    Skew = |claimed observation instant - trusted host instant|.  Historical
    x99 class: tolerance ~120s (2 minutes).  Pentium-class drift is bounded by
    the same 120s in observe-only mode.  A naive or otherwise unverifiable
    *now* fails closed with UTC_SKEW; the UTC timezone offset of *now* is
    deliberately ignored because it says nothing about clock agreement.
    """
    skew = utc_skew_seconds(now)
    if skew is None or skew > tolerance_seconds:
        return False, REASON_UTC_SKEW
    return True, REASON_OK


# ---------------------------------------------------------------------------
# Core shadow pre-flight adapter
# ---------------------------------------------------------------------------

def shadow_pre_flight(
    *,
    provider,
    key: bytes,
    policy: dict,
    ledger_path: str | None = None,
    stale_window_seconds: int | None = None,
    now: datetime | None = None,
) -> dict:
    """Read-only shadow pre-flight adapter.

    Composes system_supervision.observe() as a pure function with injected
    fixtures and returns a readiness/observability report that *fails closed*
    on any untrusted or unconfigured condition.

    The returned report always contains a "reason" field. REASON_OK indicates
    all checks passed. Any other reason means the bridge refuses to proceed.

    Design notes:
    - incident_pipeline is used ONLY for pure validation (_validate_key and
      validate_policy); neither of them touches state.
    - incident_pipeline.run_pipeline() is never executed here: it writes the
      durable ledger and materialises outbox/inbox/reservations/notifications
      databases, including relative-path writes. Ledger and WAL facts reach
      the report exclusively through system_supervision.observe(), which reads
      them with read-only SQL.
    - Clock skew is |now - trusted_host_now()| in seconds. It is derived from
      trusted host instants, never from a UTC timezone offset, and fails closed
      beyond the 120 s historical tolerance or when *now* is unverifiable.
    - incident_pipeline.validate_policy(policy) is called with the full autonomy
      policy schema ("atlas.autonomy.policy.v2") — this is separate from the
      kill-switch gate.
    - system_supervision.kill_switch_gate() is NOT called directly because it
      requires exactly three fields (schema/enabled/kill_switch) with the
      killswitch schema ("atlas.supervisor.killswitch.v1"), which is incompatible
      with the full autonomy policy required by incident_pipeline.validate_policy().
      The kill-switch decision is inlined here with identical logic:
      kill_switch OR (NOT enabled) => PAUSED.
    - For ss.observe() a minimal 3-field policy is constructed from the full
      policy's enabled/kill_switch values; the observe() function internally
      calls kill_switch_gate(), which succeeds with this minimal policy.
    - ValueError from ss.observe() caused by a future heartbeat observed_at is
      converted to REASON_FUTURE_HEARTBEAT so the bridge reports the exact
      failure mode rather than a generic probe error.
    """

    # -------------------------------------------------------------
    # 1. Fail fast: missing / invalid 32-byte HMAC key
    # -------------------------------------------------------------
    try:
        incident_pipeline._validate_key(key)
    except (ValueError, TypeError):
        return {
            "schema": "atlas.shadow.bridge.v1",
            "reason": REASON_MISSING_KEY,
            "read_only": True,
            "execution_started": False,
            "messages_sent": False,
            "services_restarted": False,
            "kill_switch": {"schema": ss.KILL_SWITCH_SCHEMA, "decision": "UNKNOWN",
                            "enabled": False, "engaged": False,
                            "independent_of_observations": True},
            "utc_skew": None,
        }

    # -------------------------------------------------------------
    # 2. Clock-skew check against the trusted host instant (fails closed).
    # Skew = |now - trusted host clock|; the UTC timezone offset of *now* is
    # never used as evidence of clock agreement.
    # -------------------------------------------------------------
    if now is None:
        now = trusted_host_now()
    skew_ok, skew_reason = check_utc_skew(now)
    if not skew_ok:
        return {
            "schema": "atlas.shadow.bridge.v1",
            "reason": REASON_UTC_SKEW,
            "utc_skew_seconds": utc_skew_seconds(now),
            "tolerance_seconds": SKEW_TOLERANCE_SECONDS,
            "read_only": True,
            "execution_started": False,
            "messages_sent": False,
            "services_restarted": False,
            "kill_switch": {"schema": ss.KILL_SWITCH_SCHEMA, "decision": "UNKNOWN",
                            "enabled": False, "engaged": False,
                            "independent_of_observations": True},
        }

    # -------------------------------------------------------------
    # 3. Policy validation (fails closed on disabled / no policy)
    # -------------------------------------------------------------
    try:
        incident_pipeline.validate_policy(policy)
    except (ValueError, PermissionError):
        return {
            "schema": "atlas.shadow.bridge.v1",
            "reason": REASON_DISABLED_POLICY,
            "read_only": True,
            "execution_started": False,
            "messages_sent": False,
            "services_restarted": False,
            "kill_switch": {"schema": ss.KILL_SWITCH_SCHEMA, "decision": "UNKNOWN",
                            "enabled": policy.get("enabled", False),
                            "engaged": policy.get("kill_switch", False),
                            "independent_of_observations": True},
        }

    # -------------------------------------------------------------
    # 4. Kill-switch gate (pure, clock-free; only the policy document decides).
    # Inlined here because system_supervision.kill_switch_gate() requires exactly
    # three fields (schema/enabled/kill_switch) with the killswitch schema,
    # which is incompatible with the full autonomy policy required by
    # incident_pipeline.validate_policy().  The logic is identical:
    #   kill_switch OR (NOT enabled)  =>  PAUSED
    #   otherwise                                   =>  MONITORING
    # -------------------------------------------------------------
    kill_sw = policy.get("kill_switch", False)
    enbl = policy.get("enabled", True)
    if kill_sw or not enbl:
        kill_mode = "PAUSED"
    else:
        kill_mode = "MONITORING"

    # -------------------------------------------------------------
    # 5. Early return: kill switch engaged
    # -------------------------------------------------------------
    if kill_mode == "PAUSED":
        return {
            "schema": "atlas.shadow.bridge.v1",
            "reason": REASON_KILL_SWITCH,
            "read_only": True,
            "execution_started": False,
            "messages_sent": False,
            "services_restarted": False,
            "kill_switch": {"schema": ss.KILL_SWITCH_SCHEMA, "decision": "PAUSED",
                            "enabled": policy["enabled"],
                            "engaged": policy["kill_switch"],
                            "independent_of_observations": True},
        }

    # -------------------------------------------------------------
    # 6. System supervision observation (pure, read-only).
    # Build a minimal 3-field policy for ss.observe() so that the internal
    # kill_switch_gate() call succeeds.  The full policy is used for
    # incident_pipeline.validate_policy() above.
    # -------------------------------------------------------------
    observe_policy = {
        "schema": ss.KILL_SWITCH_SCHEMA,
        "enabled": policy["enabled"],
        "kill_switch": policy["kill_switch"],
    }

    try:
        supervision_report = ss.observe(
            provider=provider,
            policy=observe_policy,
            ledger_path=ledger_path,
            now=now,
            stale_window_seconds=stale_window_seconds or ss.STALE_WINDOW_SECONDS,
        )
    except ValueError as ve:
        # ss.observe() raises ValueError when a heartbeat's observed_at is
        # in the future (ss.observe -> assess_heartbeat -> utc rejects it).
        # Convert to the specific future-heartbeat reason code so the bridge
        # reports the exact failure mode.
        if "future timestamp" in str(ve).lower():
            return {
                "schema": "atlas.shadow.bridge.v1",
                "reason": REASON_FUTURE_HEARTBEAT,
                "read_only": True,
                "execution_started": False,
                "messages_sent": False,
                "services_restarted": False,
                "kill_switch": {"schema": ss.KILL_SWITCH_SCHEMA, "decision": "UNKNOWN",
                                "enabled": policy["enabled"],
                                "engaged": policy["kill_switch"],
                                "independent_of_observations": True},
            }
        # Any other ValueError from supervision fails closed
        return {
            "schema": "atlas.shadow.bridge.v1",
            "reason": REASON_MISSING_HEARTBEAT,
            "read_only": True,
            "execution_started": False,
            "messages_sent": False,
            "services_restarted": False,
            "kill_switch": {"schema": ss.KILL_SWITCH_SCHEMA, "decision": "UNKNOWN",
                            "enabled": policy["enabled"],
                            "engaged": policy["kill_switch"],
                            "independent_of_observations": True},
            "observation_error": str(ve),
        }
    except Exception as exc:
        # Any unexpected failure from supervision fails closed
        return {
            "schema": "atlas.shadow.bridge.v1",
            "reason": REASON_MISSING_HEARTBEAT,
            "read_only": True,
            "execution_started": False,
            "messages_sent": False,
            "services_restarted": False,
            "kill_switch": {"schema": ss.KILL_SWITCH_SCHEMA, "decision": "UNKNOWN",
                            "enabled": policy["enabled"],
                            "engaged": policy["kill_switch"],
                            "independent_of_observations": True},
            "observation_error": str(exc),
        }

    # -------------------------------------------------------------
    # 7. Inspect heartbeats for missing / future / stale conditions
    # -------------------------------------------------------------
    beats = supervision_report.get("heartbeats", {})
    for observer, entry in beats.items():
        status = entry.get("status")
        if status == "MISSING":
            return {
                "schema": "atlas.shadow.bridge.v1",
                "reason": REASON_MISSING_HEARTBEAT,
                "read_only": True,
                "execution_started": False,
                "messages_sent": False,
                "services_restarted": False,
                "kill_switch": {"schema": ss.KILL_SWITCH_SCHEMA, "decision": "UNKNOWN",
                                "enabled": policy["enabled"],
                                "engaged": policy["kill_switch"],
                                "independent_of_observations": True},
                "heartbeat": observer,
                "heartbeat_status": status,
            }
        if status == "STALE":
            return {
                "schema": "atlas.shadow.bridge.v1",
                "reason": REASON_STALE_HEARTBEAT,
                "read_only": True,
                "execution_started": False,
                "messages_sent": False,
                "services_restarted": False,
                "kill_switch": {"schema": ss.KILL_SWITCH_SCHEMA, "decision": "UNKNOWN",
                                "enabled": policy["enabled"],
                                "engaged": policy["kill_switch"],
                                "independent_of_observations": True},
                "heartbeat": observer,
                "heartbeat_status": status,
                "age_seconds": entry.get("age_seconds"),
                "stale_window_seconds": entry.get("stale_window_seconds"),
            }
        if status == "HEALTHY":
            # Double-check no future/invalid observation data slipped through
            # the observe() gate (it rejects future timestamps but we double-check
            # here as a safety net in case ss.observe() was mocked/bypassed).
            # Fail closed on empty, malformed or naive observed_at instead of
            # silently swallowing the parse error.
            observed_at_raw = entry.get("observed_at", "")
            observed_at_str = (observed_at_raw if isinstance(observed_at_raw, str)
                               else repr(observed_at_raw))
            malformed_report = {
                "schema": "atlas.shadow.bridge.v1",
                "reason": REASON_MALFORMED_HEARTBEAT,
                "read_only": True,
                "execution_started": False,
                "messages_sent": False,
                "services_restarted": False,
                "kill_switch": {"schema": ss.KILL_SWITCH_SCHEMA, "decision": "UNKNOWN",
                                "enabled": policy["enabled"],
                                "engaged": policy["kill_switch"],
                                "independent_of_observations": True},
                "heartbeat": observer,
                "heartbeat_status": status,
                "observed_at": observed_at_str,
            }
            if observed_at_raw is None or observed_at_raw == "":
                return malformed_report
            if isinstance(observed_at_raw, datetime):
                observed_at = observed_at_raw
            elif isinstance(observed_at_raw, str):
                try:
                    observed_at = datetime.fromisoformat(observed_at_raw)
                except (ValueError, TypeError):
                    return malformed_report
            else:
                return malformed_report
            if (not isinstance(observed_at, datetime)
                    or observed_at.tzinfo is None
                    or observed_at.utcoffset() is None):
                return malformed_report
            observed_instant = _utc_instant(observed_at)
            now_instant = _utc_instant(now)
            if observed_instant is None or now_instant is None:
                return malformed_report
            if observed_instant > now_instant:
                return {
                    "schema": "atlas.shadow.bridge.v1",
                    "reason": REASON_FUTURE_HEARTBEAT,
                    "read_only": True,
                    "execution_started": False,
                    "messages_sent": False,
                    "services_restarted": False,
                    "kill_switch": {"schema": ss.KILL_SWITCH_SCHEMA, "decision": "UNKNOWN",
                                    "enabled": policy["enabled"],
                                    "engaged": policy["kill_switch"],
                                    "independent_of_observations": True},
                    "heartbeat": observer,
                    "heartbeat_status": status,
                    "observed_at": observed_at_str,
                }

    # -------------------------------------------------------------
    # 8. Ledger / WAL status (read-only SQL; fails closed on unknown WAL)
    # -------------------------------------------------------------
    alarms = supervision_report.get("alarms", {})
    wal_reason = alarms.get("reason")
    if wal_reason in ("live_wal_without_shared_memory", "wal_status_unavailable",
                       "open_failed", "missing_ledger", "unexpected_ledger_schema",
                       "read_failed"):
        return {
            "schema": "atlas.shadow.bridge.v1",
            "reason": REASON_UNKNOWN_WAL_STATUS,
            "read_only": True,
            "execution_started": False,
            "messages_sent": False,
            "services_restarted": False,
            "kill_switch": {"schema": ss.KILL_SWITCH_SCHEMA, "decision": "UNKNOWN",
                            "enabled": policy["enabled"],
                            "engaged": policy["kill_switch"],
                            "independent_of_observations": True},
            "wal_status": wal_reason,
            "alarms": alarms,
        }

    # -------------------------------------------------------------
    # 9. Observe-only probe: no pipeline execution, no writes.
    # incident_pipeline.run_pipeline() is deliberately unreachable here. It
    # would call durable_incidents.reconcile() (ledger writes) and
    # materialize() (relative-path outbox plus inbox/reservations/notifications
    # databases), violating the read-only contract of this bridge. Ledger and
    # WAL facts were already observed read-only in step 8 through
    # system_supervision.observe() -> _alarms(). The report states plainly
    # that nothing was executed.
    # -------------------------------------------------------------
    pipeline_report = {
        "status": "not_executed",
        "mode": "observe_only",
        "events": [],
        "totals": {
            "events": 0, "accepted": 0, "duplicate": 0,
            "deferred": 0, "missions_reserved": 0,
            "missions_already_reserved": 0,
            "missions_withheld": 0,
            "notifications_queued": 0,
            "notifications_existing": 0,
            "notifications_withheld": 0,
            "resolutions": 0,
        },
    }

    # -------------------------------------------------------------
    # 10. Compose final observability report
    # -------------------------------------------------------------
    report = {
        "schema": "atlas.shadow.bridge.v1",
        "reason": REASON_OK,
        "mode": supervision_report.get("mode", "UNKNOWN"),
        "supervision": supervision_report.get("supervision", "UNKNOWN"),
        "kill_switch": supervision_report.get("kill_switch", {
            "schema": ss.KILL_SWITCH_SCHEMA,
            "decision": kill_mode,
            "enabled": policy["enabled"],
            "engaged": policy["kill_switch"],
            "independent_of_observations": True,
        }),
        "utc_skew_seconds": utc_skew_seconds(now),
        "tolerance_seconds": SKEW_TOLERANCE_SECONDS,
        "heartbeats": supervision_report.get("heartbeats", {}),
        "alarms": alarms,
        "pipeline": {
            "status": pipeline_report.get("status", "not_executed"),
            "mode": pipeline_report.get("mode", "observe_only"),
            "events_count": len(pipeline_report.get("events", [])),
            "totals": pipeline_report.get("totals", {
                "events": 0, "accepted": 0, "duplicate": 0,
                "deferred": 0, "missions_reserved": 0,
                "missions_already_reserved": 0,
                "missions_withheld": 0,
                "notifications_queued": 0,
                "notifications_existing": 0,
                "notifications_withheld": 0,
                "resolutions": 0,
            }),
        },
        "read_only": True,
        "execution_started": False,
        "messages_sent": False,
        "services_restarted": False,
    }

    return report


# ---------------------------------------------------------------------------
# Convenience: quick-check entry point (no side effects, all fixtures injected)
# ---------------------------------------------------------------------------

def quick_check(
    *,
    provider,          # mapping observer -> heartbeat dict or None
    key: bytes,        # 32-byte HMAC key
    policy: dict,      # autonomy policy
    ledger_path: str | None = None,
    now: datetime | None = None,
) -> dict:
    """Minimal shadow pre-flight check. Same contract as shadow_pre_flight
    but with a simplified provider (raw dict mapping rather than callable).
    Returns the full observability report with a reason code."""
    if now is None:
        now = trusted_host_now()

    # Build a callable provider from the dict
    def _provider(observer):
        return provider.get(observer)

    return shadow_pre_flight(
        provider=_provider,
        key=key,
        policy=policy,
        ledger_path=ledger_path,
        now=now,
    )