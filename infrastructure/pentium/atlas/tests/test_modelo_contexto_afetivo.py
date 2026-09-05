import unittest

from infrastructure.pentium.atlas.modelo_contexto_afetivo import (
    EntidadeAfetiva,
    TipoEntidadeAfetiva,
    VinculoAfetivo,
)


class ModeloContextoAfetivoTests(unittest.TestCase):
    def test_tipos_de_entidade_cobrem_design_a2(self):
        self.assertEqual(
            {
                "cerebro", "membro", "orgao_vital", "dependencia_externa",
                "recurso_externo", "projeto", "servico",
            },
            {item.value for item in TipoEntidadeAfetiva},
        )

    def test_entidade_rejeita_identificador_vazio(self):
        with self.assertRaises(ValueError):
            EntidadeAfetiva("   ", "Core", TipoEntidadeAfetiva.MEMBRO)

    def test_vinculo_limita_todas_as_dimensoes(self):
        vinculo = VinculoAfetivo(
            "core", 2.0, -1.0, 0.7, 1.4, -0.2, 0.9,
        )
        self.assertEqual(
            (1.0, 0.0, 0.7, 1.0, 0.0, 0.9),
            (
                vinculo.importancia,
                vinculo.proximidade,
                vinculo.responsabilidade,
                vinculo.dependencia_operacional,
                vinculo.familiaridade,
                vinculo.confianca_operacional,
            ),
        )

    def test_evolucao_altera_apenas_campos_experienciais(self):
        original = VinculoAfetivo("x99", 0.8, 0.7, 0.9, 0.6, 0.4, 0.5)
        novo = original.evoluir_experiencia(0.2, -0.8)
        self.assertEqual((0.8, 0.7, 0.9, 0.6), (
            novo.importancia, novo.proximidade,
            novo.responsabilidade, novo.dependencia_operacional,
        ))
        self.assertAlmostEqual(0.6, novo.familiaridade)
        self.assertEqual(0.0, novo.confianca_operacional)
