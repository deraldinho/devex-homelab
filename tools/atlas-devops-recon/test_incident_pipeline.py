"""CP11 read-only end-to-end incident pipeline TDD.

Only an isolated fake snapshot probe, a caller-provided 32-byte TEST key and
temp paths are used. No OS tasks/services, endpoints, secrets or real sends.
"""
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

import incident_pipeline
from autonomy_policy_gate import SCHEMA
from durable_incidents import list_open, reconcile
from signed_event_transport import sign

TEST_KEY = bytes(range(32))  # caller-provided 32-byte TEST key, never production
NOW = datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc)
FINDINGS = {"worker_stale": {"summary": "heartbeat lagging"}}

POLICY = {"schema": SCHEMA, "enabled": True, "kill_switch": False,
          "mode": "observe_only", "auto_approve": False, "auto_write": False,
          "allowed_actions": ["diagnose_readonly"], "origins": ["x99_worker"],
          "kinds": ["worker_stale", "worker_duplicate"],
          "limits": {"daily_readonly_missions": 5, "max_concurrent": 2,
                     "max_total_cost_usd": 0}}


def fake_snapshot(findings=None):
    """Isolated snapshot probe: pure function, no OS inspection at all."""
    data = FINDINGS if findings is None else findings

    def probe():
        return json.loads(json.dumps(data))
    return probe


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.ledger_db = root / "ledger.db"
        self.outbox = root / "proposals"
        self.inbox_db = root / "inbox.db"
        self.reservations_db = root / "reservations.db"
        self.notifications_db = root / "notifications.db"

    def run_pipeline(self, findings=None, key=TEST_KEY, policy=None, now=NOW,
                     probe=None):
        return incident_pipeline.run_pipeline(
            probe=probe if probe is not None else fake_snapshot(findings),
            source="x99_worker", key=key, policy=policy or POLICY,
            ledger_db=self.ledger_db, proposal_outbox=self.outbox,
            inbox_db=self.inbox_db, reservations_db=self.reservations_db,
            notifications_db=self.notifications_db, now=now)

    def ingest(self, envelope, key=TEST_KEY, policy=None, now=NOW):
        return incident_pipeline.ingest_event(
            envelope, key=key, policy=policy or POLICY, inbox_db=self.inbox_db,
            reservations_db=self.reservations_db,
            notifications_db=self.notifications_db, now=now)

    def count(self, db, table):
        if not Path(db).exists():
            return 0
        con = sqlite3.connect(str(db))
        try:
            try:
                return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                return 0
        finally:
            con.close()

    def statuses(self, db, table):
        if not Path(db).exists():
            return []
        con = sqlite3.connect(str(db))
        try:
            try:
                return [r[0] for r in con.execute(
                    f"SELECT status FROM {table} ORDER BY status")]
            except sqlite3.OperationalError:
                return []
        finally:
            con.close()

    # -- happy path ------------------------------------------------------
    def test_end_to_end_readonly_chain(self):
        result = self.run_pipeline()
        self.assertEqual(result["status"], "pipeline_complete")
        self.assertEqual(len(result["opened"]), 1)
        self.assertEqual(len(list_open(self.ledger_db, "x99_worker")), 1)
        self.assertEqual(self.count(self.inbox_db, "inbox"), 1)
        self.assertEqual(self.count(self.reservations_db, "reservations"), 1)
        self.assertEqual(self.count(self.notifications_db, "notifications"), 1)
        event = result["events"][0]
        self.assertEqual(event["receiver"], "accepted")
        self.assertEqual(event["decision"], "ALLOW_READONLY_ONLY")
        self.assertEqual(event["reservation"], "RESERVED_READONLY")
        self.assertEqual(event["notification"], "queued")
        self.assertFalse(event["execution_authorized"])
        self.assertFalse(event["execution_started"])
        self.assertFalse(result["execution_started"])
        self.assertFalse(result["dispatch_performed"])
        self.assertEqual(result["messages_sent"], 0)
        # prepared for humans, NEVER sent by the pipeline
        self.assertEqual(self.statuses(self.notifications_db, "notifications"),
                         ["pending"])

    def test_static_snapshot_dict_is_accepted(self):
        result = self.run_pipeline(probe=dict(FINDINGS))
        self.assertEqual(result["totals"]["accepted"], 1)

    # -- idempotency / replay -------------------------------------------
    def test_duplicate_run_never_creates_new_mission_or_notification(self):
        first = self.run_pipeline()
        second = self.run_pipeline(now=NOW + timedelta(minutes=5))
        self.assertEqual(len(first["opened"]), 1)
        self.assertEqual(second["opened"], [])
        self.assertEqual(second["totals"]["duplicate"], 1)
        self.assertEqual(second["totals"]["missions_reserved"], 0)
        self.assertEqual(second["totals"]["missions_already_reserved"], 1)
        self.assertEqual(second["totals"]["notifications_queued"], 0)
        self.assertEqual(second["totals"]["notifications_existing"], 1)
        self.assertEqual(self.count(self.reservations_db, "reservations"), 1)
        self.assertEqual(self.count(self.notifications_db, "notifications"), 1)
        self.assertEqual(self.count(self.inbox_db, "inbox"), 1)

    def test_replayed_envelope_is_idempotent(self):
        reconcile(self.ledger_db, self.outbox, source="x99_worker",
                  findings=FINDINGS, at=NOW)
        proposal = json.loads(
            next(self.outbox.glob("*.json")).read_text(encoding="utf-8"))
        envelope = sign(proposal, key=TEST_KEY, origin="x99_worker", now=NOW)
        first = self.ingest(envelope)
        second = self.ingest(envelope)
        self.assertEqual(first["receiver"], "accepted")
        self.assertEqual(first["reservation"], "RESERVED_READONLY")
        self.assertEqual(first["notification"], "queued")
        self.assertEqual(second["receiver"], "duplicate")
        self.assertEqual(second["reservation"], "ALREADY_RESERVED")
        self.assertEqual(second["notification"], "already_queued")
        self.assertEqual(self.count(self.reservations_db, "reservations"), 1)
        self.assertEqual(self.count(self.notifications_db, "notifications"), 1)

    def test_resolution_replay_never_creates_mission_or_notification(self):
        first = self.run_pipeline()
        second = self.run_pipeline(findings={},
                                   now=NOW + timedelta(minutes=2))
        self.assertEqual(first["totals"]["notifications_queued"], 1)
        self.assertEqual(second["resolved"], first["opened"])
        self.assertEqual(second["totals"]["resolutions"], 1)
        self.assertEqual(second["totals"]["missions_reserved"], 0)
        self.assertEqual(second["totals"]["notifications_queued"], 0)
        self.assertEqual(self.count(self.reservations_db, "reservations"), 1)
        self.assertEqual(self.count(self.notifications_db, "notifications"), 1)
        self.assertEqual(self.count(self.inbox_db, "inbox"), 2)

    def test_corrupt_inbox_fails_closed_no_deferred_or_new_mission(self):
        self.run_pipeline()
        self.inbox_db.write_bytes(b"not a sqlite database")
        with self.assertRaises(sqlite3.OperationalError):
            self.run_pipeline(findings={}, now=NOW + timedelta(minutes=2))
        self.assertEqual(self.count(self.reservations_db, "reservations"), 1)
        self.assertEqual(self.count(self.notifications_db, "notifications"), 1)

    # -- fail closed on untrusted input ---------------------------------
    def test_forged_signature_and_wrong_key_leave_no_side_effects(self):
        self.run_pipeline()
        proposal = json.loads(
            next(self.outbox.glob("*.json")).read_text(encoding="utf-8"))
        forged = sign(proposal, key=TEST_KEY, origin="x99_worker", now=NOW)
        forged["signature"] = "0" * 64
        with self.assertRaises(PermissionError):
            self.ingest(forged)
        with self.assertRaises(PermissionError):
            self.ingest(sign(proposal, key=TEST_KEY, origin="x99_worker",
                             now=NOW), key=bytes(range(1, 33)))
        self.assertEqual(self.count(self.inbox_db, "inbox"), 1)
        self.assertEqual(self.count(self.reservations_db, "reservations"), 1)
        self.assertEqual(self.count(self.notifications_db, "notifications"), 1)

    def test_execution_escalation_never_reaches_receiver(self):
        reconcile(self.ledger_db, self.outbox, source="x99_worker",
                  findings=FINDINGS, at=NOW)
        proposal = json.loads(
            next(self.outbox.glob("*.json")).read_text(encoding="utf-8"))
        with self.assertRaises(PermissionError):
            sign(dict(proposal, auto_execute=True), key=TEST_KEY,
                 origin="x99_worker", now=NOW)
        self.assertFalse(self.inbox_db.exists())

    # -- caller-provided key, paths and policy fail fast ----------------
    def test_key_must_be_caller_provided_32_bytes(self):
        calls = []

        def probe():
            calls.append(1)
            return dict(FINDINGS)

        with self.assertRaises(ValueError):
            self.run_pipeline(key=b"short", probe=probe)
        self.assertEqual(calls, [])  # rejected before any observation
        with self.assertRaises(TypeError):
            incident_pipeline.run_pipeline(probe=probe, source="x99_worker",
                                           policy=POLICY)
        self.assertFalse(hasattr(incident_pipeline, "KEY"))
        self.assertFalse(hasattr(incident_pipeline, "HMAC_KEY"))

    def test_invalid_policy_fails_before_observation(self):
        calls = []

        def probe():
            calls.append(1)
            return dict(FINDINGS)

        with self.assertRaises(PermissionError):
            self.run_pipeline(policy=dict(POLICY, auto_approve=True),
                              probe=probe)
        self.assertEqual(calls, [])

    # -- autonomy policy gates the mission and the notification ---------
    def test_kill_switch_pauses_before_mission_and_notification(self):
        result = self.run_pipeline(policy=dict(POLICY, kill_switch=True))
        event = result["events"][0]
        self.assertEqual(event["receiver"], "accepted")
        self.assertEqual(event["decision"], "PAUSED")
        self.assertEqual(event["notification"], "skipped")
        self.assertEqual(self.count(self.reservations_db, "reservations"), 0)
        self.assertEqual(self.count(self.notifications_db, "notifications"), 0)

    def test_unapproved_kind_gets_no_mission_or_notification(self):
        result = self.run_pipeline(policy=dict(POLICY,
                                               kinds=["worker_duplicate"]))
        event = result["events"][0]
        self.assertEqual(event["decision"], "DENIED")
        self.assertEqual(event["notification"], "skipped")
        self.assertEqual(self.count(self.inbox_db, "inbox"), 1)
        self.assertEqual(self.count(self.reservations_db, "reservations"), 0)
        self.assertEqual(self.count(self.notifications_db, "notifications"), 0)

    def test_daily_limit_withholds_second_mission_and_notification(self):
        strict = dict(POLICY, limits={"daily_readonly_missions": 1,
                                      "max_concurrent": 1,
                                      "max_total_cost_usd": 0})
        self.run_pipeline(policy=strict)
        second = self.run_pipeline(
            policy=strict, now=NOW + timedelta(minutes=1),
            findings={"worker_stale": {"summary": "heartbeat lagging"},
                      "worker_duplicate": {"summary": "two workers"}})
        self.assertEqual(second["totals"]["missions_reserved"], 0)
        self.assertEqual(second["totals"]["missions_already_reserved"], 1)
        self.assertEqual(second["totals"]["missions_withheld"], 1)
        self.assertEqual(second["totals"]["notifications_withheld"], 1)
        self.assertEqual(len(list_open(self.ledger_db, "x99_worker")), 2)
        self.assertEqual(self.count(self.inbox_db, "inbox"), 2)
        self.assertEqual(self.count(self.reservations_db, "reservations"), 1)
        self.assertEqual(self.count(self.notifications_db, "notifications"), 1)

    # -- fail closed on probe problems ----------------------------------
    def test_probe_failure_fails_closed_without_partial_state(self):
        def boom():
            raise RuntimeError("snapshot unavailable")

        with self.assertRaises(RuntimeError):
            self.run_pipeline(probe=boom)
        self.assertFalse(self.inbox_db.exists())
        self.assertEqual(self.count(self.reservations_db, "reservations"), 0)
        self.assertEqual(self.count(self.notifications_db, "notifications"), 0)

    # -- no execution / no send capability in the module ----------------
    def test_pipeline_exposes_no_dispatch_or_os_execution_capability(self):
        source = Path(incident_pipeline.__file__).read_text(encoding="utf-8")
        self.assertNotIn("dispatch_one", source)
        self.assertNotIn("explicit_enabled", source)
        self.assertNotIn("subprocess", source)
        result = self.run_pipeline()
        self.assertEqual(result["messages_sent"], 0)
        self.assertEqual(self.statuses(self.notifications_db, "notifications"),
                         ["pending"])


class ReadonlyUriRegressionTests(unittest.TestCase):
    def test_reserved_uri_chars_do_not_tamper_mode_ro(self):
        import tempfile
        from pathlib import Path
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        weird = root / "dir#pct"
        weird.mkdir()
        inbox_db = weird / "inbox#%.db"
        ledger_db = root / "ledger.db"
        outbox = root / "proposals"
        reservations_db = root / "reservations.db"
        notifications_db = root / "notifications.db"
        result = incident_pipeline.run_pipeline(
            probe=fake_snapshot(FINDINGS) if False else (lambda: dict(FINDINGS)),
            source="x99_worker", key=TEST_KEY, policy=POLICY,
            ledger_db=ledger_db, proposal_outbox=outbox,
            inbox_db=inbox_db, reservations_db=reservations_db,
            notifications_db=notifications_db, now=NOW)
        self.assertEqual(result["status"], "pipeline_complete")
        self.assertEqual(self._count(inbox_db, "inbox"), 1)

    def _count(self, db, table):
        if not Path(db).exists():
            return 0
        con = sqlite3.connect(str(db))
        try:
            return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            return 0
        finally:
            con.close()

if __name__ == "__main__":
    unittest.main()
