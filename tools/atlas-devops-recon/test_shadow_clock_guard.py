"""TDD for shadow_clock_guard.py: fail-closed multi-host time skew verification.

Every dependency is mocked or injected.  No real Windows service, systemd unit,
network or production file is touched.  Observed instants arrive as
timezone-aware :class:~datetime.datetime objects.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from shadow_clock_guard import (
    REASON_OK,
    REASON_UTC_SKEW,
    REASON_NAIVE_DATETIME,
    REASON_FUTURE_DATA,
    REASON_STALE_DATA,
    REASON_INVALID_TOLERANCE,
    REASON_MISSING_HOST,
    verify_time_skew,
)

T = datetime(2026, 10, 14, 18, 0, 0, tzinfo=timezone.utc)
X99 = "x99_host"
PENTIUM = "pentium_host"


def make_observed(at: datetime) -> datetime:
    """Coerce a datetime into the shape expected by verify_time_skew."""
    if at.tzinfo is None:
        return at
    return at


# -----------------------------------------------------------------------------
# Helper: valid UTC instants
# -----------------------------------------------------------------------------

def x99_at(seconds_offset: int = 0) -> datetime:
    """x99 observed instant relative to T."""
    return T + timedelta(seconds=seconds_offset)

def pentium_at(seconds_offset: int = 0) -> datetime:
    """pentium observed instant relative to T."""
    return T + timedelta(seconds=seconds_offset)


# -----------------------------------------------------------------------------
# Base valid-input GREEN test
# -----------------------------------------------------------------------------

class ValidInputTests(unittest.TestCase):
    """verify_time_skew returns REASON_OK when all checks pass."""

    def test_within_tolerance_no_age(self):
        """x99 and pentium within default 120s tolerance, no bounded age."""
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(0),
            pentium_observed=pentium_at(0),
            reference_instant=T,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, REASON_OK)

    def test_within_tolerance_with_bounded_age(self):
        """Within tolerance and young enough for the bounded-age window."""
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(0),
            pentium_observed=pentium_at(60),
            # Reference is "now": it must be >= every observed instant,
            # otherwise the observation would be future data (rejected above).
            reference_instant=T + timedelta(seconds=60),
            bounded_age_seconds=120,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, REASON_OK)

    def test_zero_skew_identical_observations(self):
        """Identical x99/pentium instants always pass (skew = 0)."""
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(42),
            pentium_observed=pentium_at(42),
            reference_instant=T + timedelta(seconds=42),  # now >= observations
        )
        self.assertTrue(ok)
        self.assertEqual(reason, REASON_OK)


# -----------------------------------------------------------------------------
# UTC skew RED tests
# -----------------------------------------------------------------------------

class UTCSkewFailClosedTests(unittest.TestCase):
    """verify_time_skew returns REASON_UTC_SKEW when skew exceeds tolerance."""

    def test_skew_exceeds_tolerance(self):
        """x99 at T+0, pentium at T+200 => skew 200 > 120s tolerance."""
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(0),
            pentium_observed=pentium_at(200),
            reference_instant=T + timedelta(seconds=200),  # now >= observations
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_UTC_SKEW)

    def test_skew_exactly_tolerance_ok(self):
        """Skew exactly at tolerance (120s) should pass (not > tolerance)."""
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(0),
            pentium_observed=pentium_at(120),
            reference_instant=T + timedelta(seconds=120),  # now >= observations
        )
        # skew_seconds == tolerance_seconds => not >, so OK
        self.assertTrue(ok)
        self.assertEqual(reason, REASON_OK)

    def test_negative_skew_wrapped(self):
        """Pentium earlier than x99; absolute skew still computed."""
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(200),
            pentium_observed=pentium_at(0),
            reference_instant=T + timedelta(seconds=200),  # now >= observations
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_UTC_SKEW)


# -----------------------------------------------------------------------------
# Naive datetime RED tests
# -----------------------------------------------------------------------------

class NaiveDatetimeTests(unittest.TestCase):
    """verify_time_skew rejects naive (no-tz) datetimes."""

    def test_naive_x99(self):
        ok, reason, details = verify_time_skew(
            x99_observed=T.replace(tzinfo=None),  # naive
            pentium_observed=pentium_at(0),
            reference_instant=T,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_NAIVE_DATETIME)

    def test_naive_pentium(self):
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(0),
            pentium_observed=T.replace(tzinfo=None),  # naive
            reference_instant=T,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_NAIVE_DATETIME)

    def test_naive_reference(self):
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(0),
            pentium_observed=pentium_at(0),
            reference_instant=T.replace(tzinfo=None),  # naive
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_NAIVE_DATETIME)


# -----------------------------------------------------------------------------
# Future data RED tests
# -----------------------------------------------------------------------------

class FutureDataTests(unittest.TestCase):
    """verify_time_skew rejects observed instants that are future relative
    to the reference instant."""
    def test_future_x99(self):
        ok, reason, details = verify_time_skew(
            x99_observed=T + timedelta(seconds=1),  # future
            pentium_observed=pentium_at(0),
            reference_instant=T,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_FUTURE_DATA)

    def test_future_pentium(self):
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(0),
            pentium_observed=T + timedelta(seconds=1),  # future
            reference_instant=T,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_FUTURE_DATA)


# -----------------------------------------------------------------------------
# Bounded age RED/GREEN tests
# -----------------------------------------------------------------------------

class BoundedAgeTests(unittest.TestCase):
    """verify_time_skew rejects stale data when bounded_age_seconds is exceeded."""

    def test_x99_too_stale(self):
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(-200),   # 200s ago
            pentium_observed=pentium_at(0),
            reference_instant=T,
            bounded_age_seconds=120,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_STALE_DATA)
        self.assertEqual(details["host"], "x99")

    def test_pentium_too_stale(self):
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(0),
            pentium_observed=pentium_at(-180),  # 180s ago
            reference_instant=T,
            bounded_age_seconds=120,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_STALE_DATA)
        self.assertEqual(details["host"], "pentium")

    def test_within_bounded_age_ok(self):
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(-60),
            pentium_observed=pentium_at(-60),
            reference_instant=T,
            bounded_age_seconds=120,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, REASON_OK)


# -----------------------------------------------------------------------------
# Invalid tolerance RED tests
# -----------------------------------------------------------------------------

class InvalidToleranceTests(unittest.TestCase):
    """verify_time_skew rejects invalid tolerance parameters."""

    def test_tolerance_zero(self):
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(0),
            pentium_observed=pentium_at(0),
            reference_instant=T,
            tolerance_seconds=0,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_INVALID_TOLERANCE)

    def test_tolerance_negative(self):
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(0),
            pentium_observed=pentium_at(0),
            reference_instant=T,
            tolerance_seconds=-5,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_INVALID_TOLERANCE)

    def test_bounded_age_non_positive(self):
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(0),
            pentium_observed=pentium_at(0),
            reference_instant=T,
            bounded_age_seconds=0,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_INVALID_TOLERANCE)

    def test_bounded_age_float_rejected(self):
        # float is not int; the guard checks isinstance(..., int)
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(0),
            pentium_observed=pentium_at(0),
            reference_instant=T,
            bounded_age_seconds=120.0,
        )
        # float passes the int check? actually isinstance(120.0, int) is False
        # so it should be INVALID_TOLERANCE. But bounded_age_seconds is the
        # *second* positional after reference; let me verify the logic.
        # In our code, bounded_age_seconds non-int or <=0 triggers
        # REASON_INVALID_TOLERANCE because we bundle the check together.
        # Actually re-reading the code: the tolerance check and bounded_age
        # check are bundled: if bounded_age_seconds is not None we check both.
        # So a float bounded_age should hit the isinstance(tolerance_seconds,
        # <=0) check first? No, tolerance_seconds is the default 120. The
        # bounded_age_seconds check is: if not isinstance(bounded_age_seconds,
        # int) or bounded_age_seconds <= 0. A float 120.0 fails isinstance(int),
        # so it should return REASON_INVALID_TOLERANCE.
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_INVALID_TOLERANCE)


# -----------------------------------------------------------------------------
# Missing host RED tests
# -----------------------------------------------------------------------------

class MissingHostTests(unittest.TestCase):
    """verify_time_skew rejects when a host observed instant is None."""

    def test_none_x99(self):
        ok, reason, details = verify_time_skew(
            x99_observed=None,
            pentium_observed=pentium_at(0),
            reference_instant=T,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_MISSING_HOST)

    def test_none_pentium(self):
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(0),
            pentium_observed=None,
            reference_instant=T,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_MISSING_HOST)


# -----------------------------------------------------------------------------
# Comprehensive integration tests
# -----------------------------------------------------------------------------

class IntegrationTests(unittest.TestCase):
    """End-to-end combinations exercising the full guard logic."""

    def test_all_checks_pass_combined(self):
        """x99/pentium within tolerance, both young, reference valid."""
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(-30),
            pentium_observed=pentium_at(30),
            reference_instant=T + timedelta(seconds=30),  # now >= observations
            tolerance_seconds=120,
            bounded_age_seconds=120,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, REASON_OK)

    def test_skew_over_tolerance_within_age(self):
        """Skew exceeds tolerance even though data is young."""
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(-50),
            pentium_observed=pentium_at(100),
            reference_instant=T + timedelta(seconds=100),  # now >= observations
            tolerance_seconds=120,
            bounded_age_seconds=200,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_UTC_SKEW)  # skew=150 > 120

    def test_stale_overrides_skew_ok(self):
        """Old data is rejected even if skew would be fine."""
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(-200),
            pentium_observed=pentium_at(0),
            reference_instant=T,
            tolerance_seconds=120,
            bounded_age_seconds=120,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_STALE_DATA)


# -----------------------------------------------------------------------------
# Aware-offset normalization tests
# (UTC offset representation is NOT host clock drift)
# -----------------------------------------------------------------------------

class AwareOffsetNormalizationTests(unittest.TestCase):
    """The UTC offset of an aware datetime must never be mistaken for drift.

    Drift is the difference between UTC *instants*; two hosts may render the
    same instant with different offsets (+02:00, -05:00, UTC) without any
    skew, and two hosts may render the *same wall-clock label* with different
    offsets while actually being 2h apart in real time.
    """

    PLUS_2 = timezone(timedelta(hours=2))
    MINUS_5 = timezone(timedelta(hours=-5))

    def test_same_instant_different_offsets_zero_skew(self):
        """x99 in UTC vs pentium in +02:00, same instant => skew exactly 0."""
        ok, reason, details = verify_time_skew(
            x99_observed=T,
            pentium_observed=T.astimezone(self.PLUS_2),
            reference_instant=T,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, REASON_OK)
        self.assertAlmostEqual(details["skew_seconds"], 0.0, places=6)

    def test_aware_non_utc_hosts_are_valid_not_naive(self):
        """Fixed-offset aware datetimes are valid input (not NAIVE)."""
        ok, reason, details = verify_time_skew(
            x99_observed=T.astimezone(self.MINUS_5),
            pentium_observed=T.astimezone(self.PLUS_2),
            reference_instant=T,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, REASON_OK)
        self.assertAlmostEqual(details["skew_seconds"], 0.0, places=6)

    def test_identical_wall_clock_different_offsets_is_real_drift(self):
        """Same wall-clock label in UTC vs +02:00 = 2h real drift => skew."""
        ok, reason, details = verify_time_skew(
            x99_observed=datetime(2026, 10, 14, 18, 0, 0, tzinfo=timezone.utc),
            pentium_observed=datetime(
                2026, 10, 14, 18, 0, 0, tzinfo=self.PLUS_2
            ),  # == 16:00 UTC => 2h apart
            reference_instant=T,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_UTC_SKEW)
        self.assertAlmostEqual(details["skew_seconds"], 7200.0, places=6)

    def test_future_detected_under_non_utc_offset(self):
        """A genuinely future instant expressed in +02:00 is rejected."""
        ok, reason, details = verify_time_skew(
            x99_observed=x99_at(0),
            pentium_observed=(T + timedelta(seconds=1)).astimezone(self.PLUS_2),
            reference_instant=T,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_FUTURE_DATA)

    def test_stale_detected_under_non_utc_offset(self):
        """Age is measured on instants, not on the offset-adjusted labels."""
        ok, reason, details = verify_time_skew(
            x99_observed=(T - timedelta(seconds=200)).astimezone(self.MINUS_5),
            pentium_observed=pentium_at(0),
            reference_instant=T,
            bounded_age_seconds=120,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REASON_STALE_DATA)
        self.assertEqual(details["host"], "x99")
        self.assertAlmostEqual(details["age_seconds"], 200.0, places=6)

    def test_to_utc_seconds_is_offset_independent(self):
        """_to_utc_seconds maps equal instants to one identical epoch value."""
        from shadow_clock_guard import _to_utc_seconds

        utc_seconds = _to_utc_seconds(T)
        self.assertAlmostEqual(
            utc_seconds, _to_utc_seconds(T.astimezone(self.PLUS_2)), places=6
        )
        self.assertAlmostEqual(
            utc_seconds, _to_utc_seconds(T.astimezone(self.MINUS_5)), places=6
        )
        # Epoch origin: 1970-01-01T00:00:00Z is exactly 0.0 epoch seconds.
        self.assertAlmostEqual(
            _to_utc_seconds(datetime(1970, 1, 1, tzinfo=timezone.utc)),
            0.0,
            places=6,
        )
        # A real 300s gap stays 300s regardless of offset representation.
        self.assertAlmostEqual(
            _to_utc_seconds(T + timedelta(seconds=300)) - utc_seconds,
            300.0,
            places=6,
        )


if __name__ == "__main__":
    unittest.main()