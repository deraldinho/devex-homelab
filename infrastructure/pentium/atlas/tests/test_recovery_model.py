import unittest

from infrastructure.pentium.atlas.recovery_model import (
    RecoveryPlan,
    RecoveryRisk,
    RecoveryState,
)


class RecoveryModelTests(unittest.TestCase):
    def make_plan(self, **overrides):
        payload = dict(
            recovery_id="r1",
            host="x99",
            target="atlas-worker",
            capability="restart_container",
            risk=RecoveryRisk.SAFE_CONTROL,
            reversible=True,
            expected_postconditions=("container_running",),
            max_attempts=2,
            cooldown_s=60.0,
            timeout_s=15.0,
        )
        payload.update(overrides)
        return RecoveryPlan(**payload)

    def test_recovery_plan_requires_identity_target_capability_and_postcondition(self):
        for field in ("recovery_id", "host", "target", "capability"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    self.make_plan(**{field: ""})
        with self.assertRaises(ValueError):
            self.make_plan(expected_postconditions=())

    def test_recovery_plan_requires_positive_attempts_cooldown_and_timeout(self):
        with self.assertRaises(ValueError):
            self.make_plan(max_attempts=0)
        with self.assertRaises(ValueError):
            self.make_plan(cooldown_s=0)
        with self.assertRaises(ValueError):
            self.make_plan(timeout_s=0)

    def test_recovery_key_is_host_capability_target_scoped(self):
        plan = self.make_plan()
        self.assertEqual("x99:restart_container:atlas-worker", plan.recovery_key)

    def test_recovery_states_cover_verified_lifecycle_and_escalation(self):
        expected = {
            "PLANNED", "AUTHORIZED", "EXECUTING", "VERIFYING", "RECOVERED",
            "BLOCKED", "REFRESH_REQUIRED", "FAILED", "ESCALATED", "COOLDOWN",
        }
        self.assertTrue(expected.issubset({item.name for item in RecoveryState}))


if __name__ == "__main__":
    unittest.main()
