import unittest

from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo, ImpulsoAfetivo, PersonalidadeBase, PoliticaDecaimento
from infrastructure.pentium.atlas.motor_afetivo import MotorEstadoAfetivo


P = PersonalidadeBase(0.20, 0.25, 0.10, 0.70, 0.55, 0.75)
D = PoliticaDecaimento(3600, 900, 1800, 21600, 7200, 10800, 3600)


class MotorEstadoAfetivoTests(unittest.TestCase):
    def test_impulso_aplica_decaimento_antes_do_delta(self):
        inicial = EstadoAfetivo(0.80, 0.25, 0.10, 0.70, 0.55, 0.75, "2026-09-04T12:00:00+00:00")
        motor = MotorEstadoAfetivo(P, D, inicial, lambda: "2026-09-04T13:00:00+00:00")
        novo = motor.aplicar_impulso(ImpulsoAfetivo("recuperacao", delta_valencia=0.10))
        self.assertAlmostEqual(0.60, novo.valencia, places=9)

    def test_impulso_respeita_limites(self):
        motor = MotorEstadoAfetivo(P, D, P.criar_estado("2026-09-04T12:00:00+00:00"), lambda: "2026-09-04T12:00:00+00:00")
        novo = motor.aplicar_impulso(ImpulsoAfetivo("critico", delta_estresse=1.0, delta_ativacao=1.0))
        self.assertEqual(1.0, novo.estresse)
        self.assertEqual(1.0, novo.ativacao)

    def test_a1_preserva_foco_sem_decidi_lo(self):
        inicial = EstadoAfetivo(0.20, 0.25, 0.10, 0.70, 0.55, 0.75, "2026-09-04T12:00:00+00:00", "x99")
        motor = MotorEstadoAfetivo(P, D, inicial, lambda: "2026-09-04T12:00:00+00:00")
        self.assertEqual("x99", motor.aplicar_impulso(ImpulsoAfetivo("teste", delta_curiosidade=0.10)).foco_atencao)
