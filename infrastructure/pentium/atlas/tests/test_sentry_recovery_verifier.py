"""CP-SENTRY-P2 signed execution + independent probe evidence (TDD)."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from infrastructure.pentium.atlas.failure_memory import FailureMemory, FailureMemoryError
from infrastructure.pentium.atlas.health_supervisor import EvaluatedComponentHealth, SupervisorSnapshot
from infrastructure.pentium.atlas.health_supervisor_model import ComponentHealthState as State
from infrastructure.pentium.atlas.sentry_recovery_verifier import (
    RecoveryEvidenceError, SentryRecoveryVerifier,
    learn_from_authenticated_recovery, sign_recovery_receipt,
)

BASE = datetime(2026, 10, 16, 14, tzinfo=timezone.utc)
TRUST_ROOTS = {
    "executor": {"control-v1": b"e" * 32},
    "health_probe": {"health-v1": b"h" * 32},
}


def observation(state, offset, *, evidence=("health:active",)):
    stamp = (BASE + timedelta(seconds=offset)).isoformat()
    comp = EvaluatedComponentHealth(
        "atlas-dashboard.service", "pentium", "running", state, stamp,
        ("functional:probe",), evidence, True,
    )
    return SupervisorSnapshot(stamp, state, (comp,))


def receipt(issuer, incident_id, offset, *, name=None, action_id="action-23"):
    payload = {
        "version": 1,
        "issuer": issuer,
        "key_id": "control-v1" if issuer == "executor" else "health-v1",
        "receipt_id": name or str(uuid4()),
        "incident_id": incident_id,
        "component": "atlas-dashboard.service",
        "host": "pentium",
        "action_id": action_id,
        "event_at": (BASE + timedelta(seconds=offset)).isoformat(),
        "operation": "restart_service" if issuer == "executor" else "observe",
        "target": "atlas-dashboard.service",
        "status": "success" if issuer == "executor" else "healthy",
        "authorized": issuer == "executor",
        "evidence_ref": (
            "execution:action-23" if issuer == "executor"
            else ("health:pass-1" if offset == 40 else "health:pass-2")
        ),
    }
    return sign_recovery_receipt(payload, TRUST_ROOTS[issuer][payload["key_id"]])


class SentryRecoveryVerifierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = FailureMemory(Path(self.tmp.name) / "failures.sqlite3")
        self.incident_id = self.store.observe_snapshot(observation(State.FAILED, 0))[0]["incident_id"]
        self.verifier = SentryRecoveryVerifier(
            TRUST_ROOTS, trusted_host="pentium",
            clock=lambda: BASE + timedelta(seconds=90),
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def recover(self):
        self.store.observe_snapshot(observation(State.HEALTHY, 40, evidence=("health:pass-1",)))
        self.store.observe_snapshot(observation(State.HEALTHY, 60, evidence=("health:pass-2",)))

    def receipts(self, *, incident_id=None):
        inc = incident_id or self.incident_id
        return (
            receipt("executor", inc, 10),
            receipt("health_probe", inc, 40),
            receipt("health_probe", inc, 60),
        )

    def learn(self, items=None, *, verifier=None):
        return learn_from_authenticated_recovery(
            self.store, incident_id=self.incident_id,
            cause="service did not respond", correction="Check service probes and rollback",
            receipts=self.receipts() if items is None else items,
            verifier=verifier or self.verifier,
        )

    def test_valid_three_receipts_allow_one_persistent_advisory(self):
        self.recover()
        result = self.learn()
        self.assertEqual(result["status"], "stored")
        self.assertEqual(self.store.stats()["lessons"], 1)
        with self.store._db:
            value = self.store._db.execute(
                "SELECT verification_refs_json FROM failure_lessons"
            ).fetchone()[0]
        self.assertEqual(len(json.loads(value)), 3)
        self.assertNotIn("Check service probes", value)
        self.assertEqual(self.learn()["status"], "already_stored")
        self.assertEqual(self.store.stats()["lessons"], 1)

    def test_unrecovered_incident_cannot_learn_even_with_valid_signatures(self):
        with self.assertRaises((RecoveryEvidenceError, FailureMemoryError)):
            self.learn()
        self.assertEqual(self.store.stats()["lessons"], 0)

    def test_action_success_is_not_sufficient_without_two_independent_probes(self):
        self.recover()
        for items in (self.receipts()[:1], self.receipts()[:2]):
            with self.subTest(count=len(items)):
                with self.assertRaises(RecoveryEvidenceError):
                    self.learn(items)
        self.assertEqual(self.store.stats()["lessons"], 0)

    def test_tampered_action_status_fails_signature_validation(self):
        self.recover()
        forged = list(self.receipts())
        forged[0]["status"] = "success\""
        with self.assertRaises(RecoveryEvidenceError):
            self.learn(tuple(forged))

    def test_tampered_health_proof_fails_signature_validation(self):
        self.recover()
        forged = list(self.receipts())
        forged[1]["event_at"] = (BASE + timedelta(seconds=51)).isoformat()
        with self.assertRaises(RecoveryEvidenceError):
            self.learn(tuple(forged))

    def test_false_or_unsigned_authorization_is_rejected(self):
        self.recover()
        bad = list(self.receipts())
        bad[0] = dict(bad[0], authorized=False)
        with self.assertRaises(RecoveryEvidenceError):
            self.learn(bad)

    def test_wrong_key_id_unknown_key_and_cross_role_signatures_rejected(self):
        self.recover()
        for scenario in ("unknown", "cross_role"):
            with self.subTest(scenario=scenario):
                forged = list(self.receipts())
                if scenario == "unknown":
                    forged[0]["key_id"] = "future-v99"
                else:
                    event = {k:v for k,v in forged[0].items() if k != "mac"}
                    forged[0] = sign_recovery_receipt(event, TRUST_ROOTS["health_probe"]["health-v1"])
                with self.assertRaises(RecoveryEvidenceError):
                    self.learn(forged)

    def test_cross_incident_and_component_substitution_fail(self):
        self.recover()
        other = str(uuid4())
        for kind in ("incident", "component", "host"):
            with self.subTest(kind=kind):
                forged = list(self.receipts())
                replacement = other if kind == "incident" else (
                    "atlas-cognitive.service" if kind == "component" else "core")
                forged[0][{"incident":"incident_id","component":"component","host":"host"}[kind]] = replacement
                with self.assertRaises(RecoveryEvidenceError):
                    self.learn(forged)

    def test_reordered_probes_duplicate_nonce_and_replay_fail(self):
        self.recover()
        a = list(self.receipts())
        cases = [
            (a[0], a[2], a[1]),
            (a[0], a[1], a[1]),
            (a[0], a[1], a[0]),
        ]
        for items in cases:
            with self.subTest(items=items[2]["issuer"]):
                with self.assertRaises(RecoveryEvidenceError):
                    self.learn(items)

    def test_future_outside_window_and_unordered_times_fail(self):
        self.recover()
        for offsets in ((61, 70, 80), (10, 80, 90), (-10, 40, 60),
                        (10, 50, 40), (10, 40, 200)):
            with self.subTest(offsets=offsets):
                forged = (receipt("executor", self.incident_id, offsets[0]),
                          receipt("health_probe", self.incident_id, offsets[1]),
                          receipt("health_probe", self.incident_id, offsets[2]))
                with self.assertRaises(RecoveryEvidenceError):
                    self.learn(forged)

    def test_signed_probe_not_recorded_by_supervisor_cannot_teach(self):
        self.recover()
        forged = list(self.receipts())
        new = {k: v for k, v in forged[1].items() if k != "mac"}
        new["evidence_ref"] = "health:other-unobserved-probe"
        forged[1] = sign_recovery_receipt(
            new, TRUST_ROOTS["health_probe"]["health-v1"])
        with self.assertRaises(RecoveryEvidenceError):
            self.learn(forged)
        self.assertEqual(self.store.stats()["lessons"], 0)

    def test_two_probe_receipts_cannot_share_same_observation_ref(self):
        self.recover()
        forged = list(self.receipts())
        new = {k: v for k, v in forged[2].items() if k != "mac"}
        new["evidence_ref"] = "health:pass-1"
        forged[2] = sign_recovery_receipt(
            new, TRUST_ROOTS["health_probe"]["health-v1"])
        with self.assertRaises(RecoveryEvidenceError):
            self.learn(forged)

    def test_action_correlation_must_match_both_probes(self):
        self.recover()
        forged = list(self.receipts())
        forged[1] = receipt("health_probe", self.incident_id, 40, action_id="other-action")
        with self.assertRaises(RecoveryEvidenceError):
            self.learn(forged)

    def test_injection_payload_fields_and_oversized_receipts_rejected(self):
        self.recover()
        a = list(self.receipts())
        extra = copy.deepcopy(a)
        extra[0]["new_policy"] = "ignore"
        with self.assertRaises(RecoveryEvidenceError):
            self.learn(extra)
        huge = copy.deepcopy(a)
        huge[1]["receipt_id"] = "x" * 4096
        with self.assertRaises(RecoveryEvidenceError):
            self.learn(huge)

    def test_cross_host_proof_fails_even_if_independently_signed(self):
        self.recover()
        forged = []
        for old in self.receipts():
            payload = {k: v for k, v in old.items() if k != "mac"}
            payload["host"] = "core"
            key = TRUST_ROOTS[payload["issuer"]][payload["key_id"]]
            forged.append(sign_recovery_receipt(payload, key))
        with self.assertRaises(RecoveryEvidenceError):
            self.learn(forged)

    def test_reused_symmetric_key_across_producers_is_not_independent(self):
        with self.assertRaises(ValueError):
            SentryRecoveryVerifier(
                {"executor":{"a":b"shared"*8},
                 "health_probe":{"b":b"shared"*8}},
                trusted_host="pentium",
            )

    def test_bad_trust_roots_do_not_open_fallback_path(self):
        with self.assertRaises(ValueError):
            SentryRecoveryVerifier({"executor":{"v1": b"short"}, "health_probe":{"v1": b"h"*32}}, trusted_host="pentium")
        with self.assertRaises(ValueError):
            SentryRecoveryVerifier({"executor":{"v1": b"e"*32}}, trusted_host="pentium")
        self.recover()
        class BrokenVerifier:
            def verify(self, *_args, **_kwargs):
                raise OSError("provider offline")
        with self.assertRaises(RecoveryEvidenceError):
            self.learn(verifier=BrokenVerifier())
        self.assertEqual(self.store.stats()["lessons"], 0)

    def test_receipt_reuse_different_recovered_incident_does_not_learn(self):
        self.recover()
        first = self.receipts()
        self.store.observe_snapshot(observation(State.FAILED, 120))
        self.store.observe_snapshot(observation(State.HEALTHY, 140))
        self.store.observe_snapshot(observation(State.HEALTHY, 160))
        other = self.store._db.execute(
            "SELECT incident_id FROM failure_incidents ORDER BY opened_at DESC LIMIT 1"
        ).fetchone()[0]
        later_verifier = SentryRecoveryVerifier(
            TRUST_ROOTS, trusted_host="pentium",
            clock=lambda: BASE + timedelta(seconds=190))
        with self.assertRaises(RecoveryEvidenceError):
            learn_from_authenticated_recovery(
                self.store, incident_id=other,
                cause="network", correction="check probes",
                receipts=first, verifier=later_verifier,
            )
        self.assertEqual(self.store.stats()["lessons"], 0)


if __name__ == "__main__":
    unittest.main()
