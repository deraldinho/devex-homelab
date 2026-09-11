import unittest

from infrastructure.pentium.atlas.cognitive_cache import CognitiveCache, CognitiveCachePolicy
from infrastructure.pentium.atlas.modelo_contexto_cognitivo import ContextoCognitivo, MotivoAtivacaoCognitiva
from infrastructure.pentium.atlas.modelo_llm_gateway import ResultadoInferencia


def contexto(timestamp="2026-09-05T21:00:00+00:00", *, memoria_ts="2026-09-05T20:00:00+00:00"):
    return ContextoCognitivo(
        1, timestamp, MotivoAtivacaoCognitiva.REFLEXAO_PERIODICA,
        "core", "healthy", "observado", None, {"stress": 0.1}, "calmo", (),
        "core", None, (), (), (),
        ({"memory_id": "m1", "content": "Core estavel", "timestamp": memoria_ts},),
    )


class FakeClock:
    def __init__(self): self.now = 0.0
    def __call__(self): return self.now


class CognitiveCacheTests(unittest.TestCase):
    def cache(self, clock=None, max_entries=2, ttl_s=10):
        return CognitiveCache(CognitiveCachePolicy(max_entries, ttl_s, "qwen3-0.6b-q4", "k1-v1"), clock=clock)

    def test_chave_ignora_timestamp_top_level_mas_preserva_timestamp_interno(self):
        cache = self.cache()
        a = cache.key(contexto("2026-09-05T21:00:00+00:00"), "formular_resposta_cognitiva")
        b = cache.key(contexto("2026-09-05T21:01:00+00:00"), "formular_resposta_cognitiva")
        c = cache.key(contexto(memoria_ts="2026-09-05T20:01:00+00:00"), "formular_resposta_cognitiva")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
    def test_ttl_expira_e_lru_remove_mais_antiga(self):
        clock = FakeClock()
        cache = self.cache(clock=clock, max_entries=2, ttl_s=5)
        ok = ResultadoInferencia(True, "a", None, 10, "fake")
        cache.put(contexto(), "t1", ok)
        cache.put(contexto(), "t2", ok)
        self.assertIsNotNone(cache.get(contexto(), "t1"))
        cache.put(contexto(), "t3", ok)
        self.assertIsNone(cache.get(contexto(), "t2"))
        clock.now = 6
        self.assertIsNone(cache.get(contexto(), "t1"))
        metrics = cache.metrics()
        self.assertGreaterEqual(metrics["eviction"], 1)
        self.assertGreaterEqual(metrics["expired"], 1)

    def test_somente_reflexao_periodica_e_cacheavel(self):
        cache = self.cache()
        self.assertTrue(cache.allowed(MotivoAtivacaoCognitiva.REFLEXAO_PERIODICA))
        for motivo in MotivoAtivacaoCognitiva:
            if motivo is not MotivoAtivacaoCognitiva.REFLEXAO_PERIODICA:
                self.assertFalse(cache.allowed(motivo))

    def test_resultado_falho_nao_e_admitido(self):
        from infrastructure.pentium.atlas.modelo_llm_gateway import ErroInferencia
        cache = self.cache()
        falha = ResultadoInferencia(False, None, ErroInferencia.TIMEOUT, 10, "fake")
        self.assertFalse(cache.put(contexto(), "t", falha))
        self.assertIsNone(cache.get(contexto(), "t"))


if __name__ == "__main__":
    unittest.main()