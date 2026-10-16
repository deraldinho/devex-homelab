"""Shadow clock guard: fail-closed multi-host time skew verification.

Verifies timezone-aware UTC observed instants from multiple hosts (x99, pentium)
against an independent reference instant with optional bounded age.  Fails closed
on any untrusted or unconfigured condition.  UTC offset representation is preserved
for correctness but is NOT used as the clock-drift signal — skew is detected from
the UTC timestamp difference between the two host observations.

Design notes:
  - No real NTP queries, services, or network access.
  - All inputs are pure, injected fixtures.  Invalid inputs return
    (False, reason, details) rather than raising (except programmer bugs).
  - The UTC offset of each datetime is validated as present and correct,
    but clock-drift is determined by the absolute UTC timestamp difference
    between the x99 and pentium observations, not by offset comparisons.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple, Dict, Any

# ---------------------------------------------------------------------------
# Reason codes (clear, machine-readable)
# ---------------------------------------------------------------------------

REASON_OK = "OK"
REASON_UTC_SKEW = "UTC_SKEW"
REASON_NAIVE_DATETIME = "NAIVE_DATETIME"
REASON_FUTURE_DATA = "FUTURE_DATA"
REASON_STALE_DATA = "STALE_DATA"
REASON_INVALID_TOLERANCE = "INVALID_TOLERANCE"
REASON_MISSING_HOST = "MISSING_HOST"


def _validate_datetime(label: str, value: datetime) -> Tuple[bool, str | None]:
    """Validate that *value* is a non-None timezone-aware datetime.

    Returns ``(is_valid, error_reason)``.  If *value* is valid the second
    element is ``None``.
    """
    if value is None:
        return False, REASON_MISSING_HOST
    if not isinstance(value, datetime):
        return False, REASON_NAIVE_DATETIME
    if getattr(value, "tzinfo", None) is None or value.utcoffset() is None:
        return False, REASON_NAIVE_DATETIME
    return True, None


def _to_utc_seconds(value: datetime) -> float:
    """Convert a timezone-aware datetime to UTC epoch seconds.

    Uses :meth:`datetime.timestamp`, which for a timezone-aware datetime is
    computed from exact integer day/second arithmetic against the UTC epoch.
    The result therefore depends only on the *instant* the datetime denotes,
    never on its UTC-offset representation and never on the host machine's
    local timezone.  (A ``datetime`` has no ``total_seconds()`` — that method
    belongs to :class:`datetime.timedelta` — so the epoch value is obtained
    through ``timestamp()`` rather than by calling it on the datetime.)
    """
    return value.astimezone(timezone.utc).timestamp()


def verify_time_skew(
    x99_observed: datetime,
    pentium_observed: datetime,
    reference_instant: datetime,
    *,
    tolerance_seconds: int = 120,
    bounded_age_seconds: int | None = None,
) -> tuple[bool, str, dict]:
    """Fail-closed multi-host time skew verification.

    Args:
        x99_observed: timezone-aware UTC observed instant from the x99 host.
        pentium_observed: timezone-aware UTC observed instant from the pentium
            host.
        reference_instant: independent timezone-aware UTC reference instant.
        tolerance_seconds: max allowed absolute skew (in seconds) between the
            x99 and pentium observed instants.  Defaults to 120 (2 minutes),
            matching the historical x99/Pentium drift baseline.
        bounded_age_seconds: optional maximum age (in seconds) for observed
            data.  If ``None`` the age check is skipped.  Must be a positive
            integer when supplied.

    Returns:
        ``(ok, reason, details)`` tuple where:

        - ``ok`` is ``True`` iff every check passes.
        - ``reason`` is a code string (``REASON_OK`` on success).
        - ``details`` is a :dict`` with diagnostic particulars.

    Fails closed: any invalid input returns ``(False, reason, details)`` rather
    than proceeding.  No real NTP or service calls are made.
    """
    # ---------------------------------------------------------------------
    # 1. Validate scalar configuration parameters (fail closed on bad
    #    tolerance regardless of whether bounded-age checking is enabled).
    # ---------------------------------------------------------------------
    if not isinstance(tolerance_seconds, int) or tolerance_seconds <= 0:
        return False, REASON_INVALID_TOLERANCE, {
            "tolerance_seconds": tolerance_seconds,
            "bounded_age_seconds": bounded_age_seconds,
        }
    if bounded_age_seconds is not None and (
        not isinstance(bounded_age_seconds, int) or bounded_age_seconds <= 0
    ):
        return False, REASON_INVALID_TOLERANCE, {
            "tolerance_seconds": tolerance_seconds,
            "bounded_age_seconds": bounded_age_seconds,
        }

    # ---------------------------------------------------------------------
    # 2. Validate all three datetime inputs are non-None, timezone-aware.
    # ---------------------------------------------------------------------
    ref_ok, ref_reason = _validate_datetime("reference_instant", reference_instant)
    if not ref_ok:
        return False, ref_reason, {"invalid_instant": None}

    x99_ok, x99_reason = _validate_datetime("x99_observed", x99_observed)
    if not x99_ok:
        return False, x99_reason, {"invalid_instant": None}

    pentium_ok, pentium_reason = _validate_datetime("pentium_observed", pentium_observed)
    if not pentium_ok:
        return False, pentium_reason, {"invalid_instant": None}

    # ---------------------------------------------------------------------
    # 3. Convert to UTC epoch seconds for drift & age calculations.
    # ---------------------------------------------------------------------
    ref_utc = _to_utc_seconds(reference_instant)
    x99_utc = _to_utc_seconds(x99_observed)
    pentium_utc = _to_utc_seconds(pentium_observed)

    # ---------------------------------------------------------------------
    # 4. Reject future observations relative to the reference instant.
    # ---------------------------------------------------------------------
    if x99_utc > ref_utc:
        return False, REASON_FUTURE_DATA, {
            "observed_instant": x99_observed.isoformat(),
            "reference_instant": reference_instant.isoformat(),
        }
    if pentium_utc > ref_utc:
        return False, REASON_FUTURE_DATA, {
            "observed_instant": pentium_observed.isoformat(),
            "reference_instant": reference_instant.isoformat(),
        }

    # ---------------------------------------------------------------------
    # 5. Optional bounded-age check (parameters already validated above).
    # ---------------------------------------------------------------------
    if bounded_age_seconds is not None:
        x99_age = ref_utc - x99_utc          # positive = old data
        pentium_age = ref_utc - pentium_utc
        if x99_age > bounded_age_seconds:
            return False, REASON_STALE_DATA, {
                "host": "x99",
                "observed_at": x99_observed.isoformat(),
                "age_seconds": x99_age,
                "bounded_age_seconds": bounded_age_seconds,
            }
        if pentium_age > bounded_age_seconds:
            return False, REASON_STALE_DATA, {
                "host": "pentium",
                "observed_at": pentium_observed.isoformat(),
                "age_seconds": pentium_age,
                "bounded_age_seconds": bounded_age_seconds,
            }

    # ---------------------------------------------------------------------
    # 6. Check skew between the two host observations.
    #    UTC offset is NOT used as the drift signal; we compare the UTC
    #    timestamps directly.
    # ---------------------------------------------------------------------
    skew_seconds = abs(x99_utc - pentium_utc)
    if skew_seconds > tolerance_seconds:
        return False, REASON_UTC_SKEW, {
            "host_x99": x99_observed.isoformat(),
            "host_pentium": pentium_observed.isoformat(),
            "skew_seconds": skew_seconds,
            "tolerance_seconds": tolerance_seconds,
        }

    # ---------------------------------------------------------------------
    # 7. All checks passed.
    # ---------------------------------------------------------------------
    return True, REASON_OK, {
        "host_x99": x99_observed.isoformat(),
        "host_pentium": pentium_observed.isoformat(),
        "reference_instant": reference_instant.isoformat(),
        "skew_seconds": skew_seconds,
        "tolerance_seconds": tolerance_seconds,
        "bounded_age_seconds": bounded_age_seconds,
    }