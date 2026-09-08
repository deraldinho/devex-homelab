import unittest

from infrastructure.pentium.atlas.adaptador_stimulus_percepcao import ConfigFontePercepcao
from infrastructure.pentium.atlas.grafo_dependencias import GrafoDependencias
from infrastructure.pentium.atlas.modelo_incidente import IncidenteTecnico
from infrastructure.pentium.atlas.modelo_percepcao import EstadoObservacao, EstadoPercepcao
from infrastructure.pentium.atlas.percepcao import PoliticaConfirmacaoPercepcao
from infrastructure.pentium.atlas.pipeline_percepcao_correlacao import PipelinePercepcaoCorrelacao
from infrastructure.pentium.atlas.stimulus_model import Stimulus, StimulusSeverity


NOW = "2026-09-08T10:30:00+00:00"


def build_pipeline(capacidade_incidentes=2):
    grafo = GrafoDependencias(8)
    configs = {
        "core.agent": ConfigFontePercepcao("core.agent", "core", ("reachable",), 0.8),
        "core.ping": ConfigFontePercepcao("core.ping", "core", ("reachable",), 0.8),
    }
    return PipelinePercepcaoCorrelacao(
        configs, PoliticaConfirmacaoPercepcao(2, 0.95, 8), grafo,
        capacidade_evidencias_por_entidade=8,
        capacidade_incidentes=capacidade_incidentes,
        max_entidades_por_incidente=8,
        id_factory=lambda: "inc-new",
    )


def perception(entity="core", state=EstadoObservacao.INACESSIVEL):
    return EstadoPercepcao(entity, state, 0.9, None, (), ("core.agent",), False, NOW)

def incident(i="inc-old", entity="core"):
    return IncidenteTecnico(
        i, entity, "indisponibilidade_correlacionada", "critical", NOW,
        entity, 1.0, (entity,), 1,
    )


class PipelinePercepcaoRestauracaoTests(unittest.TestCase):
    def test_restaura_percepcao_e_incidente_sem_reaplicar_evento(self):
        pipeline = build_pipeline()
        pipeline.restaurar_estado((perception(),), (incident(),))
        self.assertEqual(("core",), tuple(p.entidade_id for p in pipeline.percepcoes()))
        self.assertEqual(("inc-old",), tuple(i.incidente_id for i in pipeline.incidentes_ativos()))

        stimulus = Stimulus(
            "s-new", "core.agent", "status_changed", StimulusSeverity.INFO,
            NOW, {"reachable": True}, 1.0, "corr",
        )
        resultado = pipeline.processar(stimulus)
        self.assertTrue(resultado.aceito)

    def test_rejeita_percepcao_de_entidade_sem_configuracao(self):
        pipeline = build_pipeline()
        with self.assertRaises(ValueError):
            pipeline.restaurar_estado((perception("unknown"),), ())

    def test_rejeita_incidente_restaurado_acima_da_capacidade(self):
        pipeline = build_pipeline(capacidade_incidentes=1)
        with self.assertRaises(OverflowError):
            pipeline.restaurar_estado((perception(),), (incident("inc-1"), incident("inc-2")))


if __name__ == "__main__":
    unittest.main()
