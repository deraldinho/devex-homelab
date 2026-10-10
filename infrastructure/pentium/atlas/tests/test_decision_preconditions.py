import unittest
from datetime import datetime, timezone

from infrastructure.pentium.atlas.decision_preconditions import DecisionPreconditionGate
from infrastructure.pentium.atlas.recovery_model import RecoveryPlan, RecoveryRisk


NOW = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)


def plan(**overrides):
    payload = dict(
        recovery_id="r1",
        host="core",
        target="atlas-worker",
        capability="restart_container",
        risk=RecoveryRisk.SAFE_CONTROL,
        reversible=True,
        expected_postconditions=("container_running",),
        max_attempts=2,
        cooldown_s=60.0,
        timeout_s=15.0,
        generation_token="gen-7",
    )
    payload.update(overrides)
    return RecoveryPlan(**payload)


def current(**overrides):
    payload = dict(
        target_unhealthy=True,
        observed_at="2026-10-09T11:59:45+00:00",
        generation_token="gen-7",
        capability_allowed=True,
        equivalent_recovery_completed=False,
        policy_allowed=True,
        human_confirmation_recovery_id=None,
    )
    payload.update(overrides)
    return payload


class DecisionPreconditionTests(unittest.TestCase):
    def setUp(self):
        self.gate = DecisionPreconditionGate(max_evidence_age_s=30, clock=lambda: NOW)

    def test_all_current_assumptions_allow_execution(self):
        result = self.gate.validate(plan(), current())
        self.assertTrue(result.allowed)
        self.assertEqual("ok", result.reason)
        self.assertTrue(all(check.satisfied for check in result.checks))

    def test_target_already_healthy_blocks_stale_recovery(self):
        result = self.gate.validate(plan(), current(target_unhealthy=False))
        self.assertFalse(result.allowed)
        self.assertEqual("target_already_healthy", result.reason)

    def test_stale_evidence_requires_refresh(self):
        result = self.gate.validate(
            plan(),
            current(observed_at="2026-10-09T11:58:00+00:00"),
        )
        self.assertFalse(result.allowed)
        self.assertEqual("evidence_stale", result.reason)
        self.assertTrue(result.refresh_required)

    def test_generation_change_blocks_execution(self):
        result = self.gate.validate(plan(), current(generation_token="gen-8"))
        self.assertFalse(result.allowed)
        self.assertEqual("generation_changed", result.reason)

    def test_capability_revocation_blocks_execution(self):
        result = self.gate.validate(plan(), current(capability_allowed=False))
        self.assertFalse(result.allowed)
        self.assertEqual("capability_not_allowed", result.reason)

    def test_equivalent_recovery_already_completed_blocks_duplicate(self):
        result = self.gate.validate(plan(), current(equivalent_recovery_completed=True))
        self.assertFalse(result.allowed)
        self.assertEqual("equivalent_recovery_completed", result.reason)

    def test_cooldown_or_budget_revalidation_blocks_execution(self):
        result = self.gate.validate(plan(), current(policy_allowed=False))
        self.assertFalse(result.allowed)
        self.assertEqual("policy_not_allowed", result.reason)

    def test_confirmation_must_match_current_recovery_id(self):
        guarded = plan(requires_confirmation=True)
        missing = self.gate.validate(guarded, current())
        self.assertFalse(missing.allowed)
        self.assertEqual("human_confirmation_required", missing.reason)
        wrong = self.gate.validate(
            guarded,
            current(human_confirmation_recovery_id="other"),
        )
        self.assertFalse(wrong.allowed)
        ok = self.gate.validate(
            guarded,
            current(human_confirmation_recovery_id="r1"),
        )
        self.assertTrue(ok.allowed)


if __name__ == "__main__":
    unittest.main()
