from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from .recovery_model import RecoveryPlan


@dataclass(frozen=True)
class DecisionPrecondition:
    name: str
    satisfied: bool
    reason: str


@dataclass(frozen=True)
class PreconditionCheck:
    allowed: bool
    reason: str
    checks: tuple[DecisionPrecondition, ...]
    refresh_required: bool = False


class DecisionPreconditionGate:
    def __init__(
        self,
        *,
        max_evidence_age_s: float,
        clock=lambda: datetime.now(timezone.utc),
    ):
        self.max_evidence_age_s = float(max_evidence_age_s)
        if self.max_evidence_age_s <= 0:
            raise ValueError("max_evidence_age_s must be > 0")
        self.clock = clock

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return timezone-aware datetime")
        return value.astimezone(timezone.utc)

    def _evidence_check(self, current_state: Mapping[str, object]) -> DecisionPrecondition:
        raw = current_state.get("observed_at")
        if not raw:
            return DecisionPrecondition("evidence_fresh", False, "evidence_missing")
        try:
            observed = datetime.fromisoformat(str(raw))
            if observed.tzinfo is None or observed.utcoffset() is None:
                raise ValueError("naive")
            age_s = max(
                0.0,
                (self._now() - observed.astimezone(timezone.utc)).total_seconds(),
            )
        except (TypeError, ValueError):
            return DecisionPrecondition("evidence_fresh", False, "evidence_invalid")
        return DecisionPrecondition(
            "evidence_fresh",
            age_s <= self.max_evidence_age_s,
            "ok" if age_s <= self.max_evidence_age_s else "evidence_stale",
        )

    def validate(
        self,
        plan: RecoveryPlan,
        current_state: Mapping[str, object],
    ) -> PreconditionCheck:
        checks: list[DecisionPrecondition] = []

        target_unhealthy = bool(current_state.get("target_unhealthy", False))
        checks.append(
            DecisionPrecondition(
                "target_unhealthy",
                target_unhealthy,
                "ok" if target_unhealthy else "target_already_healthy",
            )
        )

        checks.append(self._evidence_check(current_state))

        generation_ok = (
            plan.generation_token is None
            or str(current_state.get("generation_token") or "") == plan.generation_token
        )
        checks.append(
            DecisionPrecondition(
                "generation_unchanged",
                generation_ok,
                "ok" if generation_ok else "generation_changed",
            )
        )

        capability_ok = bool(current_state.get("capability_allowed", False))
        checks.append(
            DecisionPrecondition(
                "capability_allowed",
                capability_ok,
                "ok" if capability_ok else "capability_not_allowed",
            )
        )

        duplicate = bool(current_state.get("equivalent_recovery_completed", False))
        checks.append(
            DecisionPrecondition(
                "equivalent_recovery_not_completed",
                not duplicate,
                "equivalent_recovery_completed" if duplicate else "ok",
            )
        )

        policy_ok = bool(current_state.get("policy_allowed", False))
        checks.append(
            DecisionPrecondition(
                "policy_allowed",
                policy_ok,
                "ok" if policy_ok else "policy_not_allowed",
            )
        )

        if plan.requires_confirmation:
            confirmation_ok = (
                str(current_state.get("human_confirmation_recovery_id") or "")
                == plan.recovery_id
            )
            checks.append(
                DecisionPrecondition(
                    "human_confirmation",
                    confirmation_ok,
                    "ok" if confirmation_ok else "human_confirmation_required",
                )
            )

        first_failed = next((item for item in checks if not item.satisfied), None)
        if first_failed is None:
            return PreconditionCheck(True, "ok", tuple(checks), False)
        return PreconditionCheck(
            False,
            first_failed.reason,
            tuple(checks),
            first_failed.reason in {
                "evidence_missing",
                "evidence_invalid",
                "evidence_stale",
                "generation_changed",
            },
        )
