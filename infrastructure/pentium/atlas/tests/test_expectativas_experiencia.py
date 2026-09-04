import unittest

from infrastructure.pentium.atlas.modelo_contexto_afetivo import (
    EstadoExpectativa,
    Expectativa,
    ExperienciaOperacional,
    TipoExpectativa,
    TipoExperienciaOperacional,
)


class ExpectativasExperienciaTests(unittest.TestCase):
    def test_expectativa_planejada_fica_atrasada_depois_do_limite(self):
        expectativa = Expectativa(
            "exp-1", "core", TipoExpectativa.MANUTENCAO_PLANEJADA,
            "2026-09-04T12:00:00+00:00",
            "2026-09-04T13:00:00+00:00",
            "2026-09-04T14:00:00+00:00",
        )
        self.assertEqual(
            EstadoExpectativa.EM_CURSO,
            expectativa.estado_em("2026-09-04T13:30:00+00:00"),
        )
        self.assertEqual(
            EstadoExpectativa.ATRASADA,
            expectativa.estado_em("2026-09-04T14:00:01+00:00"),
        )

    def test_expectativa_pode_ser_concluida_ou_cancelada(self):
        expectativa = Expectativa(
            "exp-2", "x99", TipoExpectativa.RETORNO_ESPERADO,
            "2026-09-04T12:00:00+00:00",
            "2026-09-04T12:30:00+00:00",
            "2026-09-04T13:00:00+00:00",
        )
        self.assertEqual(
            EstadoExpectativa.CUMPRIDA,
            expectativa.concluir().estado_em("2026-09-04T14:00:00+00:00"),
        )
        self.assertEqual(
            EstadoExpectativa.CANCELADA,
            expectativa.cancelar().estado_em("2026-09-04T14:00:00+00:00"),
        )

    def test_experiencia_normaliza_instante_e_e_imutavel(self):
        experiencia = ExperienciaOperacional(
            "evt-1", "core", TipoExperienciaOperacional.INCIDENTE,
            "2026-09-04T09:00:00-03:00",
        )
        self.assertEqual("2026-09-04T12:00:00+00:00", experiencia.ocorrido_em)
        with self.assertRaises(Exception):
            experiencia.entidade_id = "x99"
