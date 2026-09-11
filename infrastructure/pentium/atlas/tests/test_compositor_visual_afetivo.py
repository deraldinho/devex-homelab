import unittest
from infrastructure.pentium.atlas.compositor_visual_afetivo import CompositorVisualAfetivo
from infrastructure.pentium.atlas.contexto_foco_emocao import ResultadoFocoEmocao
from infrastructure.pentium.atlas.emocao_derivada import EmocaoDerivada
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo
from infrastructure.pentium.atlas.modelo_foco import AssuntoFoco, FocoAtencao
from infrastructure.pentium.atlas.modelo_visual_atlas import EstadoInteracaoVisual

NOW = "2026-09-08T04:00:00+00:00"

class CompositorVisualAfetivoTests(unittest.TestCase):
    def resultado(self, emocao, *, foco=True, estresse=.2, ativacao=.4, engajamento=.6, curiosidade=.5):
        estado = EstadoAfetivo(.1, ativacao, estresse, .7, engajamento, curiosidade, NOW, "core" if foco else None)
        principal = AssuntoFoco("core", "core", .6, .6, .6, .6, .6, .6) if foco else None
        foco_obj = FocoAtencao(principal, (), NOW, 2)
        return ResultadoFocoEmocao(estado, foco_obj, EmocaoDerivada(emocao, ()))

    def interacao(self, **kwargs):
        return EstadoInteracaoVisual(atualizado_em=NOW, **kwargs)

    def test_mapeia_rotulos_canonicos_para_arquetipos(self):
        casos = {
            "calmo": "SERENO", "confiante": "SERENO", "satisfeito": "SERENO",
            "interessado": "ENGAJADO", "curioso": "CURIOSO",
            "atento": "ATENTO", "vigilante": "ATENTO",
            "preocupado": "PREOCUPADO",
            "estressado": "SOB_PRESSAO", "alarmado": "SOB_PRESSAO", "frustrado": "SOB_PRESSAO",
            "aliviado": "RECUPERANDO",
        }
        compositor = CompositorVisualAfetivo()
        for rotulo, esperado in casos.items():
            with self.subTest(rotulo=rotulo):
                visual = compositor.compor(self.resultado(rotulo), self.interacao())
                self.assertEqual(esperado, visual.expressao.value)

    def test_prioridade_de_modo_e_foco(self):
        compositor = CompositorVisualAfetivo()
        resultado = self.resultado("atento")
        self.assertEqual("CONVERSANDO", compositor.compor(resultado, self.interacao(falando=True)).modo.value)
        self.assertEqual("CONVERSANDO", compositor.compor(resultado, self.interacao(pensando=True)).modo.value)
        self.assertEqual("CONVERSANDO", compositor.compor(resultado, self.interacao(ouvindo=True)).modo.value)
        self.assertEqual("REAGINDO", compositor.compor(resultado, self.interacao(), reacao_critica=True).modo.value)
        visual = compositor.compor(resultado, self.interacao())
        self.assertEqual("OBSERVANDO", visual.modo.value)
        self.assertEqual("core", visual.foco_visual)
        self.assertEqual("core", visual.direcao_olhar)

    def test_sem_foco_fica_ocioso_e_neutro(self):
        visual = CompositorVisualAfetivo().compor(self.resultado("calmo", foco=False), self.interacao())
        self.assertEqual("OCIOSO", visual.modo.value)
        self.assertEqual("neutro", visual.foco_visual)

    def test_gesto_reflete_interacao_sem_mudar_afeto(self):
        compositor = CompositorVisualAfetivo()
        resultado = self.resultado("curioso")
        self.assertEqual("fala", compositor.compor(resultado, self.interacao(falando=True)).gesto_atual)
        self.assertEqual("pensamento", compositor.compor(resultado, self.interacao(pensando=True)).gesto_atual)
        self.assertEqual("escuta", compositor.compor(resultado, self.interacao(ouvindo=True)).gesto_atual)
        self.assertEqual("duvida", compositor.compor(resultado, self.interacao(duvida_identidade=True)).gesto_atual)
        self.assertEqual("curioso", resultado.emocao.principal)

if __name__ == "__main__":
    unittest.main()
