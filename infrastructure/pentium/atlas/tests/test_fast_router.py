from pathlib import Path
import unittest

from infrastructure.pentium.atlas.configuracao_fast_router import carregar_politica_fast_router
from infrastructure.pentium.atlas.fast_router import FastRouter
from infrastructure.pentium.atlas.modelo_evento_semantico import (
    EntidadeSemantica,
    EstadoSemantico,
    EventoSemantico,
    TipoEventoSemantico,
)
from infrastructure.pentium.atlas.modelo_fast_router import RotaSemantica
from infrastructure.pentium.atlas.stimulus_model import StimulusSeverity


ROOT = Path(__file__).resolve().parents[1]


def evento(
    tipo: TipoEventoSemantico,
    estado: EstadoSemantico,
    severidade: StimulusSeverity,
    novidade: float,
    *,
    entidade: EntidadeSemantica = EntidadeSemantica.CORE,
) -> EventoSemantico:
    return EventoSemantico(
        entity=entidade,
        event=tipo,
        state=estado,
        severity=severidade,
        novelty=novidade,
        correlation_id="corr-1",
        attributes={},
    )


class FastRouterTests(unittest.TestCase):
    def setUp(self):
        politica = carregar_politica_fast_router(ROOT / "config_fast_router.json")
        self.router = FastRouter(politica)

    def test_baseline_saudavel_e_trivial_vai_para_drop(self):
        decisao = self.router.decidir(evento(
            TipoEventoSemantico.OBSERVED,
            EstadoSemantico.HEALTHY,
            StimulusSeverity.INFO,
            1.0,
        ))
        self.assertEqual(decisao.rotas, (RotaSemantica.DROP,))
        self.assertEqual(decisao.score, 0.15)

    def test_critico_vai_direto_para_reacao_e_afeto_sem_llm_ou_cache(self):
        decisao = self.router.decidir(evento(
            TipoEventoSemantico.STATE_CHANGED,
            EstadoSemantico.CRITICAL,
            StimulusSeverity.CRITICAL,
            1.0,
        ))
        self.assertEqual(
            decisao.rotas,
            (RotaSemantica.FAST_REACTION, RotaSemantica.AFFECT),
        )

    def test_recovery_de_host_e_reacao_de_alivio_direta(self):
        decisao = self.router.decidir(evento(
            TipoEventoSemantico.RECOVERED,
            EstadoSemantico.HEALTHY,
            StimulusSeverity.NOTICE,
            1.0,
        ))
        self.assertEqual(
            decisao.rotas,
            (RotaSemantica.FAST_REACTION, RotaSemantica.AFFECT),
        )

    def test_evento_conhecido_de_baixa_novidade_prefere_cache(self):
        decisao = self.router.decidir(evento(
            TipoEventoSemantico.STATE_CHANGED,
            EstadoSemantico.DEGRADED,
            StimulusSeverity.WARNING,
            0.10,
        ))
        self.assertEqual(
            decisao.rotas,
            (RotaSemantica.AFFECT, RotaSemantica.CACHE_LOOKUP),
        )

    def test_evento_novo_de_score_alto_vai_fast_sem_llm(self):
        decisao = self.router.decidir(evento(
            TipoEventoSemantico.STATE_CHANGED,
            EstadoSemantico.DEGRADED,
            StimulusSeverity.WARNING,
            1.0,
        ))
        self.assertEqual(
            decisao.rotas,
            (RotaSemantica.FAST_REACTION, RotaSemantica.AFFECT),
        )
        self.assertAlmostEqual(decisao.score, 0.80)

    def test_evento_novo_ambiguo_defer_para_slow_llm_sem_bloquear_afeto(self):
        decisao = self.router.decidir(evento(
            TipoEventoSemantico.STATE_CHANGED,
            EstadoSemantico.ACTIVE,
            StimulusSeverity.NOTICE,
            1.0,
        ))
        self.assertEqual(
            decisao.rotas,
            (RotaSemantica.AFFECT, RotaSemantica.SLOW_LLM),
        )
        self.assertAlmostEqual(decisao.score, 0.45)

    def test_presenca_wifi_nao_acorda_llm_na_s2(self):
        decisao = self.router.decidir(evento(
            TipoEventoSemantico.PRESENCE_MISSING,
            EstadoSemantico.MISSING,
            StimulusSeverity.INFO,
            1.0,
            entidade=EntidadeSemantica.WIFI_ZONE,
        ))
        self.assertEqual(decisao.rotas, (RotaSemantica.AFFECT,))
        self.assertNotIn(RotaSemantica.SLOW_LLM, decisao.rotas)


if __name__ == "__main__":
    unittest.main()
