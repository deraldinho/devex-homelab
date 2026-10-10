import unittest
from dataclasses import dataclass
from datetime import datetime, timezone

from infrastructure.pentium.atlas.decision_preconditions import DecisionPreconditionGate
from infrastructure.pentium.atlas.recovery_controller import RecoveryController
from infrastructure.pentium.atlas.recovery_model import RecoveryPlan, RecoveryRisk, RecoveryState


NOW = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)


@dataclass
class Decision:
    autorizada: bool


def plan(**overrides):
    payload = dict(
        recovery_id="r1",
        host="core",
        target="atlas-worker.service",
        capability="restart_service",
        risk=RecoveryRisk.SAFE_CONTROL,
        reversible=True,
        expected_postconditions=("service_healthy",),
        max_attempts=1,
        cooldown_s=60.0,
        timeout_s=15.0,
        evidence_refs=("health:event-1",),
    )
    payload.update(overrides)
    return RecoveryPlan(**payload)


def current(**overrides):
    payload = dict(
        target_unhealthy=True,
        observed_at="2026-10-09T11:59:50+00:00",
        generation_token=None,
        capability_allowed=True,
        equivalent_recovery_completed=False,
        policy_allowed=True,
        human_confirmation_recovery_id=None,
    )
    payload.update(overrides)
    return payload


class RecoveryControllerTests(unittest.TestCase):
    def build(
        self,
        *,
        state=None,
        policy=True,
        executor=None,
        verifier=None,
        monotonic=lambda: 1000.0,
    ):
        state = current() if state is None else state
        executor_calls = []
        def default_executor(capability, arguments, plan_obj, action):
            executor_calls.append((capability, dict(arguments)))
            return {"status": "success"}
        actual_executor = executor or default_executor
        controller = RecoveryController(
            DecisionPreconditionGate(max_evidence_age_s=30, clock=lambda: NOW),
            current_state_provider=lambda recovery_plan: dict(state),
            policy_evaluator=lambda capability, arguments: Decision(policy),
            executor=actual_executor,
            verifier=verifier or (lambda recovery_plan, result: (True, ("verify:ok",))),
            monotonic=monotonic,
        )
        return controller, executor_calls

    def test_success_runs_full_verified_lifecycle(self):
        controller, calls = self.build()
        result = controller.recover(plan())
        self.assertEqual(RecoveryState.RECOVERED, result.state)
        self.assertEqual(
            (
                RecoveryState.PLANNED,
                RecoveryState.AUTHORIZED,
                RecoveryState.EXECUTING,
                RecoveryState.VERIFYING,
                RecoveryState.RECOVERED,
            ),
            result.transitions,
        )
        self.assertEqual(1, len(calls))
        self.assertIn("verify:ok", result.evidence_refs)

    def test_policy_deny_blocks_without_execution(self):
        controller, calls = self.build(policy=False)
        result = controller.recover(plan())
        self.assertEqual(RecoveryState.BLOCKED, result.state)
        self.assertEqual([], calls)

    def test_stale_precondition_requires_refresh_without_execution(self):
        controller, calls = self.build(
            state=current(observed_at="2026-10-09T11:58:00+00:00")
        )
        result = controller.recover(plan())
        self.assertEqual(RecoveryState.REFRESH_REQUIRED, result.state)
        self.assertEqual([], calls)

    def test_executor_failure_is_failed_and_never_recovered(self):
        def failing(*args):
            raise RuntimeError("command failed")
        controller, _ = self.build(executor=failing)
        result = controller.recover(plan())
        self.assertEqual(RecoveryState.FAILED, result.state)
        self.assertNotIn(RecoveryState.RECOVERED, result.transitions)

    def test_command_success_with_failed_postcondition_is_failed(self):
        controller, _ = self.build(verifier=lambda recovery_plan, result: (False, ("verify:failed",)))
        result = controller.recover(plan())
        self.assertEqual(RecoveryState.FAILED, result.state)
        self.assertEqual(RecoveryState.VERIFYING, result.transitions[-2])
        self.assertNotIn(RecoveryState.RECOVERED, result.transitions)

    def test_failure_budget_escalates_on_next_attempt(self):
        def failing(*args):
            raise RuntimeError("command failed")
        controller, _ = self.build(executor=failing)
        first = controller.recover(plan(max_attempts=1))
        second = controller.recover(plan(max_attempts=1))
        self.assertEqual(RecoveryState.FAILED, first.state)
        self.assertEqual(RecoveryState.ESCALATED, second.state)

    def test_successful_recovery_enters_cooldown_and_blocks_duplicate(self):
        controller, _ = self.build(monotonic=lambda: 1000.0)
        first = controller.recover(plan(cooldown_s=60))
        second = controller.recover(plan(cooldown_s=60))
        self.assertEqual(RecoveryState.RECOVERED, first.state)
        self.assertEqual(RecoveryState.COOLDOWN, second.state)

    def test_capability_arguments_are_typed_from_recovery_plan(self):
        controller, calls = self.build()
        controller.recover(plan())
        self.assertEqual(
            [("restart_service", {"host": "core", "service": "atlas-worker.service"})],
            calls,
        )


if __name__ == "__main__":
    unittest.main()
