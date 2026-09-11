import unittest
from infrastructure.pentium.atlas.modelo_visual_atlas import EstadoVisualAtlas, EstadoInteracaoVisual, ModoVisual, ExpressaoVisual

class ModeloVisualAtlasTests(unittest.TestCase):
    def test_estado_visual_para_dict_preserva_contrato_dashboard(self):
        estado = EstadoVisualAtlas(
            modo=ModoVisual.OBSERVANDO, expressao=ExpressaoVisual.CURIOSO,
            intensidade_expressao=0.7, foco_visual="core", direcao_olhar="core",
            gesto_atual="nenhum", velocidade_movimento=0.3, intensidade_movimento=0.4,
            falando=False, ouvindo=True, pensando=False, duvida_identidade=False,
            transicao_ms=400,
        )
        payload = estado.para_dict()
        self.assertEqual(1, payload["versao_avatar"])
        self.assertEqual("OBSERVANDO", payload["modo"])
        self.assertEqual("CURIOSO", payload["expressao"])
        self.assertEqual("core", payload["foco_visual"])

    def test_estado_visual_limita_intensidades(self):
        estado = EstadoVisualAtlas(
            modo="OCIOSO", expressao="SERENO", intensidade_expressao=2,
            foco_visual="", direcao_olhar="frente", gesto_atual="nenhum",
            velocidade_movimento=-1, intensidade_movimento=3,
            falando=False, ouvindo=False, pensando=False, duvida_identidade=False,
            transicao_ms=400,
        )
        self.assertEqual(1.0, estado.intensidade_expressao)
        self.assertEqual(0.0, estado.velocidade_movimento)
        self.assertEqual(1.0, estado.intensidade_movimento)
        self.assertEqual("neutro", estado.foco_visual)

    def test_rejeita_transicao_fora_do_bound(self):
        with self.assertRaises(ValueError):
            EstadoVisualAtlas(
                modo="OCIOSO", expressao="SERENO", intensidade_expressao=.2,
                foco_visual="neutro", direcao_olhar="frente", gesto_atual="nenhum",
                velocidade_movimento=.2, intensidade_movimento=.2,
                falando=False, ouvindo=False, pensando=False, duvida_identidade=False,
                transicao_ms=10,
            )

    def test_interacao_exige_timestamp_com_timezone(self):
        with self.assertRaises(ValueError):
            EstadoInteracaoVisual(atualizado_em="2026-09-08T01:00:00")

if __name__ == "__main__":
    unittest.main()
