import unittest
from datetime import datetime, timezone, timedelta
from trusted_cross_host_clock import verify_cross_host_clock, REASON_INVALID_BOUNDS, REASON_INVALID_MAX_AGE, REASON_INVALID_TTL, REASON_UNVERIFIED_PROVENANCE, REASON_FUTURE_DATA, REASON_STALE_DATA

NOW = datetime(2026, 10, 15, tzinfo=timezone.utc)
def payload(**changes):
    sample = dict(source_id="signed-clock", captured_at=NOW, reference_instant=NOW,
                  max_age_seconds=60, rtt_bound_seconds=1, uncertainty_seconds=1,
                  ttl_seconds=60, verified=True, provenance={"verified": True})
    sample.update(changes)
    return dict(reference_samples=[sample], x99_observed=NOW, pentium_observed=NOW, now=NOW)

class ClockHardeningRegression(unittest.TestCase):
    def check_rejected(self, reason, **change):
        ok, actual, _ = verify_cross_host_clock(payload(**change))
        self.assertFalse(ok)
        self.assertEqual(actual, reason)
    def test_reject_large_rtt(self):
        self.check_rejected(REASON_INVALID_BOUNDS, rtt_bound_seconds=100000)
    def test_reject_large_uncertainty(self):
        self.check_rejected(REASON_INVALID_BOUNDS, uncertainty_seconds=100000)
    def test_reject_nonfinite_uncertainty(self):
        self.check_rejected(REASON_INVALID_BOUNDS, uncertainty_seconds=float("inf"))
    def test_reject_large_max_age(self):
        self.check_rejected(REASON_INVALID_MAX_AGE, max_age_seconds=100000)
    def test_reject_large_ttl(self):
        self.check_rejected(REASON_INVALID_TTL, ttl_seconds=100000)
    def test_reject_conflicting_provenance(self):
        self.check_rejected(REASON_UNVERIFIED_PROVENANCE, provenance={"verified": False})
    def test_reject_future_host(self):
        data = payload()
        data['x99_observed'] = NOW + timedelta(seconds=400)
        self.assertEqual(verify_cross_host_clock(data)[1], REASON_FUTURE_DATA)
    def test_reject_stale_host(self):
        data = payload()
        data['pentium_observed'] = NOW - timedelta(seconds=400)
        self.assertEqual(verify_cross_host_clock(data)[1], REASON_STALE_DATA)
    def test_accept_valid_signed_sample(self):
        self.assertTrue(verify_cross_host_clock(payload())[0])

if __name__ == "__main__":
    unittest.main()
