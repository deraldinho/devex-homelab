import threading
import unittest

from infrastructure.pentium.atlas.certificacao_cognitiva import CertificadorCognitivo, MetricasSistema


class SamplerComSinal:
    def __init__(self, liberar):
        self.calls = 0
        self._liberar = liberar

    def coletar(self):
        self.calls += 1
        if self.calls >= 3:
            self._liberar.set()
        return MetricasSistema(100 + self.calls, 200 + self.calls, 10, float(self.calls * 10), 40.0 + self.calls)


class CertificacaoDuranteTests(unittest.TestCase):
    def test_coleta_amostras_bounded_durante_inferencia(self):
        liberar = threading.Event()
        sampler = SamplerComSinal(liberar)
        cert = CertificadorCognitivo(sampler=sampler, interval_s=0.001, max_amostras_durante=4, sleeper=lambda _: None)

        def inferir():
            liberar.wait(timeout=1)
            return {"sucesso": True, "tokens_por_s": 3.0}

        resultado = cert.executar(inferir)
        self.assertGreaterEqual(len(resultado.durante), 2)
        self.assertLessEqual(len(resultado.durante), 4)
        self.assertGreaterEqual(max(m.cpu_percent or 0 for m in resultado.durante), 20.0)
        self.assertTrue(resultado.inferencia_sucesso)
