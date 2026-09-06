import unittest

from infrastructure.pentium.atlas.certificacao_cognitiva import (
    CertificadorCognitivo,
    MetricasSistema,
)


class FakeSampler:
    def __init__(self):
        self.calls = 0

    def coletar(self):
        self.calls += 1
        return MetricasSistema(
            rss_atlas_kib=1000 + self.calls,
            rss_llm_kib=2000 + self.calls,
            swap_usada_kib=300,
            cpu_percent=25.0,
            temperatura_c=55.0,
        )


class CertificadorCognitivoTests(unittest.TestCase):
    def test_certificacao_mede_antes_durante_depois_e_latencia(self):
        sampler = FakeSampler()
        tempos = iter([10.0, 10.25])
        cert = CertificadorCognitivo(sampler=sampler, monotonic=lambda: next(tempos))
        resultado = cert.executar(lambda: {"sucesso": True, "tokens_por_s": 4.5})
        self.assertEqual(3, sampler.calls)
        self.assertEqual(250, resultado.latencia_total_ms)
        self.assertTrue(resultado.inferencia_sucesso)
        self.assertEqual(4.5, resultado.tokens_por_s)
        self.assertEqual(1001, resultado.antes.rss_atlas_kib)
        self.assertEqual(1002, resultado.durante[0].rss_atlas_kib)
        self.assertEqual(1003, resultado.depois.rss_atlas_kib)

    def test_falha_da_inferencia_e_registrada_sem_quebrar_harness(self):
        sampler = FakeSampler()
        tempos = iter([1.0, 1.1])
        cert = CertificadorCognitivo(sampler=sampler, monotonic=lambda: next(tempos))
        resultado = cert.executar(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        self.assertFalse(resultado.inferencia_sucesso)
        self.assertEqual("RuntimeError", resultado.erro)


if __name__ == "__main__":
    unittest.main()
