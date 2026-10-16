"""TDD for atlas_shadow_bridge.py: read-only shadow pre-flight adapter.

Every dependency is mocked or injected. No real Windows service, systemd unit,
network or production file is touched. Observers arrive through a unittest.mock
seam and every ledger lives inside a temporary directory.
"""
from pathlib import Path
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone

import atlas_shadow_bridge as sb
import system_supervision as ss
import incident_pipeline

T = datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc)
WIN = "windows_worker_observer"
LINUX = "linux_systemd_observer"

# Minimal valid autonomy policy that passes incident_pipeline.validate_policy()
# (which delegates to autonomy_policy_gate.validate_policy()).
# Note: schema must be "atlas.autonomy.policy.v2" for this gate.
# The kill-switch decision is inlined in the bridge (separate from the policy schema).
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
    "limits": {
        "daily_readonly_missions": 5,
        "max_concurrent": 2,
        "max_total_cost_usd": 0,
    },
}
DEFAULT_KEY = bytes(range(32))  # 32-byte TEST key, never production


def beat(observer, seq=1, at=T, detector=None):
    return {"schema": ss.HEARTBEAT_SCHEMA, "observer": observer,
            "detector": detector or (observer + ".probe"),
            "sequence": seq, "observed_at": at.isoformat()}


def provider_from_mapping(mapping):
    """Return a callable provider used by ss.observe()."""
    def provide(observer):
        return mapping.get(observer)
    return provide


class ShadowBridgeTests(unittest.TestCase):
    """Shadow pre-flight adapter observability tests."""

    def setUp(self):
        self.temp = __import__('tempfile').TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # The bridge derives clock skew from the trusted host instant, not
        # from a UTC timezone offset. Pin that seam to the fixture instant T
        # so skew assertions are deterministic; the production default of
        # trusted_host_now() remains the live host clock and is never
        # bypassed for callers that do not inject it.
        host_seam = mock.patch.object(sb, "trusted_host_now", lambda: T)
        host_seam.start()
        self.addCleanup(host_seam.stop)

    def _make_ledger(self, name="ledger.db"):
        db = self.root / name
        import sqlite3 as _sq
        con = _sq.connect(str(db), isolation_level=None, timeout=10)
        con.execute("PRAGMA busy_timeout=10000")
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript("""
            CREATE TABLE IF NOT EXISTS incidents(
                id TEXT PRIMARY KEY, source TEXT NOT NULL, kind TEXT NOT NULL,
                occurrence INTEGER NOT NULL, status TEXT NOT NULL
                CHECK(status IN ('open','resolved')),
                payload TEXT NOT NULL, opened_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(source,kind,occurrence)
            );
        """)
        con.close()
        return db

    # ---- reason-code basics -------------------------------------------------

    def test_ok_healthy_heartbeats_and_empty_ledger(self):
        """Minimal pass: healthy heartbeats, no ledger -> REASON_OK.
        Supervision is DEGRADED when no ledger is configured (consistent with
        CP11 ss.observe() behaviour: alarms status UNKNOWN -> not CLEAR)."""
        report = sb.shadow_pre_flight(
            provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
            key=DEFAULT_KEY,
            policy=MINIMAL_POLICY,
            ledger_path=None,
            now=T,
        )
        self.assertEqual(report["reason"], sb.REASON_OK)
        # No ledger = alarms status UNKNOWN -> not CLEAR -> supervision DEGRADED
        self.assertEqual(report["supervision"], "DEGRADED")
        self.assertEqual(report["mode"], "MONITORING")

    def test_ok_with_ledger_present_and_clear(self):
        """With a clean ledger (no open incidents) still REASON_OK."""
        ledger = self._make_ledger()
        report = sb.shadow_pre_flight(
            provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
            key=DEFAULT_KEY,
            policy=MINIMAL_POLICY,
            ledger_path=str(ledger),
            now=T,
        )
        self.assertEqual(report["reason"], sb.REASON_OK)

    # ---- UTC skew fails closed ------------------------------------------

    def test_utc_skew_fails_closed(self):
        """A claimed observation time 200 s away from the trusted host
        instant fails closed with UTC_SKEW (tolerance 120 s). Skew comes
        from trusted host instants, never from a UTC timezone offset.
        """
        skewed = T + timedelta(seconds=200)  # 200 s ahead of the host instant
        report = sb.shadow_pre_flight(
            provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
            key=DEFAULT_KEY,
            policy=MINIMAL_POLICY,
            now=skewed,
        )
        self.assertEqual(report["reason"], sb.REASON_UTC_SKEW)
        self.assertEqual(report["utc_skew_seconds"], 200)

    def test_utc_skew_within_tolerance_ok(self):
        """Now within 120s tolerance should not trigger UTC_SKEW."""
        report = sb.shadow_pre_flight(
            provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
            key=DEFAULT_KEY,
            policy=MINIMAL_POLICY,
            now=T,  # zero skew against the pinned trusted host instant
        )
        self.assertEqual(report["reason"], sb.REASON_OK)
        self.assertEqual(report["utc_skew_seconds"], 0)

    def test_non_utc_offset_same_instant_is_not_skew(self):
        """A non-UTC timezone offset that names the very same instant as the
        trusted host clock is NOT skew: skew is measured between instants,
        never from the UTC offset itself."""
        shifted = T.astimezone(timezone(timedelta(hours=-3)))
        self.assertNotEqual(shifted.utcoffset().total_seconds(), 0)
        report = sb.shadow_pre_flight(
            provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
            key=DEFAULT_KEY,
            policy=MINIMAL_POLICY,
            now=shifted,
        )
        self.assertEqual(report["reason"], sb.REASON_OK)

    def test_naive_now_fails_closed_utc_skew(self):
        """A naive (unverifiable) observation time fails closed with UTC_SKEW."""
        report = sb.shadow_pre_flight(
            provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
            key=DEFAULT_KEY,
            policy=MINIMAL_POLICY,
            now=datetime(2026, 10, 14, 18, 0, 0),
        )
        self.assertEqual(report["reason"], sb.REASON_UTC_SKEW)

    def test_bridge_never_runs_incident_pipeline(self):
        """Strictly observe-only: incident_pipeline.run_pipeline() must stay
        unreachable from the bridge, even with a healthy ledger. It would
        write ledger rows and relative-path outbox/inbox databases."""
        ledger = self._make_ledger()
        with mock.patch.object(sb.incident_pipeline, "run_pipeline",
                               side_effect=AssertionError("run_pipeline reached")):
            report = sb.shadow_pre_flight(
                provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
                key=DEFAULT_KEY,
                policy=MINIMAL_POLICY,
                ledger_path=str(ledger),
                now=T,
            )
        self.assertEqual(report["reason"], sb.REASON_OK)
        self.assertTrue(report["read_only"])
        self.assertFalse(report["execution_started"])
        # No relative-path state may appear in the working tree
        for name in ("shadow_proposals", "shadow_inbox", "shadow_reservations",
                     "shadow_notifications"):
            self.assertFalse(self.root.joinpath(name).exists())
            self.assertFalse(Path(name).exists())

    # ---- Missing heartbeat fails closed -----------------------------------

    def test_missing_observer_degraded(self):
        """Missing observer -> REASON_MISSING_HEARTBEAT."""
        report = sb.shadow_pre_flight(
            provider=provider_from_mapping({WIN: beat(WIN)}),
            key=DEFAULT_KEY,
            policy=MINIMAL_POLICY,
            now=T,
        )
        self.assertEqual(report["reason"], sb.REASON_MISSING_HEARTBEAT)
        self.assertEqual(report["heartbeat"], LINUX)
        self.assertEqual(report["heartbeat_status"], "MISSING")

    # ---- Stale heartbeat fails closed -------------------------------------

    def test_stale_heartbeat_fails_closed(self):
        """Stale heartbeat -> REASON_STALE_HEARTBEAT."""
        stale_at = T - timedelta(seconds=ss.STALE_WINDOW_SECONDS + 1)
        report = sb.shadow_pre_flight(
            provider=provider_from_mapping({
                WIN: beat(WIN, at=stale_at),
                LINUX: beat(LINUX),
            }),
            key=DEFAULT_KEY,
            policy=MINIMAL_POLICY,
            now=T,
        )
        self.assertEqual(report["reason"], sb.REASON_STALE_HEARTBEAT)
        self.assertEqual(report["heartbeat"], WIN)
        self.assertEqual(report["heartbeat_status"], "STALE")
        self.assertEqual(report["age_seconds"], ss.STALE_WINDOW_SECONDS + 1)

    # ---- Future heartbeat fails closed ------------------------------------

    def test_future_heartbeat_fails_closed(self):
        """Future heartbeat -> REASON_FUTURE_HEARTBEAT."""
        future_at = T + timedelta(seconds=1)
        report = sb.shadow_pre_flight(
            provider=provider_from_mapping({
                WIN: beat(WIN, at=future_at),
                LINUX: beat(LINUX),
            }),
            key=DEFAULT_KEY,
            policy=MINIMAL_POLICY,
            now=T,
        )
        self.assertEqual(report["reason"], sb.REASON_FUTURE_HEARTBEAT)

    # ---- Disabled policy fails closed -------------------------------------

    def test_disabled_policy_fails_closed(self):
        """Disabled policy -> REASON_DISABLED_POLICY."""
        bad_policy = {"schema": ss.KILL_SWITCH_SCHEMA, "enabled": False, "kill_switch": False}
        # This is a minimal bad policy; validate_policy will reject it because
        # it's missing required fields (mode, auto_approve, etc.).
        report = sb.shadow_pre_flight(
            provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
            key=DEFAULT_KEY,
            policy=bad_policy,
            now=T,
        )
        self.assertEqual(report["reason"], sb.REASON_DISABLED_POLICY)

    # ---- Kill switch engaged fails closed ---------------------------------

    def test_kill_switch_pauses(self):
        """Kill switch engaged -> REASON_KILL_SWITCH."""
        # Use a full valid autonomy policy (schema = atlas.autonomy.policy.v2)
        # with kill_switch=True.  The bridge inlines the kill-switch decision,
        # so this tests that the engaged path is taken correctly.
        paused_policy = {
            "schema": "atlas.autonomy.policy.v2",
            "mode": "observe_only",
            "enabled": True,
            "kill_switch": True,
            "auto_approve": False,
            "auto_write": False,
            "allowed_actions": ["diagnose_readonly"],
            "origins": ["x99_worker"],
            "kinds": ["worker_stale"],
            "limits": {"daily_readonly_missions": 5, "max_concurrent": 2, "max_total_cost_usd": 0},
        }
        report = sb.shadow_pre_flight(
            provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
            key=DEFAULT_KEY,
            policy=paused_policy,
            now=T,
        )
        self.assertEqual(report["reason"], sb.REASON_KILL_SWITCH)
        self.assertEqual(report["kill_switch"]["decision"], "PAUSED")

    # ---- Unknown WAL status fails closed ----------------------------------

    def test_wal_status_unavailable_fails_closed(self):
        """Non-existent/SQLite error on ledger -> REASON_UNKNOWN_WAL_STATUS."""
        report = sb.shadow_pre_flight(
            provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
            key=DEFAULT_KEY,
            policy=MINIMAL_POLICY,
            ledger_path="/nonexistent/path/db.dat",  # not a sqlite file
            now=T,
        )
        # Configured but missing ledger is an unknown WAL status, never OK
        self.assertEqual(report["reason"], sb.REASON_UNKNOWN_WAL_STATUS)

    # ---- Missing cryptographic key fails closed ---------------------------

    def test_missing_key_fails_closed(self):
        """Short key -> REASON_MISSING_KEY."""
        report = sb.shadow_pre_flight(
            provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
            key=b"short",  # not 32 bytes
            policy=MINIMAL_POLICY,
            now=T,
        )
        self.assertEqual(report["reason"], sb.REASON_MISSING_KEY)

    # ---- quick_check convenience                                           ----

    def test_quick_check_ok(self):
        """quick_check with valid inputs -> REASON_OK."""
        # Use a fixed now so the stale-check is deterministic.
        now = T
        report = sb.quick_check(
            provider={WIN: beat(WIN, at=now), LINUX: beat(LINUX, at=now)},
            key=DEFAULT_KEY,
            policy=MINIMAL_POLICY,
            now=now,
        )
        self.assertEqual(report["reason"], sb.REASON_OK)

    def test_quick_check_missing_key(self):
        """quick_check with short key -> REASON_MISSING_KEY."""
        report = sb.quick_check(
            provider={WIN: beat(WIN), LINUX: beat(LINUX)},
            key=b"short",
            policy=MINIMAL_POLICY,
        )
        self.assertEqual(report["reason"], sb.REASON_MISSING_KEY)


class ShadowBridgeMalformedHeartbeatTests(unittest.TestCase):
    """Audit M6: HEALTHY heartbeat double-check must fail closed."""

    def setUp(self):
        self.temp = __import__('tempfile').TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        host_seam = mock.patch.object(sb, "trusted_host_now", lambda: T)
        host_seam.start()
        self.addCleanup(host_seam.stop)

    def _healthy_report(self):
        import copy
        provider = provider_from_mapping({WIN: beat(WIN, at=T), LINUX: beat(LINUX, at=T)})
        observe_policy = {"schema": ss.KILL_SWITCH_SCHEMA, "enabled": True, "kill_switch": False}
        base = ss.observe(provider=provider, policy=observe_policy, ledger_path=None,
                          now=T, stale_window_seconds=ss.STALE_WINDOW_SECONDS)
        report = copy.deepcopy(base)
        # Ensure HEALTHY to exercise the double-check branch.
        for obs in (WIN, LINUX):
            report["heartbeats"][obs]["status"] = "HEALTHY"
        return report

    def test_mocked_observe_empty_observed_at_fails_closed(self):
        bad = self._healthy_report()
        bad["heartbeats"][WIN]["observed_at"] = ""
        with mock.patch.object(sb.ss, "observe", return_value=bad):
            report = sb.shadow_pre_flight(
                provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
                key=DEFAULT_KEY, policy=MINIMAL_POLICY, now=T)
        self.assertEqual(report["reason"], sb.REASON_MALFORMED_HEARTBEAT)
        self.assertEqual(report["heartbeat"], WIN)
        self.assertEqual(report["heartbeat_status"], "HEALTHY")

    def test_mocked_observe_malformed_observed_at_fails_closed(self):
        bad = self._healthy_report()
        bad["heartbeats"][WIN]["observed_at"] = "not-a-timestamp"
        with mock.patch.object(sb.ss, "observe", return_value=bad):
            report = sb.shadow_pre_flight(
                provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
                key=DEFAULT_KEY, policy=MINIMAL_POLICY, now=T)
        self.assertEqual(report["reason"], sb.REASON_MALFORMED_HEARTBEAT)

    def test_mocked_observe_naive_observed_at_fails_closed(self):
        bad = self._healthy_report()
        bad["heartbeats"][WIN]["observed_at"] = T.replace(tzinfo=None).isoformat()
        with mock.patch.object(sb.ss, "observe", return_value=bad):
            report = sb.shadow_pre_flight(
                provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
                key=DEFAULT_KEY, policy=MINIMAL_POLICY, now=T)
        self.assertEqual(report["reason"], sb.REASON_MALFORMED_HEARTBEAT)

    def test_mocked_observe_none_observed_at_fails_closed(self):
        bad = self._healthy_report()
        bad["heartbeats"][WIN]["observed_at"] = None
        with mock.patch.object(sb.ss, "observe", return_value=bad):
            report = sb.shadow_pre_flight(
                provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
                key=DEFAULT_KEY, policy=MINIMAL_POLICY, now=T)
        self.assertEqual(report["reason"], sb.REASON_MALFORMED_HEARTBEAT)

    def test_mocked_observe_malformed_still_future_works(self):
        # ensure future classification preserved when observed_at is valid aware future
        bad = self._healthy_report()
        bad["heartbeats"][WIN]["observed_at"] = (T + timedelta(seconds=5)).isoformat()
        with mock.patch.object(sb.ss, "observe", return_value=bad):
            report = sb.shadow_pre_flight(
                provider=provider_from_mapping({WIN: beat(WIN), LINUX: beat(LINUX)}),
                key=DEFAULT_KEY, policy=MINIMAL_POLICY, now=T)
        self.assertEqual(report["reason"], sb.REASON_FUTURE_HEARTBEAT)


if __name__ == "__main__":
    unittest.main()