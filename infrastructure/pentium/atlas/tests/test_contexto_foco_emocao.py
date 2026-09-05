import unittest

from infrastructure.pentium.atlas.contexto_foco_emocao import ContextoFocoEmocao
from infrastructure.pentium.atlas.emocao_derivada import ContextoEmocional
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo
from infrastructure.pentium.atlas.modelo_foco import AssuntoFoco, PoliticaFoco


class ContextoFocoEmocaoTests(unittest.TestCase):
    def test_processamento_atualiza_foco_sem_alterar_dimensoes(self):
        estado = EstadoAfetivo(0.1, 0.4, 0.2, 0.7, 0.6, 0.5, "2026-09-04T22:00:00+00:00")
        assunto = AssuntoFoco("core", "core", 0.8, 0.7, 0.8, 0.5, 0.7, 1.0)
        motor = ContextoFocoEmocao(PoliticaFoco(2, 0.15, 0.4), capacidade_nuances=2)

        resultado = motor.processar(estado, (assunto,), ContextoEmocional(), "2026-09-04T22:00:01+00:00")

        self.assertEqual("core", resultado.foco.principal.assunto_id)
        self.assertEqual("core", resultado.estado_afetivo.foco_atencao)
        self.assertEqual(estado.valencia, resultado.estado_afetivo.valencia)
        self.assertEqual(estado.estresse, resultado.estado_afetivo.estresse)
        self.assertIn(resultado.emocao.principal, resultado.rotulos_canonicos)

    def test_processamento_e_deterministico(self):
        estado = EstadoAfetivo(0.0, 0.1, 0.1, 0.8, 0.4, 0.3, "2026-09-04T22:00:00+00:00")
        assunto = AssuntoFoco("x99", "x99", 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        a = ContextoFocoEmocao(PoliticaFoco(2, 0.15, 0.4)).processar(estado, (assunto,), ContextoEmocional(), "2026-09-04T22:00:01+00:00")
        b = ContextoFocoEmocao(PoliticaFoco(2, 0.15, 0.4)).processar(estado, (assunto,), ContextoEmocional(), "2026-09-04T22:00:01+00:00")
        self.assertEqual(a, b)
