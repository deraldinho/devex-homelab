import unittest
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo
from infrastructure.pentium.atlas.emocao_derivada import (
    ROTULOS_EMOCAO,
    ContextoEmocional,
    derivar_emocao,
)

class TestEmocaoDerivada20(unittest.TestCase):
    def test_20_rotulos_canonicos_presentes(self):
        self.assertEqual(22, len(ROTULOS_EMOCAO))
        esperados = {
            "calmo", "atento", "interessado", "curioso", "preocupado",
            "estressado", "alarmado", "frustrado", "aliviado",
            "satisfeito", "confiante", "vigilante",
            "sereno", "harmonico", "determinado", "empolgado",
            "fascinado", "acolhedor", "orgulhoso", "sobrecarregado",
            "pensativo", "exaurido"
        }
        self.assertEqual(esperados, set(ROTULOS_EMOCAO))

    def test_derivacao_empolgado(self):
        # Alta ativacao, alta curiosidade, valencia positiva
        estado = EstadoAfetivo(
            valencia=0.8,
            ativacao=0.9,
            estresse=0.05,
            confianca=0.85,
            engajamento=0.9,
            curiosidade=0.95,
            atualizado_em="2026-09-20T10:00:00+00:00"
        )
        ctx = ContextoEmocional()
        derivada = derivar_emocao(estado, ctx, capacidade_nuances=2)
        self.assertIn(derivada.principal, ("empolgado", "fascinado", "satisfeito", "curioso"))

    def test_derivacao_sobrecarregado(self):
        # Alto estresse, alta ativacao, percepcao insegura
        estado = EstadoAfetivo(
            valencia=-0.7,
            ativacao=0.9,
            estresse=0.95,
            confianca=0.2,
            engajamento=0.3,
            curiosidade=0.1,
            atualizado_em="2026-09-20T10:00:00+00:00"
        )
        ctx = ContextoEmocional(percepcao_insegura=True)
        derivada = derivar_emocao(estado, ctx, capacidade_nuances=2)
        self.assertIn(derivada.principal, ("sobrecarregado", "estressado", "preocupado", "alarmado"))

if __name__ == "__main__":
    unittest.main()
