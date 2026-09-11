import unittest

from infrastructure.pentium.atlas.adaptador_stimulus_percepcao import ConfigFontePercepcao
from infrastructure.pentium.atlas.grafo_dependencias import GrafoDependencias
from infrastructure.pentium.atlas.modelo_percepcao import EstadoObservacao
from infrastructure.pentium.atlas.percepcao import PoliticaConfirmacaoPercepcao
from infrastructure.pentium.atlas.pipeline_percepcao_correlacao import PipelinePercepcaoCorrelacao
from infrastructure.pentium.atlas.stimulus_model import Stimulus, StimulusSeverity


def stim(sid, source, kind="status_changed", payload=None):
    return Stimulus(
        sid, source, kind, StimulusSeverity.CRITICAL,
        "2026-09-04T12:00:00+00:00", payload or {"status": "critical"},
        1.0, "corr-1",
    )


class PipelinePercepcaoCorrelacaoTests(unittest.TestCase):
    def setUp(self):
        grafo = GrafoDependencias(16)
        grafo.adicionar_dependencia("core", "firewall")
        configs = {
            "core.agent": ConfigFontePercepcao("core.agent", "core", ("reachable",), 0.8),
            "core.ping": ConfigFontePercepcao("core.ping", "core", ("reachable",), 0.8),
        }
        self.pipeline = PipelinePercepcaoCorrelacao(
            configs, PoliticaConfirmacaoPercepcao(2, 0.95, 8), grafo,
            capacidade_evidencias_por_entidade=8, capacidade_incidentes=8,
            max_entidades_por_incidente=8, id_factory=lambda: "inc-1",
        )

    def test_source_error_isolado_nao_cria_incidente_de_perda(self):
        original = stim("s1", "core.agent", kind="source_error")
        antes = original.to_dict()
        resultado = self.pipeline.processar(original)
        self.assertEqual(EstadoObservacao.PARCIALMENTE_OBSERVADO, resultado.percepcao.estado)
        self.assertEqual((), resultado.incidentes)
        self.assertEqual(antes, original.to_dict())

    def test_duas_evidencias_independentes_confirmam_e_criam_incidente(self):
        self.pipeline.processar(stim("s1", "core.agent", payload={"reachable": False}))
        resultado = self.pipeline.processar(stim("s2", "core.ping", payload={"reachable": False}))
        self.assertEqual(EstadoObservacao.INACESSIVEL, resultado.percepcao.estado)
        self.assertEqual("core", resultado.incidentes[0].entidade_principal)

    def test_stimulus_id_duplicado_e_idempotente(self):
        primeiro = self.pipeline.processar(stim("s1", "core.agent", payload={"reachable": True}))
        segundo = self.pipeline.processar(stim("s1", "core.agent", payload={"reachable": False}))
        self.assertTrue(primeiro.aceito)
        self.assertFalse(segundo.aceito)
        self.assertEqual(EstadoObservacao.OBSERVADO, segundo.percepcao.estado)


if __name__ == "__main__":
    unittest.main()


class PipelineEpisodicSinkTests(unittest.TestCase):
    def build_pipeline(self, sink=None):
        grafo = GrafoDependencias(16)
        configs = {
            "core.agent": ConfigFontePercepcao("core.agent", "core", ("reachable",), 0.8),
        }
        return PipelinePercepcaoCorrelacao(
            configs, PoliticaConfirmacaoPercepcao(1, 0.95, 8), grafo,
            capacidade_evidencias_por_entidade=8, capacidade_incidentes=8,
            max_entidades_por_incidente=8, id_factory=lambda: "inc-1",
            episodic_sink=sink,
        )

    def test_duplicate_stimulus_does_not_emit_episode_twice(self):
        seen = []
        pipeline = self.build_pipeline(seen.append)
        event = stim("s1", "core.agent", payload={"reachable": True})
        pipeline.processar(event)
        pipeline.processar(event)
        self.assertEqual(1, len(seen))
        self.assertTrue(seen[0].aceito)

    def test_sink_failure_does_not_break_perception(self):
        def fail(_result):
            raise RuntimeError("episodic down")

        result = self.build_pipeline(fail).processar(
            stim("s1", "core.agent", payload={"reachable": True})
        )
        self.assertTrue(result.aceito)
        self.assertEqual(EstadoObservacao.OBSERVADO, result.percepcao.estado)
