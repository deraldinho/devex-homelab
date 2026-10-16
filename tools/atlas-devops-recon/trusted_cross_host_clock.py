"""Trusted cross-host clock verification (CP15 remediation)."""
from __future__ import annotations
import math
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

SCHEMA = "atlas.trusted.cross.host.clock.v1"

REASON_OK = "OK"
REASON_MISSING_SOURCE_ID = "MISSING_SOURCE_ID"
REASON_MISSING_CAPTURE_TIME = "MISSING_CAPTURE_TIME"
REASON_NAIVE_DATETIME = "NAIVE_DATETIME"
REASON_MISSING_REFERENCE = "MISSING_REFERENCE"
REASON_INVALID_REFERENCE = "INVALID_REFERENCE"
REASON_FUTURE_DATA = "FUTURE_DATA"
REASON_STALE_DATA = "STALE_DATA"
REASON_STALE_REFERENCE = "STALE_REFERENCE"
REASON_TTL_EXPIRED = "TTL_EXPIRED"
REASON_EXPIRED_TTL = "EXPIRED_TTL"
REASON_UNVERIFIED_PROVENANCE = "UNVERIFIED_PROVENANCE"
REASON_CLOCK_SKEW = "UTC_SKEW"
REASON_UTC_SKEW = "UTC_SKEW"
REASON_INVALID_BOUNDS = "INVALID_BOUNDS"
REASON_INVALID_MAX_AGE = "INVALID_MAX_AGE"
REASON_INVALID_TTL = "INVALID_TTL"
REASON_MISSING_HOST = "MISSING_HOST"
REASON_UNTRUSTED_SOURCE = "UNTRUSTED_SOURCE"
REASON_INVALID_TOLERANCE = REASON_INVALID_BOUNDS
MAX_TOLERANCE_SECONDS = 300
MAX_SAMPLE_LIFETIME_SECONDS = 86400
# aliases
REASON_UNVERIFIED = REASON_UNVERIFIED_PROVENANCE
REASON_UNVERIFIED_PROVENANCE = REASON_UNVERIFIED_PROVENANCE
REASON_CLOCK_DRIFT = "CLOCK_DRIFT"
REASON_DRIFT = REASON_CLOCK_SKEW
REASON_HOST_DRIFT = REASON_CLOCK_SKEW
REASON_SKEW = REASON_CLOCK_SKEW
REASON_REFERENCE_STALE = REASON_STALE_REFERENCE
REASON_CAPTURE_STALE = "CAPTURE_STALE"
REASON_SAMPLE_EXPIRED = REASON_TTL_EXPIRED
REASON_FUTURE_SAMPLE = REASON_FUTURE_DATA
REASON_FUTURE_CAPTURE = REASON_FUTURE_DATA
REASON_INVALID_RTT = REASON_INVALID_BOUNDS
REASON_INVALID_UNCERTAINTY = REASON_INVALID_BOUNDS
REASON_MISSING_SAMPLE = REASON_MISSING_REFERENCE
REASON_NO_REFERENCE = REASON_MISSING_REFERENCE
REASON_REFERENCE_MISSING = REASON_MISSING_REFERENCE
REASON_MISSING_SOURCE = REASON_MISSING_SOURCE_ID
REASON_UNTRUSTED_REFERENCE = REASON_UNVERIFIED_PROVENANCE
REASON_UNTRUSTED = REASON_UNVERIFIED_PROVENANCE
REASON_PROVENANCE_UNVERIFIED = REASON_UNVERIFIED_PROVENANCE
REASON_INVALID_PROVENANCE = REASON_UNVERIFIED_PROVENANCE
REASON_CAPTURE_FUTURE = REASON_FUTURE_DATA
REASON_CAPTURE_TOO_OLD = REASON_STALE_REFERENCE

OK = REASON_OK

def _mapping(value):
    if value is None: return {}
    if isinstance(value, Mapping): return {str(k): v for k, v in value.items()}
    if hasattr(value, "__dict__"):
        try: return {str(k): v for k, v in vars(value).items()}
        except Exception: return {}
    return {}

def _norm_key(key):
    return "".join(ch for ch in str(key).lower() if ch.isalnum())

def _find_kv(obs, aliases):
    d = _mapping(obs)
    norm_aliases = {_norm_key(a) for a in aliases}
    for k, v in d.items():
        if _norm_key(k) in norm_aliases: return k, v
    for v in d.values():
        nd = _mapping(v)
        if not nd: continue
        for k, val in nd.items():
            if _norm_key(k) in norm_aliases: return k, val
    return None, None

def _find_value(obs, aliases):
    return _find_kv(obs, aliases)[1]

def _parse_dt(value):
    if value is None: return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try: dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError: return None
    else:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None: return None
    return dt.astimezone(timezone.utc)

def _num(value):
    if value is None or isinstance(value, bool): return None
    if isinstance(value, (int, float)): return float(value)
    if isinstance(value, str):
        try: return float(value.strip())
        except ValueError: return None
    return None

def _to_utc_seconds(value):
    return value.astimezone(timezone.utc).timestamp()

def _num_field(data, aliases):
    k, v = _find_kv(data, aliases)
    if v is None: return None
    n = _num(v)
    if n is None: return None
    if k is not None and "ms" in str(k).lower().replace("_", ""): return n / 1000.0
    return n

def _flatten(value):
    if value is None: return []
    if isinstance(value, (list, tuple, set)):
        out = []
        for item in value: out.extend(_flatten(item))
        return out
    return [value]

SOURCE_ALIASES = ("source_id", "source", "source_name", "reference_source", "attestor", "attestor_id", "ntp_source", "provider", "origin")
CAPTURE_ALIASES = ("captured_at", "capture_time", "capture_at", "captured", "reference_capture_time", "capture_instant", "utc_capture_time", "sample_captured_at")
REFERENCE_ALIASES = ("reference_instant", "reference", "reference_time", "reference_utc", "ntp_instant", "ntp_time", "trusted_instant", "trusted_time", "reference_timestamp", "attested_time", "clock_reference", "independent_reference", "ntp_reference", "pentium_ntp_instant")
MAX_AGE_ALIASES = ("max_age_seconds", "max_age", "reference_max_age", "capture_max_age", "max_age_sec", "max_capture_age_seconds")
RTT_ALIASES = ("rtt_bound_seconds", "rtt_bound", "rtt", "max_rtt", "rtt_seconds", "round_trip_time", "round_trip_bound", "rtt_ms")
UNCERTAINTY_ALIASES = ("uncertainty_seconds", "uncertainty", "uncertainty_bound", "error_bound", "max_uncertainty", "uncertainty_ms")
TTL_ALIASES = ("ttl_seconds", "ttl", "time_to_live", "max_ttl", "validity_seconds", "validity", "ttl_ms")
VERIFIED_ALIASES = ("verified", "is_verified", "attestation_verified", "verified_by_caller", "signature_verified", "provenance_verified")
PROVENANCE_ALIASES = ("provenance", "signature", "signed_provenance", "attestation", "attestation_proof", "provenance_signature")

def _looks_like_sample(value):
    d = _mapping(value)
    if not d: return False
    source_aliases = ("source_id", "source", "attestor", "ntp_source", "reference_source")
    capture_aliases = ("captured_at", "capture_time", "capture_at", "captured")
    ref_aliases = ("reference_instant", "reference", "reference_time", "ntp_instant", "trusted_instant", "reference_timestamp")
    if _find_value(d, source_aliases) is not None: return True
    if _find_value(d, capture_aliases) is not None and _find_value(d, ref_aliases) is not None: return True
    return False

class ReferenceSample:
    def __init__(self, *args, **kwargs):
        data = dict(kwargs)
        positional_datetimes = []
        for i, arg in enumerate(args):
            if isinstance(arg, ReferenceSample):
                data.update(_mapping(arg)); continue
            if isinstance(arg, (list, tuple, set)): continue
            m = _mapping(arg)
            if m:
                for k, v in m.items(): data.setdefault(k, v)
                continue
            if isinstance(arg, datetime):
                positional_datetimes.append(arg); continue
            if isinstance(arg, bool):
                data.setdefault("verified", arg); continue
            if isinstance(arg, Mapping):
                for k, v in arg.items(): data.setdefault(k, v); continue
            if i == 0 and "source_id" not in data:
                data["source_id"] = arg
            elif isinstance(arg, str) and "source_id" not in data:
                data["source_id"] = arg
        if positional_datetimes:
            if _find_value(data, CAPTURE_ALIASES) is None:
                data["captured_at"] = positional_datetimes[0]
            if len(positional_datetimes) > 1 and _find_value(data, REFERENCE_ALIASES) is None:
                data["reference_instant"] = positional_datetimes[1]
        prov_raw = _find_value(data, PROVENANCE_ALIASES)
        if isinstance(prov_raw, Mapping):
            provenance = {str(k): v for k, v in prov_raw.items()}
        elif prov_raw is None:
            provenance = {}
        else:
            provenance = {"value": prov_raw}
        verified = False
        vr_key, vr_val = _find_kv(data, VERIFIED_ALIASES)
        if vr_key is not None:
            if isinstance(vr_val, bool): verified = vr_val
            elif isinstance(vr_val, str): verified = vr_val.strip().lower() in {"true", "yes", "1", "verified"}
            elif isinstance(vr_val, (int, float)): verified = bool(vr_val)
        elif "verified" in provenance:
            pv = provenance.get("verified")
            if isinstance(pv, bool): verified = pv
            elif isinstance(pv, str): verified = pv.strip().lower() in {"true", "yes", "1", "verified"}
        self.source_id = _find_value(data, SOURCE_ALIASES)
        self.captured_at = _parse_dt(_find_value(data, CAPTURE_ALIASES))
        self.reference_instant = _parse_dt(_find_value(data, REFERENCE_ALIASES))
        self.max_age_seconds = _num_field(data, MAX_AGE_ALIASES)
        self.rtt_bound_seconds = _num_field(data, RTT_ALIASES)
        self.uncertainty_seconds = _num_field(data, UNCERTAINTY_ALIASES)
        self.ttl_seconds = _num_field(data, TTL_ALIASES)
        # Explicitly contradictory attestations must never be accepted.
        if "verified" in provenance and provenance["verified"] is not True:
            verified = False
        self.verified = bool(verified)
        self.provenance = provenance
    @classmethod
    def from_raw(cls, value):
        if isinstance(value, cls): return value
        return cls(value)
    def to_dict(self):
        return {
            "source_id": self.source_id,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "reference_instant": self.reference_instant.isoformat() if self.reference_instant else None,
            "max_age_seconds": self.max_age_seconds,
            "rtt_bound_seconds": self.rtt_bound_seconds,
            "uncertainty_seconds": self.uncertainty_seconds,
            "ttl_seconds": self.ttl_seconds,
            "verified": self.verified,
            "provenance": self.provenance,
        }

# aliases
AttestedReferenceSample = ReferenceSample
CrossHostReferenceSample = ReferenceSample
TrustedReferenceSample = ReferenceSample
AttestedSample = ReferenceSample
CrossHostSample = ReferenceSample
NTPReferenceSample = ReferenceSample

def _validate_sample(sample, now):
    details = sample.to_dict()
    if not sample.source_id:
        return False, REASON_MISSING_SOURCE_ID, details
    src = str(sample.source_id).strip().lower()
    if src in {"unknown", "untrusted", "invalid", "none", "null"}:
        return False, REASON_UNTRUSTED_SOURCE, details
    if sample.captured_at is None:
        return False, REASON_MISSING_CAPTURE_TIME, details
    if sample.reference_instant is None:
        return False, REASON_INVALID_REFERENCE, details
    if sample.max_age_seconds is None or not math.isfinite(sample.max_age_seconds) or not 0 < sample.max_age_seconds <= MAX_SAMPLE_LIFETIME_SECONDS:
        return False, REASON_INVALID_MAX_AGE, details
    if sample.rtt_bound_seconds is None or not math.isfinite(sample.rtt_bound_seconds) or not 0 < sample.rtt_bound_seconds <= MAX_TOLERANCE_SECONDS:
        return False, REASON_INVALID_BOUNDS, details
    if sample.uncertainty_seconds is None or not math.isfinite(sample.uncertainty_seconds) or not 0 < sample.uncertainty_seconds <= MAX_TOLERANCE_SECONDS:
        return False, REASON_INVALID_BOUNDS, details
    if sample.ttl_seconds is None or not math.isfinite(sample.ttl_seconds) or not 0 < sample.ttl_seconds <= MAX_SAMPLE_LIFETIME_SECONDS:
        return False, REASON_INVALID_TTL, details
    age = (now - sample.captured_at).total_seconds()
    details["age_seconds"] = age
    if age < 0:
        return False, REASON_FUTURE_DATA, details
    if age > sample.max_age_seconds:
        return False, REASON_STALE_REFERENCE, details
    if age > sample.ttl_seconds:
        return False, REASON_TTL_EXPIRED, details
    ref_age = (now - sample.reference_instant).total_seconds()
    details["reference_age_seconds"] = ref_age
    if ref_age < 0:
        return False, REASON_FUTURE_DATA, details
    if ref_age > sample.max_age_seconds:
        return False, REASON_STALE_REFERENCE, details
    if ref_age > sample.ttl_seconds:
        return False, REASON_TTL_EXPIRED, details
    if not sample.verified:
        details["verified"] = False
        details["provenance_verified"] = sample.provenance.get("verified")
        return False, REASON_UNVERIFIED_PROVENANCE, details
    return True, REASON_OK, details

def _effective_bound(sample, container):
    values = []
    if sample.rtt_bound_seconds is not None and sample.rtt_bound_seconds > 0:
        values.append(sample.rtt_bound_seconds)
    if sample.uncertainty_seconds is not None and sample.uncertainty_seconds > 0:
        values.append(sample.uncertainty_seconds)
    tol = _find_value(container, ("tolerance_seconds", "max_skew_seconds", "skew_tolerance_seconds", "clock_tolerance_seconds", "drift_tolerance_seconds"))
    tn = _num(tol)
    if tol is not None:
        if tn is None or tn <= 0 or tn != tn or tn == float("inf") or tn == float("-inf"):
            return None
        if tn > MAX_TOLERANCE_SECONDS:
            return None
        if tn > 0:
            values.append(tn)
    elif tn is not None and tn > 0:
        values.append(tn)
    if not values: return 0.0
    return max(values)

def verify_cross_host_clock(*args, **kwargs):
    container = {}
    positional_samples = []
    for arg in args:
        if isinstance(arg, ReferenceSample):
            positional_samples.append(arg); continue
        if isinstance(arg, (list, tuple, set)):
            for item in arg:
                if _looks_like_sample(item): positional_samples.append(item)
            continue
        m = _mapping(arg)
        if m:
            if _looks_like_sample(m): positional_samples.append(arg)
            else:
                for k, v in m.items(): container.setdefault(k, v)
            continue
        if isinstance(arg, datetime):
            container.setdefault("observed_instant", arg); continue
        if isinstance(arg, str):
            container.setdefault("host_id", arg); continue
        if isinstance(arg, bool):
            container.setdefault("verified", arg); continue
    for k, v in kwargs.items(): container[k] = v

    raw_samples = list(positional_samples)
    sv = _find_value(container, ("reference_samples", "references", "samples", "attested_references", "reference_sample", "reference", "reference_samples_list"))
    if sv is not None: raw_samples.extend(_flatten(sv))
    if not raw_samples and _looks_like_sample(container):
        raw_samples.append(container)
    samples = [s if isinstance(s, ReferenceSample) else ReferenceSample.from_raw(s) for s in raw_samples]

    hosts_to_check = []
    x99_dt = _parse_dt(_find_value(container, ("x99_observed", "x99", "x99_time", "host_x99", "x99_timestamp", "x99_observed_at", "x99_instant")))
    if x99_dt is not None: hosts_to_check.append(("x99", x99_dt))
    pentium_dt = _parse_dt(_find_value(container, ("pentium_observed", "pentium", "pentium_time", "host_pentium", "pentium_timestamp", "pentium_observed_at", "pentium_instant")))
    if pentium_dt is not None: hosts_to_check.append(("pentium", pentium_dt))
    obs_dt = _parse_dt(_find_value(container, ("observed_instant", "observed_at", "observed", "host_observed", "host_time", "host_instant", "claimed_instant", "claimed_time", "target_instant", "subject_instant")))
    # named x99/pentium hosts are required; generic observed instant cannot substitute for named host observations
    now_raw = _find_value(container, ("now", "current_time", "assessment_time", "reference_now", "evaluated_at", "evaluation_time", "check_time"))
    now = _parse_dt(now_raw) if now_raw is not None else None
    if now is None:
        candidates = [s.captured_at for s in samples if s.captured_at is not None]
        candidates += [s.reference_instant for s in samples if s.reference_instant is not None]
        candidates += [dt for _, dt in hosts_to_check]
        if candidates: now = max(candidates)

    if not samples:
        return False, REASON_MISSING_REFERENCE, {"schema": SCHEMA, "reason": REASON_MISSING_REFERENCE, "sample_count": 0}
    if now is None:
        return False, REASON_MISSING_CAPTURE_TIME, {"schema": SCHEMA, "reason": REASON_MISSING_CAPTURE_TIME, "sample_count": len(samples)}

    valid_samples = []
    sample_results = []
    first_failure = None
    for s in samples:
        ok, reason, details = _validate_sample(s, now)
        sample_results.append({"source_id": s.source_id, "ok": ok, "reason": reason, "details": details})
        if ok: valid_samples.append(s)
        elif first_failure is None: first_failure = (ok, reason, details)
    if not valid_samples:
        ok, reason, details = first_failure if first_failure else (False, REASON_INVALID_REFERENCE, {})
        return False, reason, {"schema": SCHEMA, "reason": reason, "now": now.isoformat(), "samples": sample_results, "valid_reference_count": 0, "reference_count": len(samples)}

    if x99_dt is None or pentium_dt is None:
        details = {"schema": SCHEMA, "reason": REASON_MISSING_HOST, "now": now.isoformat(), "reference_count": len(samples), "valid_reference_count": len(valid_samples), "samples": sample_results, "host_results": {}, "verified": False}
        return False, REASON_MISSING_HOST, details
    # Cross-host observations must be fresh relative to assessment time,
    # not merely close to an injected reference instant.
    for host_id, observed in hosts_to_check:
        age = (now - observed).total_seconds()
        if age < -MAX_TOLERANCE_SECONDS:
            return False, REASON_FUTURE_DATA, {"schema": SCHEMA, "reason": REASON_FUTURE_DATA, "host_id": host_id, "host_age_seconds": age}
        if age > MAX_TOLERANCE_SECONDS:
            return False, REASON_STALE_DATA, {"schema": SCHEMA, "reason": REASON_STALE_DATA, "host_id": host_id, "host_age_seconds": age}
    host_results = {}
    overall_ok = True
    overall_reason = REASON_OK
    for host_id, observed in hosts_to_check:
        host_ok = False
        best_skew = None
        matched_source = None
        per_sample = []
        for s in valid_samples:
            if not s.verified:
                per_sample.append({"source_id": s.source_id, "verified": False, "skew_seconds": None, "bound_seconds": None, "ok": False}); continue
            skew = abs(_to_utc_seconds(observed) - _to_utc_seconds(s.reference_instant))
            bound = _effective_bound(s, container)
            if bound is None:
                sample_ok = False
                overall_reason = REASON_INVALID_BOUNDS
            else:
                sample_ok = skew <= bound
            per_sample.append({"source_id": s.source_id, "verified": True, "skew_seconds": skew, "bound_seconds": bound, "ok": sample_ok})
            if best_skew is None or skew < best_skew: best_skew = skew
            if sample_ok:
                host_ok = True; matched_source = s.source_id; break
        host_results[host_id] = {
            "observed_instant": observed.isoformat(),
            "ok": host_ok,
            "skew_seconds": best_skew,
            "bound_seconds": _effective_bound(valid_samples[0], container) if valid_samples else None,
            "matched_reference": matched_source,
            "samples": per_sample,
        }
        if host_ok:
            pass
        else:
            overall_ok = False
            if overall_reason != REASON_INVALID_BOUNDS:
                overall_reason = REASON_CLOCK_SKEW
    out_details = {
        "schema": SCHEMA,
        "reason": (REASON_OK if (hosts_to_check and overall_ok) else (overall_reason if hosts_to_check else REASON_OK)),
        "now": now.isoformat(),
        "reference_count": len(samples),
        "valid_reference_count": len(valid_samples),
        "samples": sample_results,
        "host_results": host_results,
        "verified": overall_ok if hosts_to_check else True,
    }
    if hosts_to_check:
        if overall_ok: return True, REASON_OK, out_details
        return False, overall_reason, out_details
    return True, REASON_OK, out_details

def verify_trusted_cross_host_clock(*a, **k): return verify_cross_host_clock(*a, **k)
def check_cross_host_clock(*a, **k): return verify_cross_host_clock(*a, **k)
def trusted_cross_host_clock(*a, **k): return verify_cross_host_clock(*a, **k)
def verify_clock_agreement(*a, **k): return verify_cross_host_clock(*a, **k)
def verify_reference_agreement(*a, **k): return verify_cross_host_clock(*a, **k)
def verify_host_clock(*a, **k): return verify_cross_host_clock(*a, **k)
def cross_host_clock_ok(*a, **k):
    ok, _, _ = verify_cross_host_clock(*a, **k); return bool(ok)
def verify_trusted_cross_host_time(*a, **k): return verify_cross_host_clock(*a, **k)
def is_trusted(result):
    if isinstance(result, tuple) and result: return bool(result[0])
    if isinstance(result, Mapping): return bool(result.get("verified", result.get("ok", False)))
    return bool(result)

def integration_requirements():
    return [
        "Keep existing atlas_shadow_bridge.trusted_host_now() unchanged; never substitute it for cross-host proof.",
        "Inject independently attested reference samples with source_id, captured_at UTC, reference_instant UTC, max_age, RTT/uncertainty, TTL.",
        "Caller verifies signed provenance and sets verified=True only after successful verification; unverified samples fail closed.",
        "No NTP/SSH/network calls, secrets, clock writes, or services.",
        "Wire as observe-only gate; preserve shadow read-only behavior; fail closed.",
        "At least one verified reference sample required for healthy clock; x99 drift beyond RTT/uncertainty bounds is BLOCKED.",
        "UTC offsets are encoding only, never drift evidence.",
        "Run unittest discover before integration.",
    ]
INTEGRATION_REQUIREMENTS = integration_requirements()
