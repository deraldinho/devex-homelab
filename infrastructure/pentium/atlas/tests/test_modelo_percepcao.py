import unittest

from infrastructure.pentium.atlas.modelo_percepcao import (
    EstadoObservacao,
    EstadoPercepcao,
    EvidenciaPercepcao,
    ResultadoEvidencia,
)


class ModeloPercepcaoTests(unittest.TestCase):
    def test_estados_canonicos(self):
        self.assertEqual(
            {"observado", "parcialmente_observado", "inacessivel", "desconhecido"},
            {estado.value for estado in EstadoObservacao},
        )

    def test_confianca_e_limitada(self):
        evidencia = EvidenciaPercepcao(
            "ev-1", "core", "ping", ResultadoEvidencia.DISPONIVEL,
            2.0, "2026-09-04T12:00:00+00:00",
        )
        self.assertEqual(1.0, evidencia.confianca)

    def test_estado_normaliza_timestamp_e_fontes(self):
        estado = EstadoPercepcao(
            entidade_id="core",
            estado=EstadoObservacao.OBSERVADO,
            confianca=0.8,
            ultima_observacao_valida="2026-09-04T09:00:00-03:00",
            fontes_disponiveis=("ssh", "ping", "ssh"),
            fontes_indisponiveis=("agent",),
            conflito_evidencias=False,
            atualizado_em="2026-09-04T09:01:00-03:00",
        )
        self.assertEqual("2026-09-04T12:00:00+00:00", estado.ultima_observacao_valida)
        self.assertEqual(("ping", "ssh"), estado.fontes_disponiveis)
        self.assertEqual("2026-09-04T12:01:00+00:00", estado.atualizado_em)


if __name__ == "__main__":
    unittest.main()
