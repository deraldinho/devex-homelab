"""CP16 independent red-team hardening reproduction tests (M1-M6).

These tests intentionally reproduce audit findings. They do not weaken or skip
any assertion. They may remain RED until runtime hardening agents are integrated.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import atlas_shadow_bridge as sb
import durable_incidents as di
import system_supervision as ss
import trusted_cross_host_clock as tcc

T = datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc)
WIN = "windows_worker_observer"
LINUX = "linux_systemd_observer"
POLICY = {"schema": ss.KILL_SWITCH_SCHEMA, "enabled": True, "kill_switch": False}
MINIMAL_POLICY = {
    "schema": "atlas.autonomy.policy.v2",
    "mode": "observe_only",
    "enabled": True,
    "kill_switch": False,
    "auto_approve": False,
    "auto_write": False,
    "allowed_actions": ["diagnose_readonly"],
    "origins": ["x99_worker"],
    "kinds": ["worker_stale", "worker_duplicate"],
    "limits": {"daily_readonly_missions": 5, "max_concurrent": 2, "max_total_cost_usd": 0},
}
DEFAULT_KEY = bytes(range(32))


def _sample(**kw):
    base = dict(
        source_id="pentium_ntp",
        captured_at=T,
        reference_instant=T,
        max_age_seconds=300,
        rtt_bound_seconds=5,
        uncertainty_seconds=2,
        ttl_seconds=600,
        verified=True,
        provenance={"signed": True, "verified": True},
    )
    base.update(kw)
    return tcc.ReferenceSample(**base)


def beat(observer, seq=1, at=T, detector=None):
    return {"schema": ss.HEARTBEAT_SCHEMA, "observer": observer,
            "detector": detector or (observer + ".probe"),
            "sequence": seq, "observed_at": at.isoformat()}


def provider_from_mapping(mapping):
    def provide(observer):
        return mapping.get(observer)
    return provide


# ---------------------------------------------------------------------------
# M1: no hosts false green
# ---------------------------------------------------------------------------

class TestM1NoHostsFalseGreen(unittest.TestCase):
    def test_reference_without_observed_hosts_fails_closed(self):
        ok, reason, details = tcc.verify_cross_host_clock(
            reference_samples=[_sample()],
            now=T,
        )
        self.assertFalse(ok, "verification must fail closed without x99/pentium hosts")
        self.assertEqual(reason, tcc.REASON_MISSING_HOST)


# ---------------------------------------------------------------------------
# M2: oversized skew tolerance
# ---------------------------------------------------------------------------

class TestM2OversizedSkewTolerance(unittest.TestCase):
    def test_tolerance_one_billion_is_not_accepted(self):
        s = _sample()
        result = tcc.verify_cross_host_clock(
            x99_observed=T,
            pentium_observed=T,
            reference_samples=[s],
            now=T,
            tolerance_seconds=1_000_000_000,
        )
        self.assertFalse(result[0], "oversized tolerance must not produce a healthy result")
        invalid_reason = getattr(tcc, "REASON_INVALID_TOLERANCE", tcc.REASON_INVALID_BOUNDS)
        self.assertEqual(result[1], invalid_reason)

    def test_small_historic_tolerance_still_blocks_120_second_drift(self):
        s = _sample()
        result = tcc.verify_cross_host_clock(
            x99_observed=T + timedelta(seconds=120),
            pentium_observed=T,
            reference_samples=[s],
            now=T,
        )
        self.assertFalse(result[0])
        self.assertEqual(result[1], tcc.REASON_UTC_SKEW)

    def test_clock_within_two_seconds_passes_with_bounded_tolerance(self):
        s = _sample()
        result = tcc.verify_cross_host_clock(
            x99_observed=T + timedelta(seconds=2),
            pentium_observed=T,
            reference_samples=[s],
            now=T,
        )
        self.assertTrue(result[0], result)
        self.assertEqual(result[1], tcc.REASON_OK)


# ---------------------------------------------------------------------------
# M3: future/stale independent reference
# ---------------------------------------------------------------------------

class TestM3FutureStaleIndependentReference(unittest.TestCase):
    def test_future_reference_instant_blocked_even_if_capture_now(self):
        s = _sample(reference_instant=T + timedelta(seconds=10), captured_at=T)
        ok, reason, _ = tcc.verify_cross_host_clock(
            x99_observed=T,
            pentium_observed=T,
            reference_samples=[s],
            now=T,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, tcc.REASON_FUTURE_DATA)

    def test_stale_reference_instant_blocked_even_if_capture_now(self):
        s = _sample(reference_instant=T - timedelta(seconds=400), captured_at=T)
        ok, reason, _ = tcc.verify_cross_host_clock(
            x99_observed=T,
            pentium_observed=T,
            reference_samples=[s],
            now=T,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, tcc.REASON_STALE_REFERENCE)

    def test_unknown_reference_source_rejected(self):
        s = _sample(source_id="unknown")
        ok, reason, _ = tcc.verify_cross_host_clock(
            x99_observed=T,
            pentium_observed=T,
            reference_samples=[s],
            now=T,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, tcc.REASON_UNTRUSTED_SOURCE)


# ---------------------------------------------------------------------------
# M4: materialize symlink same-content
# ---------------------------------------------------------------------------

class TestM4MaterializeSymlinkSameContent(unittest.TestCase):
    def test_symlink_guard_precedes_same_content_return(self):
        from durable_incidents import reconcile, materialize

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        p = Path(temp.name)
        db = p / "ledger.db"
        out = p / "outbox"
        reconcile(db, out, source="x99_worker",
                  findings={"worker_not_running": {"summary": "worker stopped"}},
                  at=T)

        original = Path.is_symlink
        Path.is_symlink = lambda self: True
        try:
            with self.assertRaises(PermissionError):
                materialize(db, out, source="x99_worker")
        finally:
            Path.is_symlink = original


# ---------------------------------------------------------------------------
# M5: unsafe SQLite URI path special chars
# ---------------------------------------------------------------------------

class TestM5UnsafeSqliteUriPathSpecialChars(unittest.TestCase):
    def test_ledger_path_with_reserved_uri_chars_stays_readable(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        ledger = root / "weird#pct" / "ledger#%.db"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        from durable_incidents import connect
        connect(ledger).close()

        mapping = {WIN: beat(WIN), LINUX: beat(LINUX)}
        report = ss.observe(
            provider=mapping.get,
            policy=POLICY,
            ledger_path=ledger,
            now=T,
            stale_window_seconds=ss.STALE_WINDOW_SECONDS,
        )
        self.assertEqual(report["alarms"]["status"], "CLEAR")
        self.assertTrue(report["alarms"]["ledger_present"])


# ---------------------------------------------------------------------------
# M6: HEALTHY malformed/naive heartbeat ignored
# ---------------------------------------------------------------------------

class TestM6HealthyMalformedHeartbeatIgnored(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        host_seam = mock.patch.object(sb, "trusted_host_now", lambda: T)
        host_seam.start()
        self.addCleanup(host_seam.stop)

    def _healthy_report(self):
        import copy
        provider = provider_from_mapping({WIN: beat(WIN, at=T), LINUX: beat(LINUX, at=T)})
        base = ss.observe(provider=provider, policy=POLICY, ledger_path=None,
                          now=T, stale_window_seconds=ss.STALE_WINDOW_SECONDS)
        report = copy.deepcopy(base)
        for obs in (WIN, LINUX):
            report["heartbeats"][obs]["status"] = "HEALTHY"
        return report

    def _call_with_bad_observed_at(self, value):
        bad = self._healthy_report()
        bad["heartbeats"][WIN]["observed_at"] = value
        expected = getattr(sb, "REASON_MALFORMED_HEARTBEAT", "MALFORMED_HEARTBEAT")
        with mock.patch.object(sb.ss, "observe", return_value=bad):
            report = sb.shadow_pre_flight(
                provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
                key=DEFAULT_KEY,
                policy=MINIMAL_POLICY,
                now=T,
            )
        return report, expected

    def test_empty_observed_at_fails_closed(self):
        report, expected = self._call_with_bad_observed_at("")
        self.assertEqual(report["reason"], expected)
        self.assertEqual(report["heartbeat"], WIN)
        self.assertEqual(report["heartbeat_status"], "HEALTHY")

    def test_malformed_observed_at_fails_closed(self):
        report, expected = self._call_with_bad_observed_at("not-a-timestamp")
        self.assertEqual(report["reason"], expected)

    def test_naive_observed_at_fails_closed(self):
        report, expected = self._call_with_bad_observed_at(T.replace(tzinfo=None).isoformat())
        self.assertEqual(report["reason"], expected)

    def test_none_observed_at_fails_closed(self):
        report, expected = self._call_with_bad_observed_at(None)
        self.assertEqual(report["reason"], expected)

    def test_future_classification_preserved_for_valid_future_observed_at(self):
        report, _ = self._call_with_bad_observed_at((T + timedelta(seconds=5)).isoformat())
        self.assertEqual(report["reason"], sb.REASON_FUTURE_HEARTBEAT)


if __name__ == "__main__":
    unittest.main()
