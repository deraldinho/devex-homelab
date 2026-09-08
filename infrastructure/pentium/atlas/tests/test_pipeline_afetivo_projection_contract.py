import unittest

from infrastructure.pentium.atlas.modelo_incidente import EstadoRecuperacaoIncidente
from infrastructure.pentium.atlas.pipeline_percepcao_correlacao import ResultadoPipelinePercepcaoCorrelacao
from infrastructure.pentium.atlas.tests.test_pipeline_afetivo_observacional import (
    impact, incident, make_pipeline, perception, stim,
)


class PipelineAfetivoProjectionContractTest(unittest.TestCase):
    def test_accepted_result_exposes_exact_a3_result(self):
        a3_result = ResultadoPipelinePercepcaoCorrelacao(
            True, perception(), (incident(EstadoRecuperacaoIncidente.ABERTO),))
        pipeline, *_ = make_pipeline([a3_result], [impact()])
        processed = pipeline.processar(stim("s-a3"))
        self.assertIs(processed.resultado_percepcao, a3_result)

    def test_recovery_result_keeps_same_event_incident(self):
        recovered = ResultadoPipelinePercepcaoCorrelacao(
            True, perception(), (incident(EstadoRecuperacaoIncidente.RECUPERADO),))
        pipeline, *_ = make_pipeline([recovered], [impact(True)])
        processed = pipeline.processar(stim("s-recovery"))
        self.assertEqual("recuperado", processed.resultado_percepcao.incidentes[0].estado_recuperacao.value)
        self.assertEqual("inc-1", processed.resultado_percepcao.incidentes[0].incidente_id)


if __name__ == "__main__":
    unittest.main()
