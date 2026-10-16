"""Adversarial regression tests for CP13 qa_security.

Independent security-focused probes that catch:
  - replay data loss / data destruction (ledger, inbox, reservations,
    notifications and outbox projections must survive replay)
  - unauthorized side effects (files created outside the declared
    temp roots) and unsafe relative path components
  - unmeasured clock drift (UTC skew detection)
  - missing host (absent heartbeat observer, missing ledger)
  - future timestamps (shadow heartbeats and signed-envelope TTL)
  - HMAC tampering (forged signature, tampered payload, wrong key,
    same-id-different-payload overwrite attempts)
  - unauthorized actions (forbidden kind, forbidden action, kill switch)
  - dispatch: pipeline must never dispatch, execute or send; transport
    stays unreachable without explicit enablement
  - replay idempotency (duplicate envelopes, repeated runs)

This module is self-contained: helpers are defined locally and constants are
imported from the runtime modules under test (system_supervision), never from
other test modules. Uses only temp directories, injected probes and mocks; no
external endpoints, no network, no OS execution.
"""

import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from pathlib import Path

from atlas_e2e_fixture import run_fixture, _TEST_KEY
from incident_pipeline import ingest_event
from atlas_shadow_bridge import (
    shadow_pre_flight, check_utc_skew,
    REASON_MISSING_HEARTBEAT, REASON_FUTURE_HEARTBEAT, REASON_STALE_HEARTBEAT,
    REASON_UTC_SKEW, REASON_OK, REASON_KILL_SWITCH, REASON_UNKNOWN_WAL_STATUS,
)
import system_supervision as ss
from signed_event_transport import sign, TTL_SECONDS
from autonomy_policy_gate import SCHEMA
from durable_incidents import list_open
from notification_outbox import dispatch_one

NOW = datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc)
FINDINGS = {"worker_stale": {"summary": "heartbeat lagging"}}
POLICY = {
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
KILL_SWITCH_POLICY = dict(POLICY, kill_switch=True)


def provider_from_mapping(mapping):
    """Callable provider seam for ss.observe(): observer -> record or None."""
    def provide(observer):
        return mapping.get(observer)
    return provide


def beat(observer, at, seq=1):
    """A well-formed supervisor heartbeat record (matches ss._BEAT_FIELDS)."""
    return {"schema": ss.HEARTBEAT_SCHEMA, "observer": observer,
            "detector": observer + ".probe", "sequence": seq,
            "observed_at": at.isoformat()}


def healthy_provider(at=NOW):
    return provider_from_mapping({
        obs: beat(obs, at) for obs in ss.OBSERVERS
    })


class TempStateMixin:
    """Shared isolated temp layout for full-fixture adversarial probes."""

    def make_state(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        state = {
            "ledger_db": root / "ledger.db",
            "outbox": root / "proposals",
            "inbox_db": root / "inbox.db",
            "reservations_db": root / "reservations.db",
            "notifications_db": root / "notifications.db",
        }
        for p in state.values():
            p.parent.mkdir(parents=True, exist_ok=True)
        return state

    def run_full(self, state, *, policy=None, findings=None, now=NOW,
                 probe=None):
        data = findings if findings is not None else FINDINGS
        return run_fixture(
            key=_TEST_KEY, policy=policy if policy is not None else POLICY,
            findings=data, probe=probe if probe is not None else
            (lambda: json.loads(json.dumps(data))), now=now,
            ledger_db=state["ledger_db"], proposal_outbox=state["outbox"],
            inbox_db=state["inbox_db"], reservations_db=state["reservations_db"],
            notifications_db=state["notifications_db"],
        )

    @staticmethod
    def count(db, table):
        if not db.exists():
            return 0
        con = sqlite3.connect(str(db))
        try:
            return con.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
        finally:
            con.close()


class TestReplayDataLoss(unittest.TestCase, TempStateMixin):
    """Replay must not cause data loss or destruction from prior runs."""

    def setUp(self):
        self.state = self.make_state()

    def test_replay_no_data_loss_on_repeated_runs(self):
        """Replay must not delete or lose events from the first run."""
        first = self.run_full(self.state)
        second = self.run_full(self.state, now=NOW + timedelta(minutes=5))
        self.assertGreaterEqual(first["totals"]["events"], 1)
        self.assertGreaterEqual(second["totals"]["events"],
                                first["totals"]["events"])

    def test_replay_preserves_inbox_count(self):
        """Replay must not reduce inbox rows below the first-run baseline."""
        self.run_full(self.state)
        before = self.count(self.state["inbox_db"], "inbox")
        self.run_full(self.state, now=NOW + timedelta(minutes=5))
        after = self.count(self.state["inbox_db"], "inbox")
        self.assertEqual(after, before, "Replay reduced inbox count (data loss)")

    def test_replay_preserves_every_durable_count(self):
        """Ledger, inbox, reservations and notifications survive replay."""
        self.run_full(self.state)
        baselines = {
            ("inbox_db", "inbox"): self.count(self.state["inbox_db"], "inbox"),
            ("reservations_db", "reservations"):
                self.count(self.state["reservations_db"], "reservations"),
            ("notifications_db", "notifications"):
                self.count(self.state["notifications_db"], "notifications"),
        }
        self.assertEqual(len(list_open(self.state["ledger_db"], "x99_worker")), 1)
        self.run_full(self.state, now=NOW + timedelta(minutes=7))
        for (key, table), expected in baselines.items():
            self.assertEqual(self.count(self.state[key], table), expected,
                             "Replay destroyed rows in " + table)
        self.assertEqual(len(list_open(self.state["ledger_db"], "x99_worker")),
                         1, "Replay destroyed the open ledger incident")

    def test_outbox_projection_rebuilt_after_deletion(self):
        """Outbox JSON is a rebuildable projection: deleting it must not
        destroy the durable ledger truth, and replay must restore it."""
        self.run_full(self.state)
        projections = list(self.state["outbox"].glob("*.json"))
        self.assertEqual(len(projections), 1)
        projections[0].unlink()
        result = self.run_full(self.state, now=NOW + timedelta(minutes=5))
        self.assertEqual(result["outbox_total"], 1)
        self.assertTrue(list(self.state["outbox"].glob("*.json")),
                        "Ledger truth did not rebuild the deleted projection")
        self.assertEqual(len(list_open(self.state["ledger_db"], "x99_worker")), 1)


class TestUnauthorizedSideEffects(unittest.TestCase, TempStateMixin):
    """No files may appear outside the declared temp roots; relative path
    components must resolve inside the declared root."""

    def test_no_files_created_outside_declared_temp_roots(self):
        """A full run must not create or delete any file in the working
        directory tree (the repository), only under the temp roots."""
        cwd = Path.cwd()

        def snapshot():
            files = set()
            for dirpath, dirnames, filenames in os.walk(cwd):
                dirnames[:] = [d for d in dirnames if d != "__pycache__"]
                for name in filenames:
                    files.add(os.path.relpath(os.path.join(dirpath, name), cwd))
            return files

        before = snapshot()
        state = self.make_state()
        self.run_full(state)
        after = snapshot()
        self.assertEqual(after, before,
                         "Fixture created/deleted files outside temp roots")

    def test_relative_path_components_stay_confined(self):
        """DB paths containing '..' components must resolve inside the
        declared root; no artifact may escape to the base directory."""
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        root = base / "in"
        root.mkdir()
        state = {
            "ledger_db": root / "a" / ".." / "ledger.db",
            "outbox": root / "b" / ".." / "proposals",
            "inbox_db": root / "c" / ".." / "inbox.db",
            "reservations_db": root / "d" / ".." / "reservations.db",
            "notifications_db": root / "e" / ".." / "notifications.db",
        }
        result = self.run_full(state)
        self.assertEqual(result["status"], "pipeline_complete")
        escaped = []
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(root.resolve()):
                escaped.append(str(resolved))
        self.assertEqual(escaped, [],
                         "Artifacts escaped the declared root via '..': %r"
                         % escaped)
        # Base directory must contain only the declared root.
        self.assertEqual(sorted(p.name for p in base.iterdir()), ["in"])


class TestClockDriftNoMeasurement(unittest.TestCase):
    """UTC skew must be actually measured, not assumed.

    The reference (trusted host) clock is injected rather than assumed to
    equal the fixed NOW constant, which is a historical fixture instant and not
    the current wall clock.  Only the underlying UTC instant determines skew;
    a UTC timezone offset is never treated as skew evidence.
    """

    def setUp(self):
        self._host_patch = patch(
            "atlas_shadow_bridge.trusted_host_now", return_value=NOW)
        self._host_patch.start()
        self.addCleanup(self._host_patch.stop)

    def test_utc_skew_detection_with_real_skew(self):
        """An instant 10 hours away in real time must fail skew, regardless of
        any UTC offset label."""
        real_skew = NOW + timedelta(hours=10)
        ok, reason = check_utc_skew(real_skew, tolerance_seconds=120)
        self.assertFalse(ok, "10-hour real-time skew should fail skew check")
        self.assertEqual(reason, "UTC_SKEW")

    def test_no_false_negative_on_small_skew(self):
        """An instant 1 minute away (within 120s tolerance) passes."""
        almost = NOW + timedelta(minutes=1)
        ok, reason = check_utc_skew(almost, tolerance_seconds=120)
        self.assertTrue(ok, "60-second real-time skew should pass")
        self.assertEqual(reason, "OK")

    def test_naive_timestamp_fails_closed(self):
        """A naive datetime (no tzinfo) must fail closed, never pass."""
        naive = datetime(2026, 10, 14, 18, 0)
        ok, reason = check_utc_skew(naive, tolerance_seconds=120)
        self.assertFalse(ok, "naive timestamp must fail closed")
        self.assertEqual(reason, "UTC_SKEW")

    def test_clock_offset_equivalent_instant_passes(self):
        """Same underlying instant expressed with a non-UTC offset passes:
        UTC offset is NOT clock skew."""
        # NOW in UTC is the same instant as 04:00 the next day at +10:00.
        equivalent = datetime(2026, 10, 15, 4, 0,
                              tzinfo=timezone(timedelta(hours=10)))
        # Verify it is exactly the same instant as the reference.
        self.assertEqual(equivalent.astimezone(timezone.utc), NOW)
        ok, reason = check_utc_skew(equivalent, tolerance_seconds=120)
        self.assertTrue(ok, "equivalent instant with +10 offset must pass")
        self.assertEqual(reason, "OK")

    def test_clock_offset_same_wall_clock_is_real_skew(self):
        """Same wall-clock label under different offsets is a real instant
        difference and must be rejected as skew, not excused by the offset."""
        # 18:00 at +10:00 is 10 hours earlier in UTC than the reference.
        same_wall_different_offset = datetime(
            2026, 10, 14, 18, 0, tzinfo=timezone(timedelta(hours=10)))
        ok, reason = check_utc_skew(
            same_wall_different_offset, tolerance_seconds=120)
        self.assertFalse(ok, "10-hour instant gap must fail")
        self.assertEqual(reason, "UTC_SKEW")

    def test_utc_skew_uses_injected_reference_not_offset(self):
        """Direct skew with an explicit-equivalent host reference clock shows
        offset is not used as skew evidence."""
        from atlas_shadow_bridge import utc_skew_seconds

        # An instant 30 seconds away passes under the injected reference.
        instant = NOW + timedelta(seconds=30)
        host = NOW
        skew = utc_skew_seconds(instant, host_now=host)
        self.assertIsNotNone(skew)
        self.assertLessEqual(skew, 120.0)
        # Offset representation of the same instant does not change skew.
        skew2 = utc_skew_seconds(
            instant.astimezone(timezone(timedelta(hours=3))), host_now=host)
        self.assertAlmostEqual(skew, skew2, places=6)


class TestMissingFutureHeartbeats(unittest.TestCase, TempStateMixin):
    """Missing host, stale and future heartbeat detection in the shadow
    bridge. All beats are well-formed supervisor records."""

    def setUp(self):
        self._host_patch = patch(
            "atlas_shadow_bridge.trusted_host_now", return_value=NOW)
        self._host_patch.start()
        self.addCleanup(self._host_patch.stop)
        return super().setUp()

    def test_shadow_missing_heartbeat(self):
        """Observer absent -> REASON_MISSING_HEARTBEAT, fail closed."""
        report = shadow_pre_flight(
            provider=provider_from_mapping({"windows_worker_observer": None}),
            key=_TEST_KEY, policy=POLICY, now=NOW)
        self.assertEqual(report["reason"], "MISSING_HEARTBEAT")
        self.assertEqual(report["heartbeat"], "windows_worker_observer")
        self.assertEqual(report["heartbeat_status"], "MISSING")
        self.assertTrue(report["read_only"])
        self.assertFalse(report["execution_started"])
        self.assertFalse(report["messages_sent"])

    def test_shadow_future_heartbeat(self):
        """A future observed_at must be rejected fail-closed."""
        provider = provider_from_mapping({
            "windows_worker_observer":
                beat("windows_worker_observer", NOW + timedelta(seconds=1)),
            "linux_systemd_observer":
                beat("linux_systemd_observer", NOW),
        })
        report = shadow_pre_flight(
            provider=provider, key=_TEST_KEY, policy=POLICY, now=NOW)
        self.assertEqual(report["reason"], "FUTURE_HEARTBEAT")
        self.assertTrue(report["read_only"])
        self.assertFalse(report["execution_started"])
        self.assertFalse(report["messages_sent"])
        self.assertFalse(report["services_restarted"])

    def test_shadow_stale_heartbeat(self):
        """observed_at older than the stale window -> REASON_STALE_HEARTBEAT."""
        stale_at = NOW - timedelta(seconds=ss.STALE_WINDOW_SECONDS + 1)
        provider = provider_from_mapping({
            "windows_worker_observer":
                beat("windows_worker_observer", stale_at),
            "linux_systemd_observer": beat("linux_systemd_observer", NOW),
        })
        report = shadow_pre_flight(
            provider=provider, key=_TEST_KEY, policy=POLICY, now=NOW)
        self.assertEqual(report["reason"], "STALE_HEARTBEAT")
        self.assertEqual(report["heartbeat"], "windows_worker_observer")
        self.assertEqual(report["heartbeat_status"], "STALE")
        self.assertEqual(report["age_seconds"], ss.STALE_WINDOW_SECONDS + 1)
        self.assertFalse(report["execution_started"])

    def test_shadow_missing_ledger_fails_closed(self):
        """A configured-but-missing ledger host -> UNKNOWN_WAL_STATUS."""
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        missing = Path(temp.name) / "does_not_exist.db"
        report = shadow_pre_flight(
            provider=healthy_provider(), key=_TEST_KEY, policy=POLICY,
            ledger_path=str(missing), now=NOW)
        self.assertEqual(report["reason"], "UNKNOWN_WAL_STATUS")
        self.assertEqual(report["wal_status"], "missing_ledger")
        self.assertFalse(report["execution_started"])
        self.assertFalse(report["messages_sent"])


class TestFutureTimestamps(unittest.TestCase, TempStateMixin):
    """Signed envelopes with future or stale issued_at must be rejected."""

    def setUp(self):
        self.state = self.make_state()
        self.run_full(self.state)
        self.proposal = json.loads(
            next(self.state["outbox"].glob("*.json")).read_text(
                encoding="utf-8"))

    def test_future_issued_envelope_rejected(self):
        """issued_at more than TTL ahead of receive time -> rejected."""
        envelope = sign(self.proposal, key=_TEST_KEY, origin="x99_worker",
                        now=NOW + timedelta(seconds=TTL_SECONDS + 60))
        with self.assertRaises(PermissionError):
            ingest_event(envelope, key=_TEST_KEY, policy=POLICY,
                         inbox_db=self.state["inbox_db"],
                         reservations_db=self.state["reservations_db"],
                         notifications_db=self.state["notifications_db"],
                         now=NOW)

    def test_stale_issued_envelope_rejected(self):
        """issued_at more than TTL behind receive time -> rejected."""
        envelope = sign(self.proposal, key=_TEST_KEY, origin="x99_worker",
                        now=NOW)
        with self.assertRaises(PermissionError):
            ingest_event(envelope, key=_TEST_KEY, policy=POLICY,
                         inbox_db=self.state["inbox_db"],
                         reservations_db=self.state["reservations_db"],
                         notifications_db=self.state["notifications_db"],
                         now=NOW + timedelta(seconds=TTL_SECONDS + 60))


class TestHMACForgedMessages(unittest.TestCase, TempStateMixin):
    """Forged or tampered HMAC envelopes must be rejected with no state
    change (no inbox insert, no reservation, no notification)."""

    def setUp(self):
        self.state = self.make_state()
        self.baseline = self.run_full(self.state)
        self.proposal = json.loads(
            next(self.state["outbox"].glob("*.json")).read_text(
                encoding="utf-8"))

    def snapshots(self):
        return (self.count(self.state["inbox_db"], "inbox"),
                self.count(self.state["reservations_db"], "reservations"),
                self.count(self.state["notifications_db"], "notifications"))

    def ingest(self, envelope, now=NOW):
        return ingest_event(envelope, key=_TEST_KEY, policy=POLICY,
                            inbox_db=self.state["inbox_db"],
                            reservations_db=self.state["reservations_db"],
                            notifications_db=self.state["notifications_db"],
                            now=now)

    def test_forged_signature_rejected_no_side_effects(self):
        """Zeroed HMAC: rejected, no state change."""
        before = self.snapshots()
        forged = sign(self.proposal, key=_TEST_KEY, origin="x99_worker",
                      now=NOW + timedelta(minutes=1))
        forged["signature"] = "0" * 64
        with self.assertRaises(PermissionError):
            self.ingest(forged, now=NOW + timedelta(minutes=1))
        self.assertEqual(self.snapshots(), before,
                         "Forged HMAC caused a state change")

    def test_tampered_payload_rejected_no_side_effects(self):
        """Proposal mutated after signing: signature no longer covers the
        body, so the receiver must reject it."""
        before = self.snapshots()
        envelope = sign(self.proposal, key=_TEST_KEY, origin="x99_worker",
                        now=NOW + timedelta(minutes=1))
        envelope["proposal"] = dict(envelope["proposal"],
                                    summary="tampered by adversary")
        with self.assertRaises(PermissionError):
            self.ingest(envelope, now=NOW + timedelta(minutes=1))
        self.assertEqual(self.snapshots(), before,
                         "Tampered payload caused a state change")

    def test_wrong_key_rejected_no_side_effects(self):
        """Envelope signed with a different key: rejected."""
        before = self.snapshots()
        envelope = sign(self.proposal, key=bytes([1] * 32),
                        origin="x99_worker", now=NOW + timedelta(minutes=1))
        with self.assertRaises(PermissionError):
            self.ingest(envelope, now=NOW + timedelta(minutes=1))
        self.assertEqual(self.snapshots(), before,
                         "Wrong-key envelope caused a state change")

    def test_same_id_different_payload_rejected(self):
        """A validly re-signed envelope reusing an accepted incident id with
        a different payload must not overwrite durable inbox truth."""
        before = self.snapshots()
        changed = dict(self.proposal, summary="different content, same id")
        envelope = sign(changed, key=_TEST_KEY, origin="x99_worker",
                        now=NOW + timedelta(minutes=1))
        with self.assertRaises(PermissionError):
            self.ingest(envelope, now=NOW + timedelta(minutes=1))
        self.assertEqual(self.snapshots(), before,
                         "Same-id different payload destroyed inbox truth")


class TestUnauthorizedAction(unittest.TestCase, TempStateMixin):
    """Unauthorized actions must be denied or fail closed."""

    def setUp(self):
        self.state = self.make_state()
        self._host_patch = patch(
            "atlas_shadow_bridge.trusted_host_now", return_value=NOW)
        self._host_patch.start()
        self.addCleanup(self._host_patch.stop)

    def test_forbidden_kind_no_mission(self):
        """A finding kind outside policy.kinds -> DENIED, no mission,
        no notification."""
        findings = {"worker_duplicate": {"summary": "two workers"}}
        result = self.run_full(
            self.state,
            policy=dict(POLICY, kinds=["worker_stale"]),
            findings=findings)
        event = result["events"][0]
        self.assertEqual(event["decision"], "DENIED")
        self.assertEqual(event["notification"], "skipped")
        self.assertEqual(result["totals"]["missions_reserved"], 0)
        self.assertEqual(result["totals"]["notifications_queued"], 0)

    def test_forbidden_action_fails_closed_before_observation(self):
        """allowed_actions outside the gate: PermissionError raised before
        the probe observes anything (fail closed, no partial state)."""
        for forbidden in (["diagnose_readonly", "unauthorized_action"],
                          ["unauthorized_action_only"]):
            with self.subTest(forbidden=forbidden):
                calls = []

                def probe():
                    calls.append(1)
                    return dict(FINDINGS)

                with self.assertRaises(PermissionError):
                    self.run_full(self.state, probe=probe,
                                  policy=dict(POLICY,
                                              allowed_actions=forbidden))
                self.assertEqual(calls, [],
                                 "Forbidden action observed before rejection")

    def test_kill_switch_denies_mission_and_notification(self):
        """Kill switch engaged: PAUSED, no reservation, no notification."""
        result = self.run_full(self.state, policy=KILL_SWITCH_POLICY)
        event = result["events"][0]
        self.assertEqual(event["decision"], "PAUSED")
        self.assertEqual(event["notification"], "skipped")
        self.assertEqual(result["totals"]["missions_reserved"], 0)
        self.assertEqual(result["totals"]["notifications_queued"], 0)
        self.assertEqual(result["kill_switch_decision"], "PAUSED")

    def test_shadow_kill_switch_fails_closed(self):
        """Shadow pre-flight with kill switch: REASON_KILL_SWITCH."""
        report = shadow_pre_flight(
            provider=healthy_provider(), key=_TEST_KEY,
            policy=KILL_SWITCH_POLICY, now=NOW)
        self.assertEqual(report["reason"], "KILL_SWITCH")
        self.assertEqual(report["kill_switch"]["decision"], "PAUSED")
        self.assertFalse(report["execution_started"])
        self.assertFalse(report["messages_sent"])


class TestDuplicateNotifications(unittest.TestCase, TempStateMixin):
    """Replay must not create duplicate notifications."""

    def test_no_duplicate_notifications_on_replay(self):
        state = self.make_state()
        first = self.run_full(state)
        self.assertEqual(first["totals"]["notifications_queued"], 1)
        second = self.run_full(state, now=NOW + timedelta(minutes=5))
        self.assertEqual(second["totals"]["notifications_queued"], 0,
                         "Second replay created duplicate notification")
        self.assertEqual(second["totals"]["notifications_existing"], 1)


class TestReplayIdempotency(unittest.TestCase, TempStateMixin):
    """Duplicate/replayed envelopes are idempotent at every stage."""

    def test_replayed_envelope_is_idempotent(self):
        state = self.make_state()
        self.run_full(state)
        proposal = json.loads(
            next(state["outbox"].glob("*.json")).read_text(encoding="utf-8"))
        replay_at = NOW + timedelta(minutes=1)
        envelope = sign(proposal, key=_TEST_KEY, origin="x99_worker",
                        now=replay_at)
        result = ingest_event(envelope, key=_TEST_KEY, policy=POLICY,
                              inbox_db=state["inbox_db"],
                              reservations_db=state["reservations_db"],
                              notifications_db=state["notifications_db"],
                              now=replay_at)
        self.assertEqual(result["receiver"], "duplicate")
        self.assertEqual(result["reservation"], "ALREADY_RESERVED")
        self.assertEqual(result["notification"], "already_queued")
        self.assertFalse(result["execution_started"])
        self.assertFalse(result["dispatch_performed"])
        self.assertEqual(result["messages_sent"], 0)
        self.assertEqual(self.count(state["inbox_db"], "inbox"), 1)
        self.assertEqual(self.count(state["reservations_db"], "reservations"), 1)
        self.assertEqual(self.count(state["notifications_db"], "notifications"), 1)


class TestNoDispatch(unittest.TestCase, TempStateMixin):
    """The pipeline must never dispatch, execute or send; the transport
    stays unreachable without explicit enablement."""

    def test_full_run_reports_no_execution_and_only_pending(self):
        state = self.make_state()
        result = self.run_full(state)
        self.assertFalse(result["execution_started"])
        self.assertFalse(result["dispatch_performed"])
        self.assertEqual(result["messages_sent"], 0)
        con = sqlite3.connect(str(state["notifications_db"]))
        try:
            statuses = [r[0] for r in con.execute(
                "SELECT status FROM notifications").fetchall()]
        finally:
            con.close()
        self.assertEqual(statuses, ["pending"],
                         "Notification left the prepare-only pending state")

    def test_dispatch_unreachable_without_explicit_enablement(self):
        """dispatch_one refuses to send unless explicitly enabled."""
        state = self.make_state()
        self.run_full(state)
        with self.assertRaises(PermissionError):
            dispatch_one(db_path=state["notifications_db"], id="any",
                         sender=None, explicit_enabled=False)


if __name__ == "__main__":
    unittest.main()
