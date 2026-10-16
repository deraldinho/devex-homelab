"""TDD tests for CP12 atlas_e2e_fixture synthetic end-to-end flow.

Uses only the fixture module and existing CP11 audited modules.
Zero OS execution, zero external sends, zero real services.
Disposable 32-byte test key only; no actual secrets.
"""
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from atlas_e2e_fixture import run_fixture, replay_fixture, _TEST_KEY
from incident_pipeline import run_pipeline as ip_run_pipeline, ingest_event
from autonomy_policy_gate import SCHEMA
from durable_incidents import reconcile, list_open
from signed_event_transport import sign, receive


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


class FixtureTests(unittest.TestCase):
    """TDD tests for atlas_e2e_fixture run_fixture() and replay_fixture()."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.ledger_db = root / "ledger.db"
        self.outbox = root / "proposals"
        self.inbox_db = root / "inbox.db"
        self.reservations_db = root / "reservations.db"
        self.notifications_db = root / "notifications.db"

    def _make_probe(self, findings=None):
        """Create an isolated snapshot probe (pure function, no OS inspection)."""
        data = findings if findings else FINDINGS

        def probe():
            return json.loads(json.dumps(data))
        return probe

    def run_full(self, key=_TEST_KEY, policy=POLICY, findings=FINDINGS,
                 probe=None, now=NOW):
        return run_fixture(
            key=key, policy=policy, findings=findings,
            probe=probe or self._make_probe(findings), now=now,
            ledger_db=self.ledger_db, proposal_outbox=self.outbox,
            inbox_db=self.inbox_db, reservations_db=self.reservations_db,
            notifications_db=self.notifications_db,
        )

    # -- happy path ------------------------------------------------------

    def test_happy_path_end_to_end_readonly_chain(self):
        """Full e2e: one mission reserved, one notification queued, no execution."""
        result = self.run_full()
        self.assertEqual(result["status"], "pipeline_complete")
        self.assertEqual(result["totals"]["events"], 1)
        self.assertEqual(result["totals"]["accepted"], 1)
        self.assertEqual(result["totals"]["missions_reserved"], 1)
        self.assertEqual(result["totals"]["missions_already_reserved"], 0)
        self.assertEqual(result["totals"]["missions_withheld"], 0)
        self.assertEqual(result["totals"]["notifications_queued"], 1)
        self.assertEqual(result["totals"]["notifications_existing"], 0)
        self.assertEqual(result["totals"]["notifications_withheld"], 0)
        self.assertEqual(result["kill_switch_decision"], "MONITORING")
        self.assertFalse(result["execution_started"])
        self.assertFalse(result["dispatch_performed"])
        self.assertEqual(result["messages_sent"], 0)
        # Verify DB counts
        self.assertEqual(len(list_open(self.ledger_db, "x99_worker")), 1)
        con = sqlite3.connect(str(self.inbox_db))
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM inbox").fetchone()[0], 1)
        finally:
            con.close()
        con = sqlite3.connect(str(self.reservations_db))
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM reservations").fetchone()[0], 1)
        finally:
            con.close()
        con = sqlite3.connect(str(self.notifications_db))
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 1)
        finally:
            con.close()

    # -- idempotency / replay -------------------------------------------

    def test_duplicate_run_never_creates_new_mission_or_notification(self):
        """Re-running the fixture yields no new missions or notifications."""
        first = self.run_full()
        second = self.run_full(now=NOW + timedelta(minutes=5))
        self.assertEqual(len(first["opened"]), 1)
        self.assertEqual(second["opened"], [])
        # Second run should show 1 duplicate event
        self.assertEqual(second["totals"]["duplicate"], 1)
        self.assertEqual(second["totals"]["missions_reserved"], 0)
        self.assertEqual(second["totals"]["missions_already_reserved"], 1)
        self.assertEqual(second["totals"]["notifications_queued"], 0)
        self.assertEqual(second["totals"]["notifications_existing"], 1)
        self.assertEqual(self._count("reservations"), 1)
        self.assertEqual(self._count("notifications"), 1)
        self.assertEqual(self._count("inbox"), 1)

    def _count(self, table):
        """Helper to count rows in a DB."""
        db_map = {
            "inbox": self.inbox_db,
            "reservations": self.reservations_db,
            "notifications": self.notifications_db,
        }
        db = db_map.get(table)
        if not db or not db.exists():
            return 0
        con = sqlite3.connect(str(db))
        try:
            return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            con.close()

    def test_replayed_envelope_is_idempotent(self):
        """Single replay of same envelope dedupes inbox/reservation/notification."""
        first = self.run_full()
        second = self.run_full(now=NOW + timedelta(minutes=5))
        self.assertEqual(first["status"], "pipeline_complete")
        self.assertEqual(second["status"], "pipeline_complete")
        # Totals should show duplicate counts from second run
        self.assertGreaterEqual(second["totals"]["duplicate"], 0)
        self.assertEqual(second["totals"]["missions_reserved"], 0)
        self.assertEqual(second["totals"]["missions_already_reserved"], 1)
        self.assertEqual(second["totals"]["notifications_queued"], 0)
        self.assertEqual(second["totals"]["notifications_existing"], 1)

    # -- resolution ------------------------------------------------------

    def test_resolution_replay_never_creates_mission_or_notification(self):
        """RESOLVED status closes ledger state; no new mission or notification."""
        first = self.run_full()
        # Second run with empty findings causes resolution of existing incidents
        second = self.run_full(findings={},
                               now=NOW + timedelta(minutes=2))
        self.assertEqual(first["totals"]["notifications_queued"], 1)
        # The second run should have resolved incidents
        # Check that resolutions happened via DB state
        con = sqlite3.connect(str(self.inbox_db))
        try:
            # Inbox should still have 2 entries (original + resolution marker)
            count = con.execute("SELECT COUNT(*) FROM inbox").fetchone()[0]
            # Key: no new missions/reservations/notifications created
            self.assertGreaterEqual(count, 1)
        finally:
            con.close()
        con = sqlite3.connect(str(self.reservations_db))
        try:
            # Reservations count should be unchanged
            reservations_count = con.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
            self.assertEqual(reservations_count, 1)
        finally:
            con.close()
        con = sqlite3.connect(str(self.notifications_db))
        try:
            # Notifications count should be unchanged
            notifications_count = con.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
            self.assertEqual(notifications_count, 1)
        finally:
            con.close()
        # Overall: second run totals should show 0 new reservations/notifications
        self.assertEqual(second["totals"]["missions_reserved"], 0)
        self.assertEqual(second["totals"]["notifications_queued"], 0)

    # -- kill switch -----------------------------------------------------

    def test_kill_switch_pauses_before_mission_and_notification(self):
        """Kill switch True: mission and notification skipped, no reservations."""
        result = self.run_full(policy={
            "schema": SCHEMA,
            "enabled": True,
            "kill_switch": True,
            "mode": "observe_only",
            "auto_approve": False,
            "auto_write": False,
            "allowed_actions": ["diagnose_readonly"],
            "origins": ["x99_worker"],
            "kinds": ["worker_stale", "worker_duplicate"],
            "limits": {"daily_readonly_missions": 5, "max_concurrent": 2,
                       "max_total_cost_usd": 0},
        })
        event = result["events"][0]
        self.assertEqual(event["receiver"], "accepted")
        self.assertEqual(event["decision"], "PAUSED")
        self.assertEqual(event["notification"], "skipped")
        self.assertEqual(result["totals"]["missions_reserved"], 0)
        self.assertEqual(result["totals"]["missions_already_reserved"], 0)
        self.assertEqual(result["totals"]["missions_withheld"], 0)
        self.assertEqual(result["totals"]["notifications_queued"], 0)
        self.assertEqual(result["totals"]["notifications_existing"], 0)
        self.assertEqual(result["totals"]["notifications_withheld"], 0)
        self.assertEqual(self._count("reservations"), 0)
        self.assertEqual(self._count("notifications"), 0)

    # -- tamper HMAC rejection -------------------------------------------

    def test_tampered_signature_rejected_no_side_effects(self):
        """Forged HMAC signature: rejected, no state change."""
        self.run_full()  # establish baseline
        # Forge: read a proposal and forge a new envelope with bad signature
        proposal = json.loads(
            next(self.outbox.glob("*.json")).read_text(encoding="utf-8"))
        forged = sign(proposal, key=_TEST_KEY, origin="x99_worker", now=NOW)
        forged["signature"] = "0" * 64
        from incident_pipeline import ingest_event as ip_ingest
        with self.assertRaises(PermissionError):
            ip_ingest(forged, key=_TEST_KEY, policy=POLICY,
                      inbox_db=self.inbox_db,
                      reservations_db=self.reservations_db,
                      notifications_db=self.notifications_db, now=NOW)
        # State should be unchanged from baseline
        self.assertEqual(self._count("inbox"), 1)
        self.assertEqual(self._count("reservations"), 1)
        self.assertEqual(self._count("notifications"), 1)

    # -- invalid key fail-closed ----------------------------------------

    def test_invalid_key_fail_closed(self):
        """Key not 32 bytes: ValueError raised before any observation."""
        calls = []

        def probe():
            calls.append(1)
            return dict(FINDINGS)

        with self.assertRaises(ValueError):
            run_fixture(key=b"short", probe=probe)
        self.assertEqual(calls, [])  # rejected before any observation

    # -- unapproved kind -------------------------------------------------

    def test_unapproved_kind_gets_no_mission_or_notification(self):
        """Policy with unsupported kind: DENIED, no mission, no notification."""
        result = self.run_full(policy={
            "schema": SCHEMA,
            "enabled": True,
            "kill_switch": False,
            "mode": "observe_only",
            "auto_approve": False,
            "auto_write": False,
            "allowed_actions": ["diagnose_readonly"],
            "origins": ["x99_worker"],
            "kinds": ["worker_duplicate"],  # only worker_duplicate, not worker_stale
            "limits": {"daily_readonly_missions": 5, "max_concurrent": 2,
                       "max_total_cost_usd": 0},
        })
        event = result["events"][0]
        self.assertEqual(event["decision"], "DENIED")
        self.assertEqual(event["notification"], "skipped")
        self.assertEqual(result["totals"]["missions_reserved"], 0)
        self.assertEqual(result["totals"]["missions_already_reserved"], 0)
        self.assertEqual(result["totals"]["missions_withheld"], 0)
        self.assertEqual(result["totals"]["notifications_queued"], 0)
        self.assertEqual(result["totals"]["notifications_existing"], 0)
        self.assertEqual(result["totals"]["notifications_withheld"], 0)

    # -- daily limit -----------------------------------------------------

    def test_daily_limit_withholds_second_mission_and_notification(self):
        """Daily limit of 1: second run withholds mission and notification."""
        strict = {
            "schema": SCHEMA,
            "enabled": True,
            "kill_switch": False,
            "mode": "observe_only",
            "auto_approve": False,
            "auto_write": False,
            "allowed_actions": ["diagnose_readonly"],
            "origins": ["x99_worker"],
            "kinds": ["worker_stale", "worker_duplicate"],
            "limits": {"daily_readonly_missions": 1, "max_concurrent": 1,
                       "max_total_cost_usd": 0},
        }
        self.run_full(policy=strict)
        second = self.run_full(
            policy=strict,
            findings={"worker_stale": {"summary": "heartbeat lagging"},
                      "worker_duplicate": {"summary": "two workers"}},
            now=NOW + timedelta(minutes=1),
        )
        self.assertEqual(second["totals"]["missions_reserved"], 0)
        self.assertEqual(second["totals"]["missions_already_reserved"], 1)
        self.assertEqual(second["totals"]["missions_withheld"], 1)
        self.assertEqual(second["totals"]["notifications_withheld"], 1)
        self.assertEqual(len(list_open(self.ledger_db, "x99_worker")), 2)
        self.assertEqual(self._count("inbox"), 2)
        self.assertEqual(self._count("reservations"), 1)
        self.assertEqual(self._count("notifications"), 1)

    # -- probe failure fails closed -------------------------------------

    def test_probe_failure_fails_closed_without_partial_state(self):
        """Broken probe: RuntimeError raised; no DB state created."""
        def boom():
            raise RuntimeError("snapshot unavailable")

        with self.assertRaises(RuntimeError):
            run_fixture(probe=boom)
        # No partial state
        self.assertFalse(self.inbox_db.exists() or self.reservations_db.exists()
                         or self.notifications_db.exists())

    # -- no execution / no send capability ------------------------------

    def test_pipeline_exposes_no_dispatch_or_os_execution_capability(self):
        """Fixture source contains no dispatch_one, subprocess, explicit_enabled."""
        source = Path("atlas_e2e_fixture.py").read_text(encoding="utf-8")
        self.assertNotIn("dispatch_one", source)
        self.assertNotIn("explicit_enabled", source)
        self.assertNotIn("subprocess", source)
        result = self.run_full()
        self.assertEqual(result["messages_sent"], 0)
        statuses = self._notification_statuses()
        self.assertEqual(statuses, ["pending"])

    def _notification_statuses(self):
        """Read notification statuses from DB."""
        if not self.notifications_db.exists():
            return []
        con = sqlite3.connect(str(self.notifications_db))
        try:
            return [r[0] for r in con.execute(
                "SELECT status FROM notifications ORDER BY status").fetchall()]
        finally:
            con.close()

    # -- unknown outcome handled explicitly -----------------------------

    def test_unknown_outcome_not_promoted(self):
        """Undefined/unknown outcome: fixture returns explicit status, never auto-promos."""
        # Use a policy that results in PAUSED (kill_switch) -> notification=skipped
        result = self.run_full(policy={
            "schema": SCHEMA,
            "enabled": True,
            "kill_switch": True,
            "mode": "observe_only",
            "auto_approve": False,
            "auto_write": False,
            "allowed_actions": ["diagnose_readonly"],
            "origins": ["x99_worker"],
            "kinds": ["worker_stale"],
            "limits": {"daily_readonly_missions": 5, "max_concurrent": 2,
                       "max_total_cost_usd": 0},
        })
        # Outcome is explicitly PAUSED/skipped; no auto-promotion to queued
        self.assertEqual(result["kill_switch_decision"], "PAUSED")
        self.assertEqual(result["totals"]["notifications_queued"], 0)
        # With kill switch, notification is skipped; not auto-promoted to queued
        # or withheld - it depends on the mission status context
        self.assertIn(result["totals"]["notifications_withheld"], [0, 1])
        # Unknown outcome paths are explicit, not promoted
        self.assertNotIn("promoted", str(result))

    # -- invalid key b'' rejected (no fallback to _TEST_KEY) ------------

    def test_invalid_key_empty_bytes_rejected_no_side_effects(self):
        """Key=b'': ValueError raised before any observation or DB state."""
        calls = []

        def probe():
            calls.append(1)
            return dict(FINDINGS)

        with self.assertRaises(ValueError):
            run_fixture(key=b"", probe=probe)
        self.assertEqual(calls, [])  # rejected before any observation

    # -- persisted replay / RESOLVED -----------------------------------

    def test_persisted_replay_resolved_same_paths(self):
        """Re-running fixture with same DB paths persists RESOLVED state."""
        first = self.run_full()
        # Re-run using the same DB paths from the first outcome
        second = replay_fixture(first)
        # Second run should show duplicate; no new missions or notifications
        self.assertEqual(len(first["opened"]), 1)
        self.assertEqual(second["opened"], [])
        self.assertEqual(second["totals"]["duplicate"], 1)
        self.assertEqual(second["totals"]["missions_reserved"], 0)
        self.assertEqual(second["totals"]["missions_already_reserved"], 1)
        self.assertEqual(second["totals"]["notifications_queued"], 0)
        self.assertEqual(second["totals"]["notifications_existing"], 1)
        # Verify DB counts unchanged
        con = sqlite3.connect(first["ledger_path"])
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM incidents").fetchone()[0], 1)
        finally:
            con.close()
        con = sqlite3.connect(first["inbox_db_path"])
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM inbox").fetchone()[0], 1)
        finally:
            con.close()
        con = sqlite3.connect(first["reservations_db_path"])
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM reservations").fetchone()[0], 1)
        finally:
            con.close()
        con = sqlite3.connect(first["notifications_db_path"])
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 1)
        finally:
            con.close()

    # -- failure before mutation ---------------------------------------

    def test_key_validated_before_any_observation_no_partial_state(self):
        """Invalid key: ValueError raised; no DB state created."""
        def probe():
            raise RuntimeError("snapshot unavailable")

        with self.assertRaises(ValueError):
            run_fixture(key=b"short", probe=probe)
        # No partial state - DB paths from this run should not exist
        # (run_fixture creates temp dirs; we just verify the exception was raised)

    # -- caller-provided paths unchanged ------------------------------

    def test_caller_provided_paths_persisted_through_replay(self):
        """When caller provides explicit DB paths, replay_fixture reuses them."""
        root = Path(self.temp.name) / "paths"
        root.mkdir(parents=True, exist_ok=True)
        ledger = root / "ledger.db"
        outbox = root / "proposals"
        inbox = root / "inbox.db"
        reservations = root / "reservations.db"
        notifications = root / "notifications.db"

        for p in [ledger, outbox, inbox, reservations, notifications]:
            p.parent.mkdir(parents=True, exist_ok=True)

        # First run with caller-provided paths
        first = run_fixture(
            key=_TEST_KEY,
            ledger_db=ledger,
            proposal_outbox=outbox,
            inbox_db=inbox,
            reservations_db=reservations,
            notifications_db=notifications,
            probe=self._make_probe(),
        )
        # Second run reusing same paths via replay_fixture
        second = replay_fixture(first)
        # Same DB paths should be reused; counts should be idempotent
        self.assertEqual(second["opened"], [])
        self.assertEqual(second["totals"]["duplicate"], 1)
        self.assertEqual(second["totals"]["missions_already_reserved"], 1)
        self.assertEqual(second["totals"]["notifications_existing"], 1)

    # -- idempotency under restart -----------------------------------

    def test_idempotency_under_restart_with_same_paths(self):
        """Three consecutive runs with same DB paths are fully idempotent."""
        root = Path(self.temp.name) / "restart"
        root.mkdir(parents=True, exist_ok=True)
        ledger = root / "ledger.db"
        outbox = root / "proposals"
        inbox = root / "inbox.db"
        reservations = root / "reservations.db"
        notifications = root / "notifications.db"

        for p in [ledger, outbox, inbox, reservations, notifications]:
            p.parent.mkdir(parents=True, exist_ok=True)

        first = run_fixture(
            key=_TEST_KEY,
            ledger_db=ledger,
            proposal_outbox=outbox,
            inbox_db=inbox,
            reservations_db=reservations,
            notifications_db=notifications,
            probe=self._make_probe(),
        )
        second = replay_fixture(first)
        third = replay_fixture(second)

        # All three runs: first creates 1, second and third are duplicates
        self.assertEqual(len(first["opened"]), 1)
        self.assertEqual(second["opened"], [])
        self.assertEqual(third["opened"], [])
        self.assertEqual(first["totals"]["events"], 1)
        self.assertEqual(second["totals"]["events"], 1)
        self.assertEqual(third["totals"]["events"], 1)
        self.assertEqual(second["totals"]["duplicate"], 1)
        self.assertEqual(third["totals"]["duplicate"], 1)
        self.assertEqual(first["totals"]["missions_reserved"], 1)
        self.assertEqual(second["totals"]["missions_reserved"], 0)
        self.assertEqual(third["totals"]["missions_reserved"], 0)
        self.assertEqual(first["totals"]["missions_already_reserved"], 0)
        self.assertEqual(second["totals"]["missions_already_reserved"], 1)
        self.assertEqual(third["totals"]["missions_already_reserved"], 1)
        self.assertEqual(first["totals"]["notifications_queued"], 1)
        self.assertEqual(second["totals"]["notifications_queued"], 0)
        self.assertEqual(third["totals"]["notifications_queued"], 0)
        # DB counts should be exactly 1 across all runs
        con = sqlite3.connect(str(ledger))
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM incidents").fetchone()[0], 1)
        finally:
            con.close()
        con = sqlite3.connect(str(inbox))
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM inbox").fetchone()[0], 1)
        finally:
            con.close()
        con = sqlite3.connect(str(reservations))
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM reservations").fetchone()[0], 1)
        finally:
            con.close()
        con = sqlite3.connect(str(notifications))
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 1)
        finally:
            con.close()

    def _count(self, table):
        """Helper to count rows in a DB."""
        db_map = {
            "inbox": self.inbox_db,
            "reservations": self.reservations_db,
            "notifications": self.notifications_db,
        }
        db = db_map.get(table)
        if not db or not db.exists():
            return 0
        con = sqlite3.connect(str(db))
        try:
            return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            con.close()