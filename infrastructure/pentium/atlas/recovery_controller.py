from __future__ import annotations

import time
from typing import Mapping

from .decision_preconditions import DecisionPreconditionGate
from .recovery_model import RecoveryPlan, RecoveryResult, RecoveryState


class RecoveryController:
    def __init__(
        self,
        precondition_gate: DecisionPreconditionGate,
        *,
        current_state_provider,
        policy_evaluator,
        executor,
        verifier,
        monotonic=time.monotonic,
    ):
        self._precondition_gate = precondition_gate
        self._current_state_provider = current_state_provider
        self._policy_evaluator = policy_evaluator
        self._executor = executor
        self._verifier = verifier
        self._monotonic = monotonic
        self._active: set[str] = set()
        self._failure_counts: dict[str, int] = {}
        self._last_success: dict[str, float] = {}

    @staticmethod
    def _arguments(plan: RecoveryPlan) -> dict[str, object]:
        if plan.capability in {"start_service", "stop_service", "restart_service"}:
            return {"host": plan.host, "service": plan.target}
        if plan.capability == "restart_container":
            return {"host": plan.host, "container": plan.target}
        if plan.capability == "reboot_host":
            return {"host": plan.host}
        raise PermissionError("unsupported_recovery_capability")

    @staticmethod
    def _authorized(decision) -> bool:
        if isinstance(decision, bool):
            return decision
        return bool(getattr(decision, "autorizada", False))

    @staticmethod
    def _verification(value) -> tuple[bool, tuple[str, ...]]:
        if isinstance(value, tuple) and len(value) == 2:
            ok, refs = value
            return bool(ok), tuple(str(item) for item in refs)
        return bool(value), ()

    @staticmethod
    def _result(
        plan: RecoveryPlan,
        state: RecoveryState,
        attempts: int,
        transitions: list[RecoveryState],
        *,
        reason: str,
        evidence_refs=(),
    ) -> RecoveryResult:
        return RecoveryResult(
            recovery_id=plan.recovery_id,
            state=state,
            attempts=attempts,
            reason=reason,
            evidence_refs=tuple(evidence_refs),
            transitions=tuple(transitions),
        )

    def recover(self, plan: RecoveryPlan) -> RecoveryResult:
        key = plan.recovery_key
        transitions = [RecoveryState.PLANNED]
        failures = self._failure_counts.get(key, 0)
        now = float(self._monotonic())

        if key in self._active:
            transitions.append(RecoveryState.BLOCKED)
            return self._result(
                plan, RecoveryState.BLOCKED, failures, transitions,
                reason="recovery_already_active",
                evidence_refs=plan.evidence_refs,
            )

        last_success = self._last_success.get(key)
        if last_success is not None and (now - last_success) < plan.cooldown_s:
            transitions.append(RecoveryState.COOLDOWN)
            return self._result(
                plan, RecoveryState.COOLDOWN, failures, transitions,
                reason="cooldown_active",
                evidence_refs=plan.evidence_refs,
            )

        if failures >= plan.max_attempts:
            transitions.append(RecoveryState.ESCALATED)
            return self._result(
                plan, RecoveryState.ESCALATED, failures, transitions,
                reason="max_attempts_exceeded",
                evidence_refs=plan.evidence_refs,
            )

        current_state: Mapping[str, object] = self._current_state_provider(plan)
        preconditions = self._precondition_gate.validate(plan, current_state)
        if not preconditions.allowed:
            terminal = (
                RecoveryState.REFRESH_REQUIRED
                if preconditions.refresh_required
                else RecoveryState.BLOCKED
            )
            transitions.append(terminal)
            return self._result(
                plan, terminal, failures, transitions,
                reason=preconditions.reason,
                evidence_refs=plan.evidence_refs,
            )

        arguments = self._arguments(plan)
        decision = self._policy_evaluator(plan.capability, arguments)
        if not self._authorized(decision):
            transitions.append(RecoveryState.BLOCKED)
            return self._result(
                plan, RecoveryState.BLOCKED, failures, transitions,
                reason=str(getattr(decision, "razao", "policy_denied")),
                evidence_refs=plan.evidence_refs,
            )

        transitions.append(RecoveryState.AUTHORIZED)
        self._active.add(key)
        attempt = failures + 1
        try:
            transitions.append(RecoveryState.EXECUTING)
            try:
                execution_result = self._executor(
                    plan.capability, arguments, None, None
                )
            except Exception as exc:
                self._failure_counts[key] = attempt
                transitions.append(RecoveryState.FAILED)
                return self._result(
                    plan, RecoveryState.FAILED, attempt, transitions,
                    reason=f"execution_failed:{type(exc).__name__}",
                    evidence_refs=plan.evidence_refs,
                )

            transitions.append(RecoveryState.VERIFYING)
            try:
                verified, verification_refs = self._verification(
                    self._verifier(plan, execution_result)
                )
            except Exception as exc:
                verified = False
                verification_refs = (f"verification_error:{type(exc).__name__}",)

            combined_refs = tuple(plan.evidence_refs) + tuple(verification_refs)
            if not verified:
                self._failure_counts[key] = attempt
                transitions.append(RecoveryState.FAILED)
                return self._result(
                    plan, RecoveryState.FAILED, attempt, transitions,
                    reason="postcondition_failed",
                    evidence_refs=combined_refs,
                )

            self._failure_counts[key] = 0
            self._last_success[key] = float(self._monotonic())
            transitions.append(RecoveryState.RECOVERED)
            return self._result(
                plan, RecoveryState.RECOVERED, attempt, transitions,
                reason="verified_recovery",
                evidence_refs=combined_refs,
            )
        finally:
            self._active.discard(key)
