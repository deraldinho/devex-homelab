import unittest

from infrastructure.pentium.atlas.adaptador_impacto_afetivo import (
    AdaptadorImpactoAfetivo,
    ConfigImpactoAfetivo,
)
from infrastructure.pentium.atlas.modelo_contexto_afetivo import VinculoAfetivo
from infrastructure.pentium.atlas.modelo_incidente import (
    EstadoRecuperacaoIncidente,
    IncidenteTecnico,
)
from infrastructure.pentium.atlas.modelo_percepcao import EstadoObservacao, EstadoPercepcao
from infrastructure.pentium.atlas.pipeline_percepcao_correlacao import ResultadoPipelinePercepcaoCorrelacao
from infrastructure.pentium.atlas.stimulus_model import Stimulus, StimulusSeverity


NOW = "2026-09-08T03:00:00+00:00"


def stimulus(novelty=1.0):
    return Stimulus("s-1", "core.agent", "status_changed", StimulusSeverity.WARNING, NOW, {}, novelty, "c-1", None, "f-1")


def perception(state=EstadoObservacao.OBSERVADO, confidence=0.9):
    return EstadoPercepcao("core", state, confidence, NOW, ("core.agent",), (), False, NOW)


def incident(gravity="critical", recovery=EstadoRecuperacaoIncidente.ABERTO):
    return IncidenteTecnico("inc-1", "core", "indisponibilidade_correlacionada", gravity, NOW, "core", 0.9, ("core",), 1, estado_recuperacao=recovery, recuperado_em=NOW if recovery is EstadoRecuperacaoIncidente.RECUPERADO else None)


def config():
    return ConfigImpactoAfetivo(
        gravidades={"notice": 0.3, "warning": 0.6, "critical": 1.0},
        gravidade_fallback=0.2,
        peso_operacional_minimo=0.2,
        limiar_critico=0.8,
        ganho_estresse_incidente=0.5,
        ganho_ativacao_incidente=0.4,
        perda_valencia_incidente=0.3,
        ganho_ativacao_insegura=0.2,
        ganho_curiosidade_insegura=0.15,
        reducao_estresse_recuperacao=0.5,
        ganho_valencia_recuperacao=0.3,
        ganho_confianca_recuperacao=0.2,
    )


class AdaptadorImpactoAfetivoTests(unittest.TestCase):
    def test_incidente_conhecido_gera_impacto_critico_modulado_por_vinculo(self):
        vinculo = VinculoAfetivo("core", 1.0, 0.8, 1.0, 1.0, 0.6, 0.8)
        result = ResultadoPipelinePercepcaoCorrelacao(True, perception(EstadoObservacao.INACESSIVEL), (incident(),))
        impacto = AdaptadorImpactoAfetivo(config()).derivar(stimulus(), result, vinculo, 0.25)
        self.assertTrue(impacto.contexto_emocional.criticidade_relevante)
        self.assertGreater(impacto.impulso.delta_estresse, 0.0)
        self.assertGreater(impacto.impulso.delta_ativacao, 0.0)
        self.assertLess(impacto.impulso.delta_valencia, 0.0)
        self.assertEqual("inc-1", impacto.assunto.assunto_id)

    def test_percepcao_insegura_sem_incidente_aumenta_vigilancia_sem_criticidade(self):
        result = ResultadoPipelinePercepcaoCorrelacao(True, perception(EstadoObservacao.PARCIALMENTE_OBSERVADO, 0.5), ())
        impacto = AdaptadorImpactoAfetivo(config()).derivar(stimulus(0.4), result, None, 0.0)
        self.assertTrue(impacto.contexto_emocional.percepcao_insegura)
        self.assertFalse(impacto.contexto_emocional.criticidade_relevante)
        self.assertGreater(impacto.impulso.delta_ativacao, 0.0)
        self.assertGreater(impacto.impulso.delta_curiosidade, 0.0)
        self.assertEqual("observacao:core", impacto.assunto.assunto_id)

    def test_recuperacao_reduz_estresse_e_marca_contexto(self):
        result = ResultadoPipelinePercepcaoCorrelacao(True, perception(), (incident(recovery=EstadoRecuperacaoIncidente.RECUPERADO),))
        impacto = AdaptadorImpactoAfetivo(config()).derivar(stimulus(), result, None, 0.0)
        self.assertTrue(impacto.contexto_emocional.recuperacao_relevante)
        self.assertLess(impacto.impulso.delta_estresse, 0.0)
        self.assertGreater(impacto.impulso.delta_valencia, 0.0)
        self.assertGreater(impacto.impulso.delta_confianca, 0.0)
        self.assertTrue(impacto.assunto.recuperado)

    def test_gravidade_desconhecida_usa_fallback_conservador(self):
        result = ResultadoPipelinePercepcaoCorrelacao(True, perception(EstadoObservacao.INACESSIVEL), (incident("mystery"),))
        impacto = AdaptadorImpactoAfetivo(config()).derivar(stimulus(), result, None, 0.0)
        self.assertAlmostEqual(0.2, impacto.assunto.gravidade)
        self.assertFalse(impacto.contexto_emocional.criticidade_relevante)
        self.assertLessEqual(impacto.assunto.impacto_afetivo, 0.2)

    def test_reincidencia_e_repassada_bounded_para_a4(self):
        result = ResultadoPipelinePercepcaoCorrelacao(True, perception(), ())
        impacto = AdaptadorImpactoAfetivo(config()).derivar(stimulus(), result, None, 2.0)
        self.assertEqual(1.0, impacto.contexto_emocional.reincidencia)


if __name__ == "__main__":
    unittest.main()
