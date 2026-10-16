"""CP14 read-only operational preflight aggregator.

This module NEVER touches a service, network endpoint, OS task, sandbox,
notification transport, lease store or production secret. Every observation is
caller-injected. Missing or unverifiable observations fail closed and are
reported as BLOCKED_NOT_READY with explicit, machine-readable block codes.

The module only composes existing pure validators (shadow_clock_guard) and pure
in-memory checks. No side effects: no files are created, no commands executed.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Mapping, Optional

SCHEMA = "atlas.cp14.operational_preflight.v1"
STATUS_READY = "READY"
STATUS_BLOCKED_NOT_READY = "BLOCKED_NOT_READY"

CHECK_NAMES = (
    "x99_w32time",
    "pentium_ntp",
    "reference_timestamps",
    "ssh_transport",
    "os_sandbox",
    "notification_recipient_ack",
    "lease_recovery_rollback",
    "production_hmac_key_provisioning",
    "cognitive_service_bridge",
)

MAX_CAPTURE_AGE_SECONDS = 300
DRIFT_TOLERANCE_SECONDS = 60
SKEW_TOLERANCE_SECONDS = 60

BLOCK_CODE_MISSING_OBSERVATION = "BLOCKED_NOT_READY_MISSING_OBSERVATION"
BLOCK_CODE_INVALID_INPUT = "BLOCKED_NOT_READY_INVALID_INPUT"
BLOCK_CODES = {
    "x99_w32time": "BLOCKED_NOT_READY_X99_W32TIME_STOPPED_OR_MANUAL",
    "pentium_ntp": "BLOCKED_NOT_READY_PENTIUM_NTP_UNHEALTHY",
    "reference_timestamps": "BLOCKED_NOT_READY_REFERENCE_TIMESTAMPS_INVALID",
    "ssh_transport": "BLOCKED_NOT_READY_SSH_TRANSPORT_UNREACHABLE",
    "os_sandbox": "BLOCKED_NOT_READY_OS_SANDBOX_UNAVAILABLE",
    "notification_recipient_ack": "BLOCKED_NOT_READY_NOTIFICATION_RECIPIENT_UNACKED",
    "lease_recovery_rollback": "BLOCKED_NOT_READY_LEASE_RECOVERY_NOT_READY",
    "production_hmac_key_provisioning": "BLOCKED_NOT_READY_PRODUCTION_HMAC_KEY_NOT_PROVISIONED",
    "cognitive_service_bridge": "BLOCKED_NOT_READY_COGNITIVE_SERVICE_BRIDGE_UNAVAILABLE",
}
# historic drift has its own code when timestamps exist but skew is excessive
BLOCK_CODE_HISTORIC_DRIFT = "BLOCKED_NOT_READY_HISTORIC_CLOCK_DRIFT_120S"
BLOCK_CODE_CAPTURE_STALE = "BLOCKED_NOT_READY_REFERENCE_CAPTURE_STALE"

try:
    import shadow_clock_guard as _scg
except Exception:  # pragma: no cover - optional dependency
    _scg = None


def _mapping(value: Any) -> dict:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return {str(k): v for k, v in value.items()}
    if hasattr(value, "__dict__"):
        return {str(k): v for k, v in vars(value).items()}
    return {}


def _norm_key(key: str) -> str:
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


def _find_value(obs: Any, aliases: tuple) -> Any:
    """Best-effort case-insensitive recursive (one level) value lookup."""
    d = _mapping(obs)
    norm_aliases = {_norm_key(a) for a in aliases}
    # direct
    for k, v in d.items():
        if _norm_key(k) in norm_aliases:
            return v
    # one level deeper
    for v in d.values():
        nd = _mapping(v)
        if not nd:
            continue
        for k, val in nd.items():
            if _norm_key(k) in norm_aliases:
                return val
        # boolean/string payload
    # scan all string/bool keys flattened recursively (shallow)
    for v in d.values():
        nd = _mapping(v)
        for k, val in nd.items():
            nk = _norm_key(k)
            if nk in norm_aliases:
                return val
    return None


def _section(obs: Any, aliases: tuple) -> Any:
    d = _mapping(obs)
    # direct section
    for a in aliases:
        for k, v in d.items():
            if _norm_key(k) == _norm_key(a):
                return v
    # merged top-level could itself be the section if it contains check keys
    return None


def _as_bool_state(value: Any, healthy_tokens: set, unhealthy_tokens: set) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if not s:
        return None
    if any(tok in s for tok in unhealthy_tokens):
        return False
    if any(tok in s for tok in healthy_tokens):
        return True
    # truthy-ish
    if s in {"1", "true", "yes", "y", "ok"}:
        return True
    if s in {"0", "false", "no", "n"}:
        return False
    return None


def _state_running_ok(section: Any) -> Optional[bool]:
    # check explicit "running"-ish fields
    true_tokens = {"running", "started", "active", "enabled", "healthy", "ready",
                   "ok", "available", "synchronized", "sync", "up", "true"}
    false_tokens = {"stopped", "disabled", "manual", "notrunning", "inactive",
                    "unhealthy", "down", "false", "failed", "notsynchronized"}
    d = _mapping(section)
    if not d:
        if isinstance(section, str):
            return _as_bool_state(section, true_tokens, false_tokens)
        if isinstance(section, bool):
            return section
        return None
    # find running/state/status
    candidate = _find_value(section, ("running", "state", "service_state", "status",
                                      "w32time_state", "service_status", "health"))
    if candidate is None:
        candidate = _find_value(section, ("healthy", "ok", "available"))
    if candidate is None:
        # section itself may carry boolean
        if "healthy" in d and isinstance(d.get("healthy"), bool):
            candidate = d.get("healthy")
    if candidate is None:
        return None
    return _as_bool_state(candidate, true_tokens, false_tokens)


def _start_type_ok(section: Any) -> Optional[bool]:
    d = _mapping(section)
    if not d:
        if isinstance(section, str):
            s = section.lower()
            if "manual" in s or "disabled" in s:
                return False
            if "auto" in s:
                return True
            return None
        return None
    val = _find_value(section, ("start_type", "start_mode", "starttype",
                                "start", "startup_type", "trigger_start"))
    if val is None:
        # maybe state string contains start type
        val = _find_value(section, ("state", "status"))
    if val is None:
        return None
    s = str(val).strip().lower()
    if any(t in s for t in ("manual", "disabled", "demand")):
        return False
    if any(t in s for t in ("automatic", "auto", "delayed")):
        return True
    return None


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt.astimezone(timezone.utc)


def _x99_check(obs: Any) -> tuple[bool, str, dict]:
    section = _section(obs, ("x99_w32time", "x99", "w32time", "windows_w32time",
                             "windows_time", "x99_windows_w32time"))
    if section is None:
        # maybe flat observation under a single key
        section = obs
    running_ok = _state_running_ok(section)
    start_ok = _start_type_ok(section)
    details = {
        "running_ok": running_ok,
        "automatic_start_ok": start_ok,
    }
    if running_ok is True and start_ok is True:
        return True, "OK", details
    # If section missing entirely
    if _mapping(section) == _mapping(obs) and _find_value(obs, ("running", "state", "start_type", "start_mode")) is None:
        return False, BLOCK_CODE_MISSING_OBSERVATION, details
    return False, BLOCK_CODES["x99_w32time"], details


def _pentium_check(obs: Any) -> tuple[bool, str, dict]:
    section = _section(obs, ("pentium_ntp", "pentium", "ntp", "pentium_ntp_status",
                             "ntp_status", "pentium_time"))
    if section is None:
        section = obs
    status = _find_value(section, ("status", "health", "state", "ntp_status", "result"))
    ok = _as_bool_state(status, {"healthy", "ok", "synchronized", "sync", "ready",
                                "up", "available", "true", "enabled"},
                       {"unhealthy", "error", "failed", "unsync", "unsynchronized",
                        "notsynchronized", "down", "stopped", "disabled", "false"})
    if ok is None:
        # boolean or available flags
        avail = _find_value(section, ("available", "ready", "reachable", "enabled", "healthy"))
        ok = _as_bool_state(avail, {"true", "yes", "1"}, {"false", "no", "0"}) if avail is not None else None
    details = {"ntp_status": status, "healthy": ok}
    if ok is True:
        return True, "OK", details
    # distinguish missing
    if _find_value(obs, ("status", "health", "state", "ntp_status")) is None and not _mapping(section).keys() & {"available","ready"}:
        # could still be a flat true boolean passed
        if isinstance(section, bool):
            if section:
                return True, "OK", details
            return False, BLOCK_CODES["pentium_ntp"], details
    if isinstance(obs, bool):
        return (True, "OK", details) if obs else (False, BLOCK_CODES["pentium_ntp"], details)
    return False, BLOCK_CODES["pentium_ntp"], details


def _timestamps_check(obs: Any, now: datetime) -> tuple[bool, str, dict]:
    # extract values from likely locations
    x99_raw = _find_value(obs, ("x99_observed", "x99_time", "x99_observed_at",
                                "host_x99", "x99_timestamp", "x99_observed_timestamp"))
    pentium_raw = _find_value(obs, ("pentium_observed", "pentium_time", "pentium_observed_at",
                                    "host_pentium", "pentium_timestamp", "pentium_observed_timestamp"))
    ref_raw = _find_value(obs, ("reference_instant", "reference", "independent_reference",
                                "reference_timestamp", "reference_time", "trusted_reference"))
    capture_raw = _find_value(obs, ("capture_time", "captured_at", "capture_at", "captured",
                                    "reference_capture_time", "capture_instant"))

    x99_dt = _parse_dt(x99_raw)
    pentium_dt = _parse_dt(pentium_raw)
    ref_dt = _parse_dt(ref_raw)
    capture_dt = _parse_dt(capture_raw)

    details = {
        "x99_observed": x99_dt.isoformat() if x99_dt else None,
        "pentium_observed": pentium_dt.isoformat() if pentium_dt else None,
        "reference_instant": ref_dt.isoformat() if ref_dt else None,
        "capture_time": capture_dt.isoformat() if capture_dt else None,
        "skew_seconds": None,
    }

    if x99_dt is None or pentium_dt is None or ref_dt is None:
        return False, BLOCK_CODE_INVALID_INPUT if (x99_raw is not None or pentium_raw is not None or ref_raw is not None) else BLOCK_CODE_MISSING_OBSERVATION, details
    # require capture time per task
    if capture_dt is None:
        return False, BLOCK_CODES["reference_timestamps"], details
    # capture age
    capture_age = (now - capture_dt).total_seconds()
    details["capture_age_seconds"] = capture_age
    if capture_age < 0 or capture_age > MAX_CAPTURE_AGE_SECONDS:
        return False, BLOCK_CODE_CAPTURE_STALE, details

    # independent reference must be timezone-aware (already) and not future relative to now
    if ref_dt > now:
        return False, BLOCK_CODE_INVALID_INPUT, details

    # shadow clock guard verify
    if _scg is not None:
        try:
            ok, reason, scg_details = _scg.verify_time_skew(
                x99_observed=x99_dt,
                pentium_observed=pentium_dt,
                reference_instant=ref_dt,
                tolerance_seconds=DRIFT_TOLERANCE_SECONDS,
                bounded_age_seconds=MAX_CAPTURE_AGE_SECONDS,
            )
            details["skew_seconds"] = scg_details.get("skew_seconds")
            if not ok:
                # historic drift
                if reason == getattr(_scg, "REASON_UTC_SKEW", "UTC_SKEW"):
                    return False, BLOCK_CODE_HISTORIC_DRIFT, details
                return False, BLOCK_CODES["reference_timestamps"], details
        except Exception as exc:
            details["error"] = str(exc)
            return False, BLOCK_CODES["reference_timestamps"], details
    else:
        # fallback: manual skew
        skew = abs((x99_dt - pentium_dt).total_seconds())
        details["skew_seconds"] = skew
        if skew > DRIFT_TOLERANCE_SECONDS:
            return False, BLOCK_CODE_HISTORIC_DRIFT, details

    return True, "OK", details


def _simple_section_check(obs: Any, aliases: tuple, key_aliases_ok: tuple,
                          block_code: str) -> tuple[bool, str, dict]:
    section = _section(obs, aliases)
    if section is None:
        section = obs
    # if entire obs only, try find section-specific booleans
    d = _mapping(section)
    details = {"observed": d if d else section if not isinstance(section, (str, bool)) else section}

    # boolean section
    if isinstance(section, bool):
        return (True, "OK", details) if section else (False, block_code, details)

    # string section
    if isinstance(section, str):
        s = section.strip().lower()
        if s in {"ok", "healthy", "ready", "available", "reachable", "connected",
                 "true", "yes", "enabled", "pass", "success", "acknowledged",
                 "acked", "received"}:
            return True, "OK", details
        if s in {"not_ready", "blocked", "not_ready", "unavailable", "unreachable",
                 "false", "no", "disabled", "fail", "failed"}:
            return False, block_code, details

    # dict section: look for status or availability flags
    found_status = _find_value(section, ("status", "health", "state", "result"))
    ok = _as_bool_state(found_status,
                        {"healthy", "ok", "ready", "available", "reachable", "connected",
                         "true", "enabled", "success", "pass", "acknowledged", "acked",
                         "received", "up"},
                        {"unhealthy", "error", "failed", "unavailable", "unreachable",
                         "disconnected", "false", "disabled", "down", "blocked",
                         "notready", "missing", "absent"})
    if ok is None:
        # any explicit true aliases
        for ka in key_aliases_ok:
            val = _find_value(section, (ka,))
            if val is not None:
                ok = _as_bool_state(val, {"true", "yes", "1", "ok", "ready",
                                         "available", "healthy", "received", "acked",
                                         "acknowledged", "enabled"},
                                    {"false", "no", "0", "blocked", "missing",
                                     "unavailable", "unhealthy"})
                if ok is not None:
                    break
    if ok is None:
        # maybe direct bool in section
        if isinstance(section, Mapping) and not section:
            return False, BLOCK_CODE_MISSING_OBSERVATION, details
        # if section has no recognizable truthiness but is non-empty, fail closed
        if not d:
            return False, BLOCK_CODE_MISSING_OBSERVATION, details
        # try top-level booleans
        vals = [v for v in d.values() if isinstance(v, bool)]
        if vals:
            return (all(vals), "OK" if all(vals) else block_code, details) if any(vals) else (False, block_code, details)
        return False, BLOCK_CODE_INVALID_INPUT, details
    if ok:
        return True, "OK", details
    return False, block_code, details


def _hmac_check(obs: Any) -> tuple[bool, str, dict]:
    section = _section(obs, ("production_hmac_key_provisioning", "hmac_key_provisioning",
                             "hmac_key", "production_hmac_key", "hmac", "key_provisioning"))
    if section is None:
        section = obs
    d = _mapping(section)
    details = {}
    # flatten useful metadata (never include raw key bytes)
    for k in ("provisioned", "environment", "key_length", "length", "bits",
              "uses_test_key", "test_key", "placeholder", "source", "key_id"):
        v = _find_value(section, (k,))
        if v is not None:
            details[k] = v if not isinstance(v, (bytes, bytearray)) else "<redacted>"

    # redact raw key
    raw_key = _find_value(section, ("key", "private_key", "secret", "hmac"))
    if isinstance(raw_key, (bytes, bytearray)):
        details["key_present"] = len(raw_key) > 0
        details["key_length"] = len(raw_key)
        raw_ok = (len(raw_key) == 32)
    else:
        raw_ok = None

    provisioned = _find_value(section, ("provisioned", "provisioned_successfully"))
    provisioned_bool = provisioned if isinstance(provisioned, bool) else (
        str(provisioned).lower() in {"true", "yes", "1", "ready"} if provisioned is not None else None)

    environment = _find_value(section, ("environment", "env", "target"))
    env_str = str(environment).lower() if environment is not None else None

    key_length = _find_value(section, ("key_length", "length", "size", "bits"))
    if isinstance(key_length, bool):
        key_length = None
    try:
        key_len_ok = (key_length is None) or (int(key_length) == 32 or int(key_length) == 256)
    except (TypeError, ValueError):
        key_len_ok = False

    uses_test = _find_value(section, ("uses_test_key", "test_key", "is_test_key", "sample_key"))
    uses_test_bool = False
    if isinstance(uses_test, bool):
        uses_test_bool = uses_test
    elif uses_test is not None:
        uses_test_bool = str(uses_test).lower() in {"true", "yes", "1", "test"}

    placeholder = _find_value(section, ("placeholder", "placeholder_key", "dummy"))
    placeholder_bool = False
    if isinstance(placeholder, bool):
        placeholder_bool = placeholder
    elif placeholder is not None:
        placeholder_bool = str(placeholder).lower() in {"true", "yes", "1"}

    # decision
    checks_ok = []
    if provisioned_bool is not None:
        checks_ok.append(provisioned_bool is True)
    if env_str is not None:
        checks_ok.append(env_str in {"production", "prod"})
    if key_length is not None:
        checks_ok.append(key_len_ok)
    if raw_ok is not None:
        checks_ok.append(raw_ok)
    # test/placeholder always disqualify if true
    if uses_test_bool or placeholder_bool:
        checks_ok.append(False)

    if not d and not isinstance(section, bool):
        return False, BLOCK_CODE_MISSING_OBSERVATION, details
    # if no positive signals at all, fail closed
    if provisioned_bool is None and key_length is None and raw_ok is None and env_str is None and not uses_test_bool:
        # allow a boolean section
        if isinstance(section, bool):
            return (True, "OK", details) if section else (False, BLOCK_CODES["production_hmac_key_provisioning"], details)
        return False, BLOCK_CODE_INVALID_INPUT, details

    if checks_ok and all(checks_ok):
        return True, "OK", details
    # If only provisioned_bool provided and true, and no disqualifiers
    if provisioned_bool is True and not uses_test_bool and not placeholder_bool and key_len_ok:
        # environment may be missing; accept if provisioned explicit
        if env_str is None or env_str in {"production", "prod"}:
            return True, "OK", details
    return False, BLOCK_CODES["production_hmac_key_provisioning"], details


def _lease_check(obs: Any) -> tuple[bool, str, dict]:
    section = _section(obs, ("lease_recovery_rollback", "lease_recovery", "lease", "recovery",
                             "rollback", "recovery_rollback", "lease_rollback"))
    if section is None:
        section = obs
    details = {}
    # recovery + rollback may be separate
    rec_val = _find_value(section, ("recovery_ready", "recovery", "recovery_available",
                                    "lease_recovery_ready", "restore_ready"))
    rb_val = _find_value(section, ("rollback_ready", "rollback", "rollback_available",
                                   "can_rollback", "rollback_capable"))
    rec_ok = _as_bool_state(rec_val, {"ready", "available", "true", "yes", "1", "ok", "enabled"},
                            {"false", "no", "0", "blocked", "missing", "unavailable"})
    rb_ok = _as_bool_state(rb_val, {"ready", "available", "true", "yes", "1", "ok", "enabled"},
                           {"false", "no", "0", "blocked", "missing", "unavailable"})

    if rec_ok is None and rb_ok is None:
        # generic status/ready
        general = _find_value(section, ("status", "ready", "available"))
        if isinstance(section, bool):
            if section:
                return True, "OK", details
            return False, BLOCK_CODES["lease_recovery_rollback"], details
        ok = _as_bool_state(general, {"ready", "available", "true", "yes", "1", "ok", "enabled", "pass"},
                            {"not_ready", "blocked", "false", "no", "0", "unavailable", "missing"})
        if ok is None:
            if _mapping(section):
                # if all booleans true
                bools = [v for v in _mapping(section).values() if isinstance(v, bool)]
                if bools:
                    return (all(bools), "OK" if all(bools) else BLOCK_CODES["lease_recovery_rollback"], details)
            return False, BLOCK_CODE_INVALID_INPUT if _mapping(section) else BLOCK_CODE_MISSING_OBSERVATION, details
        return (True, "OK", details) if ok else (False, BLOCK_CODES["lease_recovery_rollback"], details)

    # If both provided, both must be ok
    rec_final = True if rec_ok is None else rec_ok
    rb_final = True if rb_ok is None else rb_ok
    details["recovery_ready"] = rec_ok
    details["rollback_ready"] = rb_ok
    if (rec_ok is None or rec_ok) and (rb_ok is None or rb_ok):
        # at least one positive? require if provided
        if (rec_val is not None or rb_val is not None):
            return True, "OK", details
    if rec_ok is False or rb_ok is False:
        return False, BLOCK_CODES["lease_recovery_rollback"], details
    # no usable info
    if rec_val is None and rb_val is None:
        return False, BLOCK_CODE_MISSING_OBSERVATION, details
    return False, BLOCK_CODES["lease_recovery_rollback"], details


def _notification_ack_check(obs: Any) -> tuple[bool, str, dict]:
    section = _section(obs, ("notification_recipient_ack", "recipient_ack",
                             "notification_ack", "notification", "recipient", "ack"))
    if section is None:
        section = obs
    details = {}
    ack_val = _find_value(section, ("acked", "acknowledged", "received", "recipient_ack",
                                    "ack", "acceptance", "confirmed"))
    ack_id = _find_value(section, ("ack_id", "receipt", "message_id", "notification_id"))
    status = _find_value(section, ("status", "state", "result"))
    # blocked if explicitly unacked
    if isinstance(section, bool):
        return (True, "OK", details) if section else (False, BLOCK_CODES["notification_recipient_ack"], details)
    if ack_val is not None:
        ok = _as_bool_state(ack_val, {"true", "yes", "1", "acked", "acknowledged",
                                     "received", "confirmed", "accepted", "ok"},
                            {"false", "no", "0", "pending", "unacked", "missing", "rejected"})
        if ok is None:
            s = str(ack_val).strip().lower()
            ok = s in {"acked", "acknowledged", "received", "confirmed", "accepted", "ok", "done"}
        if ok:
            if ack_id is not None:
                details["ack_id"] = ack_id
            return True, "OK", details
        return False, BLOCK_CODES["notification_recipient_ack"], details
    if status is not None:
        s = str(status).strip().lower()
        if s in {"acked", "acknowledged", "received", "confirmed", "delivered", "ok", "accepted"}:
            if ack_id is not None:
                details["ack_id"] = ack_id
            return True, "OK", details
        if s in {"pending", "unacked", "missing", "rejected", "failed", "notreceived"}:
            return False, BLOCK_CODES["notification_recipient_ack"], details
    # if ack_id present alone, treat as acked
    if ack_id is not None:
        details["ack_id"] = ack_id
        return True, "OK", details
    if isinstance(section, Mapping) and not section:
        return False, BLOCK_CODE_MISSING_OBSERVATION, details
    if not _mapping(section):
        return False, BLOCK_CODE_MISSING_OBSERVATION, details
    bools = [v for v in _mapping(section).values() if isinstance(v, bool)]
    if bools:
        if all(bools):
            return True, "OK", details
        return False, BLOCK_CODES["notification_recipient_ack"], details
    return False, BLOCK_CODE_INVALID_INPUT, details


def _ssh_check(obs: Any) -> tuple[bool, str, dict]:
    section = _section(obs, ("ssh_transport", "ssh", "transport", "ssh_reachability"))
    if section is None:
        section = obs
    details = {}
    reach = _find_value(section, ("reachable", "reachability", "connected", "connection",
                                 "ssh_reachable", "transport_reachable", "ssh_ok"))
    status = _find_value(section, ("status", "state", "result"))
    host = _find_value(section, ("host", "endpoint", "target"))
    if host is not None:
        details["host"] = host
    if isinstance(section, bool):
        return (True, "OK", details) if section else (False, BLOCK_CODES["ssh_transport"], details)
    if reach is not None:
        ok = _as_bool_state(reach, {"true", "yes", "1", "ok", "ready", "reachable",
                                    "connected", "up", "success"},
                            {"false", "no", "0", "unreachable", "disconnected", "down",
                             "blocked", "failed", "timeout", "timedout"})
        if ok:
            return True, "OK", details
        return False, BLOCK_CODES["ssh_transport"], details
    if status is not None:
        s = str(status).strip().lower()
        if s in {"reachable", "connected", "ok", "up", "success", "pass", "true"}:
            return True, "OK", details
        if s in {"unreachable", "disconnected", "down", "failed", "timeout",
                 "blocked", "false", "error"}:
            return False, BLOCK_CODES["ssh_transport"], details
    if isinstance(section, Mapping) and not section:
        return False, BLOCK_CODE_MISSING_OBSERVATION, details
    if not _mapping(section):
        return False, BLOCK_CODE_MISSING_OBSERVATION, details
    bools = [v for v in _mapping(section).values() if isinstance(v, bool)]
    if bools:
        if all(bools):
            return True, "OK", details
        return False, BLOCK_CODES["ssh_transport"], details
    return False, BLOCK_CODE_INVALID_INPUT, details


def _sandbox_check(obs: Any) -> tuple[bool, str, dict]:
    section = _section(obs, ("os_sandbox", "sandbox", "sandbox_availability", "os_sandbox_availability"))
    if section is None:
        section = obs
    details = {}
    avail = _find_value(section, ("available", "availability", "ready", "enabled", "supported",
                                 "sandbox_available", "exists"))
    status = _find_value(section, ("status", "state", "result"))
    if isinstance(section, bool):
        return (True, "OK", details) if section else (False, BLOCK_CODES["os_sandbox"], details)
    if avail is not None:
        ok = _as_bool_state(avail, {"true", "yes", "1", "ok", "ready", "available",
                                    "enabled", "supported", "present", "up"},
                            {"false", "no", "0", "unavailable", "disabled", "missing", "absent",
                             "unsupported", "down"})
        if ok:
            return True, "OK", details
        return False, BLOCK_CODES["os_sandbox"], details
    if status is not None:
        s = str(status).strip().lower()
        if s in {"available", "ready", "ok", "up", "enabled", "supported", "present", "pass"}:
            return True, "OK", details
        if s in {"unavailable", "notavailable", "missing", "absent", "disabled",
                 "unsupported", "down", "failed", "blocked"}:
            return False, BLOCK_CODES["os_sandbox"], details
    if isinstance(section, Mapping) and not section:
        return False, BLOCK_CODE_MISSING_OBSERVATION, details
    if not _mapping(section):
        return False, BLOCK_CODE_MISSING_OBSERVATION, details
    bools = [v for v in _mapping(section).values() if isinstance(v, bool)]
    if bools:
        if all(bools):
            return True, "OK", details
        return False, BLOCK_CODES["os_sandbox"], details
    return False, BLOCK_CODE_INVALID_INPUT, details


def _cognitive_check(obs: Any) -> tuple[bool, str, dict]:
    section = _section(obs, ("cognitive_service_bridge", "cognitive_bridge", "cognitive_service",
                             "service_bridge", "bridge", "cognitive"))
    if section is None:
        section = obs
    details = {}
    avail = _find_value(section, ("available", "availability", "ready", "enabled", "healthy",
                                 "connected", "reachable", "bridge_available"))
    status = _find_value(section, ("status", "state", "health", "result"))
    endpoint = _find_value(section, ("endpoint", "url", "bridge", "service"))
    if endpoint is not None:
        details["endpoint"] = endpoint
    if isinstance(section, bool):
        return (True, "OK", details) if section else (False, BLOCK_CODES["cognitive_service_bridge"], details)
    if avail is not None:
        ok = _as_bool_state(avail, {"true", "yes", "1", "ok", "ready", "available",
                                    "enabled", "healthy", "connected", "reachable", "up"},
                            {"false", "no", "0", "unavailable", "disabled", "missing",
                             "absent", "unhealthy", "disconnected", "down", "blocked"})
        if ok:
            return True, "OK", details
        return False, BLOCK_CODES["cognitive_service_bridge"], details
    if status is not None:
        s = str(status).strip().lower()
        if s in {"available", "ready", "ok", "healthy", "connected", "reachable", "up", "enabled", "pass"}:
            return True, "OK", details
        if s in {"unavailable", "notavailable", "missing", "absent", "disabled",
                 "unhealthy", "disconnected", "down", "failed", "blocked", "error"}:
            return False, BLOCK_CODES["cognitive_service_bridge"], details
    if isinstance(section, Mapping) and not section:
        return False, BLOCK_CODE_MISSING_OBSERVATION, details
    if not _mapping(section):
        return False, BLOCK_CODE_MISSING_OBSERVATION, details
    bools = [v for v in _mapping(section).values() if isinstance(v, bool)]
    if bools:
        if all(bools):
            return True, "OK", details
        return False, BLOCK_CODES["cognitive_service_bridge"], details
    return False, BLOCK_CODE_INVALID_INPUT, details


_CHECK_FUNCS = {
    "x99_w32time": lambda obs, now: _x99_check(obs),
    "pentium_ntp": lambda obs, now: _pentium_check(obs),
    "reference_timestamps": lambda obs, now: _timestamps_check(obs, now),
    "ssh_transport": lambda obs, now: _ssh_check(obs),
    "os_sandbox": lambda obs, now: _sandbox_check(obs),
    "notification_recipient_ack": lambda obs, now: _notification_ack_check(obs),
    "lease_recovery_rollback": lambda obs, now: _lease_check(obs),
    "production_hmac_key_provisioning": lambda obs, now: _hmac_check(obs),
    "cognitive_service_bridge": lambda obs, now: _cognitive_check(obs),
}


def _collect_observations(*args, **kwargs) -> dict:
    data: dict = {}
    reserved = {"now", "policy", "provider", "observations", "observation", "obs",
                "data", "inputs", "state", "context", "checks"}
    # positional
    for a in args:
        if a is None:
            continue
        if callable(a) and not isinstance(a, (Mapping, str, bytes, bytearray)):
            try:
                a = a()
            except Exception:
                continue
        if isinstance(a, datetime):
            data.setdefault("now", a)
            continue
        m = _mapping(a)
        if m:
            # merge nested checks/observations
            for k in ("observations", "observation", "obs", "data", "inputs", "state", "context", "checks"):
                if k in m and isinstance(m[k], (Mapping,)):
                    sub = _collect_observations(m[k])
                    # remove wrapper key to avoid misclassification
                    sub.pop("now", None)
                    data.update(sub)
            m2 = {k: v for k, v in m.items() if k not in ("observations", "observation", "obs", "data", "inputs", "state", "context", "checks")}
            data.update(m2)
        elif isinstance(a, bool):
            # ambiguous; ignore
            pass
    # kwargs
    for k, v in kwargs.items():
        if k in reserved:
            if k in ("observations", "observation", "obs", "data", "inputs", "state", "context", "checks") and v is not None:
                m = _mapping(v)
                if callable(v) and not isinstance(v, (Mapping, str)):
                    try:
                        v = v()
                        m = _mapping(v)
                    except Exception:
                        m = {}
                if isinstance(v, datetime):
                    data.setdefault("now", v)
                elif m:
                    for kk in ("observations", "observation", "obs", "data", "inputs", "state", "context", "checks"):
                        if kk in m and isinstance(m[kk], Mapping):
                            data.update(_collect_observations(m[kk]))
                    data.update({kk: vv for kk, vv in m.items() if kk not in ("observations", "observation", "obs", "data", "inputs", "state", "context", "checks")})
            elif k == "now" and isinstance(v, datetime):
                data.setdefault("now", v)
            continue
        if v is None:
            continue
        if callable(v) and not isinstance(v, (Mapping, str, bytes, bytearray)):
            try:
                v = v()
            except Exception:
                continue
        if isinstance(v, datetime):
            data.setdefault(k, v)
            continue
        if isinstance(v, Mapping):
            for kk in ("observations", "observation", "obs", "data", "inputs", "state", "context", "checks"):
                if kk in v and isinstance(v[kk], Mapping):
                    data.update(_collect_observations(v[kk]))
            data.update({kkk: val for kkk, val in v.items() if kkk not in ("observations", "observation", "obs", "data", "inputs", "state", "context", "checks")})
            # also keep whole under canonical key if provided
            data.setdefault(k, v)
        else:
            data[k] = v
    return data


def operational_preflight(*args, **kwargs) -> dict:
    data = _collect_observations(*args, **kwargs)
    now = data.pop("now", None)
    if now is None:
        now = kwargs.get("now")
    if now is None:
        for k in ("now", "current_time", "reference_now"):
            if k in kwargs and isinstance(kwargs[k], datetime):
                now = kwargs[k]
                break
    if not isinstance(now, datetime):
        now = datetime.now(timezone.utc)
    else:
        now = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)

    obs = data

    checks = {}
    blocks = []
    all_ok = True
    for name in CHECK_NAMES:
        try:
            ok, code, details = _CHECK_FUNCS[name](obs, now)
        except Exception as exc:
            ok, code, details = False, BLOCK_CODE_INVALID_INPUT, {"error": str(exc)}
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
            # use specific code for drift if timestamps
            if name == "reference_timestamps" and code == BLOCK_CODE_HISTORIC_DRIFT:
                block_code = code
            else:
                block_code = code
            blocks.append(block_code)
        checks[name] = {
            "status": status,
            "code": code,
            "details": details,
        }

    # Missing observation overall: if no observations provided, ensure blocked
    if not obs:
        all_ok = False
        if BLOCK_CODE_MISSING_OBSERVATION not in blocks:
            blocks.insert(0, BLOCK_CODE_MISSING_OBSERVATION)

    ready = bool(all_ok and len(blocks) == 0)
    status = STATUS_READY if ready else STATUS_BLOCKED_NOT_READY
    # de-duplicate block codes preserving order
    deduped = []
    for b in blocks:
        if b not in deduped:
            deduped.append(b)

    report = {
        "schema": SCHEMA,
        "status": status,
        "ready": ready,
        "blocks": deduped,
        "block_codes": list(deduped),
        "blocked_reasons": list(deduped),
        "checks": checks,
        "evaluated_at": now.isoformat(),
        "read_only": True,
        "execution_started": False,
        "services_started": False,
        "services_stopped": False,
        "network_access": False,
        "secrets_returned": False,
    }
    return report


# Aliases for compatibility with possible expected entrypoint names.
run_preflight = operational_preflight
run_operational_preflight = operational_preflight
preflight = operational_preflight
check_preflight = operational_preflight
check_operational_preflight = operational_preflight
evaluate_preflight = operational_preflight
evaluate_operational_preflight = operational_preflight
preflight_check = operational_preflight


def is_ready(result: Any) -> bool:
    r = _mapping(result)
    return bool(r.get("ready") is True and r.get("status") == STATUS_READY)
