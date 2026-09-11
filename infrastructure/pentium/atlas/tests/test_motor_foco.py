import unittest
from dataclasses import replace

from infrastructure.pentium.atlas.modelo_foco import AssuntoFoco, PoliticaFoco
from infrastructure.pentium.atlas.motor_foco import MotorFoco


class MotorFocoTests(unittest.TestCase):
    def test_mesmo_assunto_atualiza_recuperacao_sem_congelar_foco(self):
        motor = self.motor()
        anterior = self.assunto("core", 0.9, critico=True)
        motor.atualizar((anterior,), "2026-09-11T12:00:00+00:00")
        recuperado = replace(anterior, critico=False, recuperado=True, gravidade=0.1)
        foco = motor.atualizar((recuperado,), "2026-09-11T12:01:00+00:00")
        self.assertEqual(recuperado, foco.principal)
        seguinte = motor.atualizar(
            (recuperado, self.assunto("x99", 0.6)), "2026-09-11T12:02:00+00:00",
        )
        self.assertEqual("x99", seguinte.principal.assunto_id)

    def assunto(self, assunto_id, valor, *, critico=False, recuperado=False):
        return AssuntoFoco(
            assunto_id, assunto_id,
            valor, valor, valor, valor, valor, valor,
            critico=critico,
            recuperado=recuperado,
        )

    def motor(self):
        return MotorFoco(PoliticaFoco(2, 0.15, 0.4))

    def test_critico_interrompe_foco_atual(self):
        motor = self.motor()
        motor.atualizar((self.assunto("core", 0.9),), "2026-09-04T21:40:00+00:00")
        foco = motor.atualizar((self.assunto("firewall", 0.4, critico=True),), "2026-09-04T21:40:01+00:00")
        self.assertEqual("firewall", foco.principal.assunto_id)

    def test_histerese_retém_foco_por_margem_pequena(self):
        motor = self.motor()
        motor.atualizar((self.assunto("core", 0.70),), "2026-09-04T21:40:00+00:00")
        foco = motor.atualizar((self.assunto("x99", 0.80),), "2026-09-04T21:40:01+00:00")
        self.assertEqual("core", foco.principal.assunto_id)

    def test_margem_significativa_substitui_foco(self):
        motor = self.motor()
        motor.atualizar((self.assunto("core", 0.50),), "2026-09-04T21:40:00+00:00")
        foco = motor.atualizar((self.assunto("x99", 0.80),), "2026-09-04T21:40:01+00:00")
        self.assertEqual("x99", foco.principal.assunto_id)

    def test_recuperacao_reduz_prioridade_e_secundarios_sao_bounded(self):
        motor = self.motor()
        foco = motor.atualizar(
            (
                self.assunto("core", 0.95, recuperado=True),
                self.assunto("firewall", 0.80),
                self.assunto("x99", 0.70),
                self.assunto("project", 0.60),
            ),
            "2026-09-04T21:40:00+00:00",
        )
        self.assertEqual("firewall", foco.principal.assunto_id)
        self.assertEqual(("x99", "project"), tuple(x.assunto_id for x in foco.secundarios))


if __name__ == "__main__":
    unittest.main()
