import unittest

from infrastructure.pentium.atlas.modelo_percepcao import EvidenciaPercepcao, EstadoObservacao, ResultadoEvidencia
from infrastructure.pentium.atlas.percepcao import PoliticaConfirmacaoPercepcao, consolidar_percepcao


class PercepcaoTests(unittest.TestCase):
    def setUp(self):
        self.politica = PoliticaConfirmacaoPercepcao(2, 0.95, 4)

    def ev(self, eid, fonte, resultado, confianca=0.8, conclusiva=False, t="2026-09-04T12:00:00+00:00"):
        return EvidenciaPercepcao(eid, "core", fonte, resultado, confianca, t, conclusiva)

    def test_sem_evidencia_e_desconhecido(self):
        estado = consolidar_percepcao("core", (), self.politica, "2026-09-04T12:00:00+00:00")
        self.assertEqual(EstadoObservacao.DESCONHECIDO, estado.estado)

    def test_observacao_valida_e_observado(self):
        estado = consolidar_percepcao("core", (self.ev("1", "ping", ResultadoEvidencia.DISPONIVEL),), self.politica, "2026-09-04T12:01:00+00:00")
        self.assertEqual(EstadoObservacao.OBSERVADO, estado.estado)

    def test_uma_indisponibilidade_isolada_e_parcial(self):
        estado = consolidar_percepcao("core", (self.ev("1", "ping", ResultadoEvidencia.INDISPONIVEL),), self.politica, "2026-09-04T12:01:00+00:00")
        self.assertEqual(EstadoObservacao.PARCIALMENTE_OBSERVADO, estado.estado)

    def test_duas_fontes_independentes_confirmam_inacessivel(self):
        evidencias = (
            self.ev("1", "ping", ResultadoEvidencia.INDISPONIVEL, 0.9),
            self.ev("2", "ssh", ResultadoEvidencia.INDISPONIVEL, 0.9),
        )
        estado = consolidar_percepcao("core", evidencias, self.politica, "2026-09-04T12:01:00+00:00")
        self.assertEqual(EstadoObservacao.INACESSIVEL, estado.estado)

    def test_disponivel_e_indisponivel_gera_conflito_parcial(self):
        evidencias = (
            self.ev("1", "ping", ResultadoEvidencia.DISPONIVEL),
            self.ev("2", "ssh", ResultadoEvidencia.INDISPONIVEL),
        )
        estado = consolidar_percepcao("core", evidencias, self.politica, "2026-09-04T12:01:00+00:00")
        self.assertTrue(estado.conflito_evidencias)
        self.assertEqual(EstadoObservacao.PARCIALMENTE_OBSERVADO, estado.estado)

    def test_evidencia_conclusiva_confirma_cedo(self):
        evidencia = self.ev("1", "agent", ResultadoEvidencia.INDISPONIVEL, 0.99, conclusiva=True)
        estado = consolidar_percepcao("core", (evidencia,), self.politica, "2026-09-04T12:01:00+00:00")
        self.assertEqual(EstadoObservacao.INACESSIVEL, estado.estado)


if __name__ == "__main__":
    unittest.main()
