from __future__ import annotations

from .configuracao_fast_router import PoliticaFastRouter
from .modelo_evento_semantico import (
    EstadoSemantico,
    EventoSemantico,
    TipoEventoSemantico,
)
from .modelo_fast_router import DecisaoFastRouter, RotaSemantica
from .stimulus_model import StimulusSeverity


_SEVERIDADE_SCORE = {
    StimulusSeverity.INFO: 0.10,
    StimulusSeverity.NOTICE: 0.30,
    StimulusSeverity.WARNING: 0.65,
    StimulusSeverity.CRITICAL: 1.00,
}

_EVENTO_BOOST = {
    TipoEventoSemantico.OBSERVED: 0.00,
    TipoEventoSemantico.STATE_CHANGED: 0.10,
    TipoEventoSemantico.RECOVERED: 0.15,
    TipoEventoSemantico.SOURCE_ERROR: 0.15,
    TipoEventoSemantico.PRESENCE_APPEARED: 0.05,
    TipoEventoSemantico.PRESENCE_MISSING: 0.10,
    TipoEventoSemantico.PRESENCE_RECOVERED: 0.10,
    TipoEventoSemantico.PRESENCE_CHANGED: 0.05,
}


class FastRouter:
    def __init__(self, politica: PoliticaFastRouter):
        self._politica = politica

    @staticmethod
    def _score(evento: EventoSemantico) -> float:
        score = (
            _SEVERIDADE_SCORE[evento.severity]
            + _EVENTO_BOOST[evento.event]
            + min(1.0, evento.novelty) * 0.05
        )
        return round(max(0.0, min(1.0, score)), 6)

    def decidir(self, evento: EventoSemantico) -> DecisaoFastRouter:
        score = self._score(evento)
        politica = self._politica

        if (
            evento.event is TipoEventoSemantico.OBSERVED
            and evento.state in {EstadoSemantico.HEALTHY, EstadoSemantico.PRESENT}
            and score <= politica.drop_score_max
        ):
            return DecisaoFastRouter((RotaSemantica.DROP,), "baseline_trivial", score)

        if evento.state is EstadoSemantico.CRITICAL or evento.severity is StimulusSeverity.CRITICAL:
            return DecisaoFastRouter(
                (RotaSemantica.FAST_REACTION, RotaSemantica.AFFECT),
                "critico_direto",
                score,
            )

        if evento.event is TipoEventoSemantico.RECOVERED:
            return DecisaoFastRouter(
                (RotaSemantica.FAST_REACTION, RotaSemantica.AFFECT),
                "recuperacao_direta",
                score,
            )

        if evento.novelty <= politica.cache_novelty_max:
            return DecisaoFastRouter(
                (RotaSemantica.AFFECT, RotaSemantica.CACHE_LOOKUP),
                "evento_conhecido_cache",
                score,
            )

        if score >= politica.fast_reaction_score_min:
            return DecisaoFastRouter(
                (RotaSemantica.FAST_REACTION, RotaSemantica.AFFECT),
                "score_alto_direto",
                score,
            )

        slow_eligible = evento.event in {
            TipoEventoSemantico.STATE_CHANGED,
            TipoEventoSemantico.SOURCE_ERROR,
        }
        if (
            slow_eligible
            and evento.novelty >= politica.slow_llm_novelty_min
            and politica.slow_llm_score_min <= score <= politica.slow_llm_score_max
        ):
            return DecisaoFastRouter(
                (RotaSemantica.AFFECT, RotaSemantica.SLOW_LLM),
                "ambiguidade_slow_llm",
                score,
            )

        return DecisaoFastRouter((RotaSemantica.AFFECT,), "afetivo_sem_escalada", score)
