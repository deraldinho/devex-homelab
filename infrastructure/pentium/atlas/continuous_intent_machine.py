from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Callable
import uuid

from .behavior_selector import BehaviorDecision
from .continuous_intent import ContinuousIntent, IntentState, IntentType


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("now must include timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class IntentTransition:
    intent: ContinuousIntent | None
    previous_state: IntentState | None
    changed: bool


class ContinuousIntentMachine:
    def __init__(self, *, ttl_s: float = 300.0, activation_threshold: float = .5,
                 id_factory: Callable[[], str] | None = None):
        if ttl_s <= 0 or not 0.0 <= activation_threshold <= 1.0:
            raise ValueError("invalid intent machine bounds")
        self._ttl_s = float(ttl_s)
        self._threshold = float(activation_threshold)
        self._id_factory = id_factory or (lambda: str(uuid.uuid4()))
        self._current: ContinuousIntent | None = None

    @property
    def current(self) -> ContinuousIntent | None:
        return self._current

    def _new_intent(self, decision: BehaviorDecision, now: str) -> ContinuousIntent:
        instant = _parse_utc(now)
        return ContinuousIntent(
            self._id_factory(), decision.tipo, IntentState.ATIVA,
            decision.assunto_id, decision.entidade_id, decision.motivo,
            decision.prioridade, instant.isoformat(), instant.isoformat(),
            (instant + timedelta(seconds=self._ttl_s)).isoformat(),
        )

    def _terminal(self, state: IntentState, now: str) -> IntentTransition:
        current = self._current
        if current is None:
            return IntentTransition(None, None, False)
        result = replace(current, estado=state, atualizado_em=_parse_utc(now).isoformat())
        self._current = None
        return IntentTransition(result, current.estado, True)

    def update(self, decision: BehaviorDecision, snapshot, *, now: str,
               human_interaction: bool = False) -> IntentTransition:
        instant = _parse_utc(now)
        current = self._current

        if current is not None and instant > _parse_utc(current.valido_ate):
            return self._terminal(IntentState.EXPIRADA, now)

        if human_interaction or decision.tipo is IntentType.INTERAGIR_COM_HUMANO:
            if current is None:
                return IntentTransition(None, None, False)
            if current.estado is IntentState.AGUARDANDO:
                return IntentTransition(current, current.estado, False)
            updated = replace(current, estado=IntentState.AGUARDANDO, atualizado_em=instant.isoformat())
            self._current = updated
            return IntentTransition(updated, current.estado, True)

        if current is None:
            if decision.tipo is IntentType.ENCERRAR_ACOMPANHAMENTO:
                return IntentTransition(None, None, False)
            if decision.prioridade < self._threshold:
                return IntentTransition(None, None, False)
            created = self._new_intent(decision, now)
            self._current = created
            return IntentTransition(created, IntentState.CANDIDATA, True)

        if decision.assunto_id != current.assunto_id:
            return self._terminal(IntentState.CANCELADA, now)

        if decision.tipo is IntentType.ENCERRAR_ACOMPANHAMENTO:
            return self._terminal(IntentState.CONCLUIDA, now)

        if current.estado is IntentState.AGUARDANDO:
            resumed = replace(
                current, estado=IntentState.ATIVA,
                atualizado_em=instant.isoformat(), prioridade=decision.prioridade,
                motivo=decision.motivo,
            )
            self._current = resumed
            return IntentTransition(resumed, current.estado, True)

        updated = replace(
            current, atualizado_em=instant.isoformat(), prioridade=decision.prioridade,
            motivo=decision.motivo,
        )
        self._current = updated
        return IntentTransition(updated, current.estado, updated != current)
