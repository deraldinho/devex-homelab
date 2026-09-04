import unittest

from infrastructure.pentium.atlas.emocao_derivada import ContextoEmocional, derivar_emocao
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo


class EmocaoDerivadaTests(unittest.TestCase):
    def estado(self, **kwargs):
        dados = dict(
            valencia=0.0, ativacao=0.2, estresse=0.1,
            confianca=0.7, engajamento=0.4, curiosidade=0.3,
            atualizado_em="2026-09-04T21:50:00+00:00",
        )
        dados.update(kwargs)
        return EstadoAfetivo(**dados)

    def test_estado_estavel_deriva_calmo(self):
        emocao = derivar_emocao(self.estado(ativacao=0.05, estresse=0.02), ContextoEmocional())
        self.assertEqual("calmo", emocao.principal)

    def test_criticidade_com_alta_ativacao_deriva_alarmado(self):
        emocao = derivar_emocao(
            self.estado(valencia=-0.7, ativacao=0.95, estresse=0.95),
            ContextoEmocional(criticidade_relevante=True),
        )
        self.assertEqual("alarmado", emocao.principal)

    def test_frustrado_exige_reincidencia_e_queda_de_confianca(self):
        base = self.estado(valencia=-0.5, ativacao=0.8, estresse=0.9, confianca=0.2)
        sem = derivar_emocao(base, ContextoEmocional(reincidencia=0.0))
        com = derivar_emocao(base, ContextoEmocional(reincidencia=1.0))
        self.assertNotEqual("frustrado", sem.principal)
        self.assertEqual("frustrado", com.principal)

    def test_recuperacao_relevante_deriva_aliviado(self):
        emocao = derivar_emocao(
            self.estado(valencia=0.5, ativacao=0.3, estresse=0.1),
            ContextoEmocional(recuperacao_relevante=True),
        )
        self.assertEqual("aliviado", emocao.principal)

    def test_nuances_sao_bounded_e_deterministicas(self):
        emocao = derivar_emocao(
            self.estado(valencia=0.6, ativacao=0.6, estresse=0.2, confianca=0.8, engajamento=0.8, curiosidade=0.7),
            ContextoEmocional(),
            capacidade_nuances=2,
        )
        self.assertLessEqual(len(emocao.nuances), 2)
        self.assertEqual(tuple(sorted(set(emocao.nuances))), tuple(sorted(emocao.nuances)))


if __name__ == "__main__":
    unittest.main()
