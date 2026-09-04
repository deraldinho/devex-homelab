import unittest

from infrastructure.pentium.atlas.decaimento_afetivo import decair_estado
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo, PersonalidadeBase, PoliticaDecaimento


P = PersonalidadeBase(0.20, 0.25, 0.10, 0.70, 0.55, 0.75)
D = PoliticaDecaimento(3600, 900, 1800, 21600, 7200, 10800, 3600)


class DecaimentoAfetivoTests(unittest.TestCase):
    def test_uma_meia_vida_reduz_metade_da_distancia_ate_a_base(self):
        estado = EstadoAfetivo(0.80, 0.25, 0.10, 0.70, 0.55, 0.75, "2026-09-04T12:00:00+00:00")
        novo = decair_estado(estado, P, D, "2026-09-04T13:00:00+00:00")
        self.assertAlmostEqual(0.50, novo.valencia, places=9)

    def test_modo_offline_limita_decaimento_a_uma_hora(self):
        estado = EstadoAfetivo(0.80, 0.25, 0.10, 0.70, 0.55, 0.75, "2026-09-04T00:00:00+00:00")
        novo = decair_estado(estado, P, D, "2026-09-04T12:00:00+00:00", modo_offline=True)
        self.assertAlmostEqual(0.50, novo.valencia, places=9)
        self.assertEqual("2026-09-04T12:00:00+00:00", novo.atualizado_em)

    def test_instante_anterior_ao_estado_e_rejeitado(self):
        with self.assertRaises(ValueError):
            decair_estado(P.criar_estado("2026-09-04T12:00:00+00:00"), P, D, "2026-09-04T11:59:59+00:00")
