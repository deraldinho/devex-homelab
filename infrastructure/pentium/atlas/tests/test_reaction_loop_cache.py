import unittest

from infrastructure.pentium.atlas.cognitive_cache import CognitiveCache, CognitiveCachePolicy
from infrastructure.pentium.atlas.modelo_contexto_cognitivo import ContextoCognitivo, DecisaoAtivacaoCognitiva, MotivoAtivacaoCognitiva
from infrastructure.pentium.atlas.modelo_llm_gateway import ResultadoInferencia
from infrastructure.pentium.atlas.reaction_loop_cognitivo import ReactionLoopCognitivo


class FakePolicy:
    def __init__(self, motivo): self.motivo = motivo
    def avaliar(self, **kwargs): return DecisaoAtivacaoCognitiva(True, self.motivo)
    def registrar_ativacao(self, *args): pass


class FakeBuilder:
    def construir(self, *, motivo, agora, **kwargs):
        return ContextoCognitivo(1, agora, motivo, "core", "healthy", "observado", None,
            {"stress": 0.1}, "calmo", (), "core", None, (), (), (), ())


class FakeGateway:
    def __init__(self, texto): self.texto, self.calls = texto, 0
    def inferir(self, contexto, tarefa):
        self.calls += 1
        return ResultadoInferencia(True, self.texto, None, 25, "fake")


class CacheFailure:
    def allowed(self, motivo): return True
    def get(self, contexto, tarefa): raise RuntimeError("cache down")
    def put(self, contexto, tarefa, resultado): raise RuntimeError("cache down")


class ReactionLoopCacheTests(unittest.TestCase):
    def cache(self):
        return CognitiveCache(CognitiveCachePolicy(8, 60, "qwen3-0.6b-q4", "k1-v1"))

    def processar(self, loop, agora):
        return loop.processar(fingerprint="fp", agora=agora, sinais_ativacao={}, dados_contexto={})

    def test_reflexao_periodica_reutiliza_cache_sem_segunda_inferencia(self):
        gateway = FakeGateway('{"versao_schema":1,"texto":"estavel","resumo":"ok","intencao":null,"parametros_intencao":{},"confianca":0.8,"motivo":"reflexao_periodica","requer_confirmacao":false}')
        loop = ReactionLoopCognitivo(FakePolicy(MotivoAtivacaoCognitiva.REFLEXAO_PERIODICA), FakeBuilder(), gateway, cognitive_cache=self.cache())
        primeira = self.processar(loop, "2026-09-05T21:00:00+00:00")
        segunda = self.processar(loop, "2026-09-05T21:01:00+00:00")
        self.assertEqual(1, gateway.calls)
        self.assertIn("estavel", primeira.texto)
        self.assertIn("estavel", segunda.texto)
        self.assertTrue(segunda.backend.startswith("cache:"))

    def test_interacao_humana_faz_bypass(self):
        gateway = FakeGateway('{"versao_schema":1,"texto":"oi","resumo":"oi","intencao":null,"parametros_intencao":{},"confianca":0.9,"motivo":"interacao_humana","requer_confirmacao":false}')
        loop = ReactionLoopCognitivo(FakePolicy(MotivoAtivacaoCognitiva.INTERACAO_HUMANA), FakeBuilder(), gateway, cognitive_cache=self.cache())
        self.processar(loop, "2026-09-05T21:00:00+00:00")
        self.processar(loop, "2026-09-05T21:00:10+00:00")
        self.assertEqual(2, gateway.calls)
    def test_resposta_com_intencao_nao_e_cacheada(self):
        gateway = FakeGateway('{"versao_schema":1,"texto":"verificar","resumo":"x","intencao":"get_host_status","parametros_intencao":{"host":"core"},"confianca":0.9,"motivo":"reflexao_periodica","requer_confirmacao":false}')
        loop = ReactionLoopCognitivo(FakePolicy(MotivoAtivacaoCognitiva.REFLEXAO_PERIODICA), FakeBuilder(), gateway, cognitive_cache=self.cache())
        self.processar(loop, "2026-09-05T21:00:00+00:00")
        self.processar(loop, "2026-09-05T21:00:10+00:00")
        self.assertEqual(2, gateway.calls)

    def test_falha_do_cache_degrada_para_gateway(self):
        gateway = FakeGateway('{"versao_schema":1,"texto":"ok","resumo":"ok","intencao":null,"parametros_intencao":{},"confianca":0.8,"motivo":"reflexao_periodica","requer_confirmacao":false}')
        loop = ReactionLoopCognitivo(FakePolicy(MotivoAtivacaoCognitiva.REFLEXAO_PERIODICA), FakeBuilder(), gateway, cognitive_cache=CacheFailure())
        resposta = self.processar(loop, "2026-09-05T21:00:00+00:00")
        self.assertEqual(1, gateway.calls)
        # CP26 hardening: never echo the raw LLM envelope on a cache miss.
        self.assertEqual("ok", resposta.texto)
        self.assertIsNone(resposta.intencao)
        self.assertFalse(resposta.intencao_autorizada)


if __name__ == "__main__":
    unittest.main()