from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .continuous_intent import IntentType


def _unit(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, number))


@dataclass(frozen=True)
class BehaviorDecision:
    tipo: IntentType
    assunto_id: str
    entidade_id: str
    motivo: str
    prioridade: float
    utility: float


class BehaviorSelector:
    def select(self, snapshot: Any, *, human_interaction: bool, habituation: float) -> BehaviorDecision:
        focus = dict(getattr(snapshot, "focus", {}) or {})
        principal = dict(focus.get("principal") or {})
        assunto = str(principal.get("assunto_id") or getattr(snapshot, "entity_id", "sistema"))
        entidade = str(principal.get("entidade_id") or getattr(snapshot, "entity_id", assunto))
        if human_interaction:
            return BehaviorDecision(IntentType.INTERAGIR_COM_HUMANO, assunto, entidade, "interacao_humana", 1.0, 1.0)

        if bool(principal.get("recuperado", False)):
            return BehaviorDecision(IntentType.ENCERRAR_ACOMPANHAMENTO, assunto, entidade, "recuperacao", .95, .95)

        if bool(principal.get("self_work_candidate", False)) and not getattr(snapshot, "incident", None):
            novelty = _unit(principal.get("novidade"))
            importance = _unit(principal.get("importancia"))
            confidence = _unit(dict(getattr(snapshot, "perception", {}) or {}).get("confianca"), .5)
            utility = max(0.0, min(1.0, .40 * novelty + .35 * importance + .25 * confidence))
            return BehaviorDecision(IntentType.SELF_WORK, assunto, entidade, "self_work_candidate", max(.2, utility), utility)

        relevance = sum(_unit(principal.get(key)) for key in ("gravidade", "importancia", "urgencia", "novidade")) / 4.0
        benefit = (_unit(principal.get("impacto_afetivo")) + _unit(principal.get("recencia"), 1.0)) / 2.0
        perception = dict(getattr(snapshot, "perception", {}) or {})
        confidence = _unit(perception.get("confianca"), .5)
        affective = dict(getattr(snapshot, "affective_state", {}) or {})
        interruption_cost = _unit(affective.get("estresse"), 0.0)
        habituation_penalty = _unit(habituation)
        utility = max(0.0, min(1.0,
            .40 * relevance + .25 * benefit + .25 * confidence
            - .05 * interruption_cost - .20 * habituation_penalty
        ))
        incident = getattr(snapshot, "incident", None)
        degraded = bool(incident) or bool(principal.get("critico")) or _unit(principal.get("gravidade")) >= .5
        tipo = IntentType.ACOMPANHAR_RECUPERACAO if degraded else IntentType.OBSERVAR
        motivo = "degraded" if degraded else "observacao"
        prioridade = max(utility, .6 if degraded else .2)
        return BehaviorDecision(tipo, assunto, entidade, motivo, min(1.0, prioridade), utility)
