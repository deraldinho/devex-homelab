import time
import unittest

from infrastructure.pentium.atlas.certificacao_cognitiva import CertificadorCognitivo, MetricasSistema


class FakeSampler:
    def __init__(self): self.calls = 0
    def coletar(self):
        self.calls += 1
        return MetricasSistema(100 + self.calls, 200 + self.calls, 10, 10.0 * self.calls, 50.0 + self.calls)


class CertificacaoDuranteTests(unittest.TestCase):
    def test_coleta_amostras_bounded_durante_inferencia(self):
        sampler = FakeSampler()
        cert = CertificadorCognitivo(sampler=sampler, interval_s=0.001, max_amostras_durante=4)
        def inferencia():
            time.sleep(0.01)
            return {"sucesso": True, "tokens_por_s": 3.5}
        resultado = cert.executar(inferencia)
        self.assertGreaterEqual(len(resultado.durante), 1)
        self.assertLessEqual(len(resultado.durante), 4)
        self.assertTrue(resultado.inferencia_sucesso)
        self.assertEqual(3.5, resultado.tokens_por_s)


if __name__ == '__main__':
    unittest.main()
