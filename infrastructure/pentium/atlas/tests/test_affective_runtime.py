import unittest
from infrastructure.pentium.atlas.affective_runtime import AffectiveRuntime
from infrastructure.pentium.atlas.compositor_visual_afetivo import CompositorVisualAfetivo
from infrastructure.pentium.atlas.contexto_foco_emocao import ResultadoFocoEmocao
from infrastructure.pentium.atlas.emocao_derivada import EmocaoDerivada
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo
from infrastructure.pentium.atlas.modelo_foco import AssuntoFoco, FocoAtencao
from infrastructure.pentium.atlas.modelo_visual_atlas import EstadoInteracaoVisual

NOW = "2026-09-08T04:30:00+00:00"

class PublisherSpy:
    def __init__(self, fail=False):
        self.fail = fail
        self.estados = []
    def publicar(self, estado):
        if self.fail:
            raise OSError("disk")
        self.estados.append(estado)

class CompositorFalho:
    def compor(self, *_args, **_kwargs):
        raise RuntimeError("boom")

class AffectiveRuntimeTests(unittest.TestCase):
    def resultado(self, emocao="atento"):
        estado = EstadoAfetivo(.1, .4, .2, .7, .6, .5, NOW, "core")
        principal = AssuntoFoco("core", "core", .6, .6, .6, .6, .6, .6)
        foco = FocoAtencao(principal, (), NOW, 2)
        return ResultadoFocoEmocao(estado, foco, EmocaoDerivada(emocao, ()))

    def interacao(self, **kwargs):
        return EstadoInteracaoVisual(atualizado_em=NOW, **kwargs)

    def test_publica_apenas_quando_visual_muda(self):
        pub = PublisherSpy()
        runtime = AffectiveRuntime(CompositorVisualAfetivo(), pub, interacao_inicial=self.interacao())
        primeiro = runtime.atualizar_resultado(self.resultado())
        segundo = runtime.atualizar_resultado(self.resultado())
        self.assertEqual(primeiro, segundo)
        self.assertEqual(1, len(pub.estados))

    def test_interacao_efemera_recompõe_visual(self):
        pub = PublisherSpy()
        runtime = AffectiveRuntime(CompositorVisualAfetivo(), pub, interacao_inicial=self.interacao())
        runtime.atualizar_resultado(self.resultado())
        visual = runtime.atualizar_interacao(self.interacao(falando=True))
        self.assertTrue(visual.falando)
        self.assertEqual("CONVERSANDO", visual.modo.value)
        self.assertEqual(2, len(pub.estados))

    def test_falha_do_publisher_nao_apaga_visual_em_memoria(self):
        pub = PublisherSpy(fail=True)
        runtime = AffectiveRuntime(CompositorVisualAfetivo(), pub, interacao_inicial=self.interacao())
        visual = runtime.atualizar_resultado(self.resultado())
        self.assertEqual(visual, runtime.ultimo_visual)
        self.assertIsInstance(runtime.ultimo_erro_publicacao, OSError)

    def test_falha_do_compositor_preserva_ultimo_visual_valido(self):
        pub = PublisherSpy()
        bom = AffectiveRuntime(CompositorVisualAfetivo(), pub, interacao_inicial=self.interacao())
        esperado = bom.atualizar_resultado(self.resultado())
        bom._compositor = CompositorFalho()
        recebido = bom.atualizar_resultado(self.resultado("curioso"))
        self.assertEqual(esperado, recebido)
        self.assertIsInstance(bom.ultimo_erro_composicao, RuntimeError)

    def test_interacao_sem_resultado_nao_inventa_emocao(self):
        runtime = AffectiveRuntime(CompositorVisualAfetivo(), PublisherSpy(), interacao_inicial=self.interacao())
        self.assertIsNone(runtime.atualizar_interacao(self.interacao(ouvindo=True)))
        self.assertIsNone(runtime.ultimo_visual)

if __name__ == "__main__":
    unittest.main()
