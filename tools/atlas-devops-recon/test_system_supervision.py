"""CP11 read-only supervisor observability TDD; every OS dependency is mocked.

No real Windows service, systemd unit, network or production file is touched:
observers arrive through a unittest.mock seam and every ledger lives inside a
temporary directory.
"""
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import system_supervision as ss
from durable_incidents import connect, reconcile

T = datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc)
WIN = "windows_worker_observer"
LINUX = "linux_systemd_observer"
POLICY = {"schema": ss.KILL_SWITCH_SCHEMA, "enabled": True, "kill_switch": False}
FINDINGS = {"worker_not_running": {"summary": "worker stopped"},
            "worker_stale": {"summary": "heartbeat missing"}}
DEFAULT = object()


def beat(observer, seq=1, at=T, detector=None):
    return {"schema": ss.HEARTBEAT_SCHEMA, "observer": observer,
            "detector": detector or (observer + ".probe"),
            "sequence": seq, "observed_at": at.isoformat()}


def fake_provider(mapping):
    def provide(observer):
        return mapping.get(observer)
    return mock.Mock(side_effect=provide)


def tree_digest(root):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).iterdir()) if p.is_file()}


class SupervisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ledger = self.root / "ledger.db"
        connect(self.ledger).close()
        self.last_provider = None

    def observe(self, mapping, *, now=T, ledger=DEFAULT, policy=None,
                window=ss.STALE_WINDOW_SECONDS):
        provider = fake_provider(mapping)
        self.last_provider = provider
        return ss.observe(provider=provider,
                          policy=POLICY if policy is None else policy,
                          ledger_path=self.ledger if ledger is DEFAULT else ledger,
                          now=now, stale_window_seconds=window)

    def seed(self, name, opened_at, updated_at=None):
        db = self.root / name
        con = connect(db)
        con.execute("""INSERT INTO incidents(id,source,kind,occurrence,status,
                       payload,opened_at,updated_at) VALUES(?,?,?,?,?,?,?,?)""",
                    ("b" * 32, "x99_worker", "worker_stale", 1, "open", "{}",
                     opened_at, updated_at or opened_at))
        con.close()
        return db

    def test_fresh_heartbeats_and_empty_ledger_are_healthy(self):
        report = self.observe({WIN: beat(WIN),
                               LINUX: beat(LINUX, at=T - timedelta(seconds=3))})
        self.assertEqual(report["schema"], ss.SCHEMA)
        self.assertEqual(report["mode"], "MONITORING")
        self.assertEqual(report["supervision"], "HEALTHY")
        self.assertEqual(report["heartbeats"][WIN]["status"], "HEALTHY")
        self.assertEqual(report["heartbeats"][LINUX]["age_seconds"], 3.0)
        self.assertEqual(report["alarms"], {"ledger_present": True,
                                            "open_alarms": 0, "status": "CLEAR",
                                            "reason": None})
        self.assertEqual(report["generated_at"], "2026-10-14T18:00:00+00:00")
        self.assertTrue(report["generated_at"].endswith("+00:00"))
        self.last_provider.assert_has_calls([mock.call(WIN), mock.call(LINUX)])
        self.assertEqual(self.last_provider.call_count, 2)

    def test_offset_timestamps_normalise_to_verifiable_utc(self):
        record = dict(beat(WIN), observed_at="2026-10-14T20:00:00+02:00")
        report = self.observe({WIN: record, LINUX: beat(LINUX)})
        self.assertEqual(report["heartbeats"][WIN]["observed_at"],
                         "2026-10-14T18:00:00+00:00")
        self.assertEqual(report["heartbeats"][WIN]["age_seconds"], 0.0)

    def test_stale_window_boundary_and_degradation(self):
        inside = self.observe({WIN: beat(WIN, at=T - timedelta(
                                   seconds=ss.STALE_WINDOW_SECONDS)),
                               LINUX: beat(LINUX)})
        self.assertEqual(inside["heartbeats"][WIN]["status"], "HEALTHY")
        outside = self.observe({WIN: beat(WIN, at=T - timedelta(
                                    seconds=ss.STALE_WINDOW_SECONDS + 1)),
                                LINUX: beat(LINUX)})
        self.assertEqual(outside["heartbeats"][WIN]["status"], "STALE")
        self.assertEqual(outside["heartbeats"][WIN]["age_seconds"], 121.0)
        self.assertEqual(outside["heartbeats"][WIN]["stale_window_seconds"],
                         ss.STALE_WINDOW_SECONDS)
        self.assertEqual(outside["supervision"], "DEGRADED")
        self.assertEqual(outside["mode"], "MONITORING")

    def test_naive_data_is_rejected(self):
        with self.assertRaises(ValueError):
            self.observe({WIN: dict(beat(WIN), observed_at="2026-10-14T18:00:00"),
                          LINUX: beat(LINUX)})
        with self.assertRaises(ValueError):
            self.observe({WIN: beat(WIN, at=datetime(2026, 10, 14, 18, 0)),
                          LINUX: beat(LINUX)})
        with self.assertRaises(ValueError):
            self.observe({WIN: beat(WIN), LINUX: beat(LINUX)},
                         now=datetime(2026, 10, 14, 18, 0))

    def test_future_data_is_rejected(self):
        with self.assertRaises(ValueError):
            self.observe({WIN: beat(WIN, at=T + timedelta(seconds=1)),
                          LINUX: beat(LINUX)})
        with self.assertRaises(ValueError):
            self.observe({WIN: beat(WIN), LINUX: beat(LINUX)},
                         now=T - timedelta(seconds=1))

    def test_duplicate_detector_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            self.observe({WIN: beat(WIN, seq=7, detector="shared.probe"),
                          LINUX: beat(LINUX, seq=7, detector="shared.probe")})
        with self.assertRaises(ValueError):
            self.observe({WIN: [beat(WIN, seq=3, detector="win.probe"),
                                beat(WIN, seq=3, detector="win.probe")],
                          LINUX: beat(LINUX)})

    def test_heartbeat_shape_and_identity_are_validated(self):
        cases = [{**beat(WIN), "schema": "attacker.v1"},
                 {**beat(WIN), "observer": LINUX},
                 {**beat(WIN), "extra": 1},
                 {**beat(WIN), "sequence": "1"},
                 {**beat(WIN), "sequence": -1},
                 {**beat(WIN), "detector": ""},
                 {**beat(WIN), "detector": "Bad Detector"},
                 beat(WIN) | {"observed_at": 1770000000}]
        for record in cases:
            with self.subTest(record=record):
                with self.assertRaises(ValueError):
                    self.observe({WIN: record, LINUX: beat(LINUX)})
        with self.assertRaises(ValueError):
            ss.assess_heartbeat(beat(WIN), observer="attacker", now=T)
        with self.assertRaises(ValueError):
            ss.assess_heartbeat(beat(WIN), observer=WIN, now=T,
                                stale_window_seconds=0)

    def test_provider_contract_is_validated(self):
        with self.assertRaises(ValueError):
            ss.observe(provider="not-callable", policy=POLICY,
                       ledger_path=self.ledger, now=T)
        with self.assertRaises(ValueError):
            self.observe({WIN: "broken", LINUX: beat(LINUX)})
        with self.assertRaises(ValueError):
            self.observe({WIN: [beat(WIN), "junk"], LINUX: beat(LINUX)})
        with self.assertRaises(ValueError):
            self.observe({WIN: beat(WIN), LINUX: beat(LINUX)}, window=None)
        with self.assertRaises(ValueError):
            self.observe({WIN: beat(WIN), LINUX: beat(LINUX)}, window=True)
        with self.assertRaises(ValueError):
            self.observe({WIN: beat(WIN), LINUX: beat(LINUX)}, window=0)

    def test_missing_observer_is_degraded_not_assumed_healthy(self):
        report = self.observe({WIN: beat(WIN)})
        self.assertEqual(report["heartbeats"][LINUX]["status"], "MISSING")
        self.assertIsNone(report["heartbeats"][LINUX]["observed_at"])
        self.assertEqual(report["supervision"], "DEGRADED")
        self.assertEqual(report["mode"], "MONITORING")

    def test_alarms_are_read_from_existing_ledger_without_mutation(self):
        reconcile(self.ledger, self.root / "out", source="x99_worker",
                  findings=FINDINGS, at=T - timedelta(seconds=30))
        before = tree_digest(self.root)
        report = self.observe({WIN: beat(WIN), LINUX: beat(LINUX)})
        self.assertEqual(report["alarms"]["status"], "ALARM")
        self.assertEqual(report["alarms"]["open_alarms"], 2)
        self.assertEqual(report["alarms"]["ledger_present"], True)
        self.assertEqual(report["supervision"], "DEGRADED")
        self.assertEqual(report["mode"], "MONITORING")
        self.assertEqual(tree_digest(self.root), before)

    def test_resolved_ledger_reports_clear(self):
        reconcile(self.ledger, self.root / "out", source="x99_worker",
                  findings=FINDINGS, at=T - timedelta(seconds=60))
        reconcile(self.ledger, self.root / "out", source="x99_worker",
                  findings={}, at=T - timedelta(seconds=30))
        report = self.observe({WIN: beat(WIN), LINUX: beat(LINUX)})
        self.assertEqual(report["alarms"], {"ledger_present": True,
                                            "open_alarms": 0, "status": "CLEAR",
                                            "reason": None})
        self.assertEqual(report["supervision"], "HEALTHY")

    def test_missing_or_unconfigured_ledger_fails_closed(self):
        absent = self.root / "absent.db"
        report = self.observe({WIN: beat(WIN), LINUX: beat(LINUX)},
                              ledger=absent)
        self.assertFalse(absent.exists())
        self.assertEqual(report["alarms"], {"ledger_present": False,
                                            "open_alarms": None,
                                            "status": "UNKNOWN",
                                            "reason": "missing_ledger"})
        self.assertEqual(report["supervision"], "DEGRADED")
        report = self.observe({WIN: beat(WIN), LINUX: beat(LINUX)},
                              ledger=None)
        self.assertEqual(report["alarms"]["status"], "UNKNOWN")
        self.assertEqual(report["alarms"]["reason"], "not_configured")
        self.assertEqual(report["supervision"], "DEGRADED")

    def test_unreadable_ledger_fails_closed(self):
        broken = self.root / "broken.db"
        broken.write_text("this is not a sqlite database", encoding="utf-8")
        report = self.observe({WIN: beat(WIN), LINUX: beat(LINUX)},
                              ledger=broken)
        self.assertEqual(report["alarms"]["status"], "UNKNOWN")
        self.assertEqual(report["alarms"]["ledger_present"], True)
        self.assertEqual(report["alarms"]["reason"], "read_failed")
        self.assertEqual(report["supervision"], "DEGRADED")

    def test_naive_ledger_timestamp_is_rejected(self):
        db = self.seed("naive.db", "2026-10-14T17:00:00")
        with self.assertRaises(ValueError):
            self.observe({WIN: beat(WIN), LINUX: beat(LINUX)}, ledger=db)

    def test_future_ledger_timestamp_is_rejected(self):
        db = self.seed("future.db", (T + timedelta(seconds=60)).isoformat())
        with self.assertRaises(ValueError):
            self.observe({WIN: beat(WIN), LINUX: beat(LINUX)}, ledger=db)

    def test_kill_switch_gate_is_pure_and_deterministic(self):
        outputs = {ss.kill_switch_gate(dict(POLICY)) for _ in range(50)}
        self.assertEqual(outputs, {"MONITORING"})
        self.assertEqual(ss.kill_switch_gate({**POLICY, "kill_switch": True}),
                         "PAUSED")
        self.assertEqual(ss.kill_switch_gate({**POLICY, "enabled": False}),
                         "PAUSED")

    def test_kill_switch_gates_perfect_health_independently(self):
        report = self.observe({WIN: beat(WIN), LINUX: beat(LINUX)},
                              policy={**POLICY, "kill_switch": True})
        self.assertEqual(report["mode"], "PAUSED")
        self.assertEqual(report["supervision"], "HEALTHY")
        self.assertTrue(report["kill_switch"]["engaged"])
        self.assertEqual(report["kill_switch"]["decision"], "PAUSED")

    def test_health_never_flips_the_gate_in_either_direction(self):
        degraded = self.observe({WIN: beat(WIN, at=T - timedelta(seconds=600)),
                                 LINUX: beat(LINUX, at=T - timedelta(seconds=600))})
        self.assertEqual(degraded["supervision"], "DEGRADED")
        self.assertEqual(degraded["mode"], "MONITORING")
        first = ss.kill_switch_gate(dict(POLICY))
        self.observe({WIN: beat(WIN), LINUX: beat(LINUX)})
        self.assertEqual(ss.kill_switch_gate(dict(POLICY)), first)

    def test_identical_inputs_produce_identical_reports(self):
        first = self.observe({WIN: beat(WIN), LINUX: beat(LINUX, seq=4)})
        second = self.observe({WIN: beat(WIN), LINUX: beat(LINUX, seq=4)})
        self.assertEqual(first, second)
        json.dumps(first)

    def test_kill_switch_policy_is_validated(self):
        bad = [{**POLICY, "schema": "attacker.v1"},
               {**POLICY, "enabled": "yes"},
               {**POLICY, "enabled": 0},
               {**POLICY, "kill_switch": 1},
               {**POLICY, "kill_switch": "true"},
               {**POLICY, "extra": True},
               {"enabled": True, "kill_switch": False},
               "not-a-policy",
               None]
        for policy in bad:
            with self.subTest(policy=policy):
                with self.assertRaises(ValueError):
                    ss.kill_switch_gate(policy)

    def test_observe_never_touches_services_or_network(self):
        report = self.observe({WIN: beat(WIN), LINUX: beat(LINUX)})
        self.assertEqual((report["read_only"], report["execution_started"],
                          report["messages_sent"], report["services_restarted"]),
                         (True, False, False, False))
        self.last_provider.assert_has_calls([mock.call(WIN), mock.call(LINUX)])
        with mock.patch("os.system", side_effect=AssertionError("os.system")), \
             mock.patch("subprocess.run", side_effect=AssertionError("run")), \
             mock.patch("subprocess.Popen", side_effect=AssertionError("popen")), \
             mock.patch("socket.socket", side_effect=AssertionError("socket")):
            self.observe({WIN: beat(WIN), LINUX: beat(LINUX)})

    def test_module_declares_no_control_messaging_capability(self):
        source = Path(ss.__file__).read_text(encoding="utf-8")
        for token in ("subprocess", "os.system", "popen", "smtplib", "socket",
                      "urllib", "requests", "systemctl", "taskkill", "net start",
                      "sc.exe", "paramiko", "http.client", "os.remove",
                      "os.unlink", "shutil.rmtree", "os.replace"):
            with self.subTest(token=token):
                self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
