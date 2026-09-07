import unittest

from infrastructure.pentium.atlas.llm_gateway import LLMGateway
from infrastructure.pentium.atlas.modelo_contexto_cognitivo import (
    ContextoCognitivo,
    MotivoAtivacaoCognitiva,
)
from infrastructure.pentium.atlas.modelo_llm_gateway import ResultadoInferencia


class BackendFake:
    def __init__(self):
        self.solicitacoes = []

    def inferir(self, solicitacao):
        self.solicitacoes.append(solicitacao)
        return ResultadoInferencia(True, "Estado resumido.", None, 1, "fake")


class LlmGatewayTests(unittest.TestCase):
    def contexto(self, texto="core"):
        return ContextoCognitivo(
            1, "2026-09-05T20:00:00+00:00",
            MotivoAtivacaoCognitiva.INTERACAO_HUMANA,
            texto, "healthy", "observado", None,
            {"valencia": 0.1}, "calmo", (), texto,
            None, (), (), (),
        )

    def test_gateway_entrega_somente_contexto_cognitivo_ao_backend(self):
        backend = BackendFake()
        gateway = LLMGateway(backend, max_payload_bytes=8192, max_tokens_contexto=4096)
        resultado = gateway.inferir(self.contexto(), "resumir_estado")
        self.assertTrue(resultado.sucesso)
        self.assertEqual(1, len(backend.solicitacoes))
        req = backend.solicitacoes[0]
        self.assertIn('"estado_tecnico":"healthy"', req.contexto_json)
        self.assertNotIn("shell", req.contexto_json.lower())

    def test_gateway_rejeita_payload_acima_do_limite_antes_do_backend(self):
        backend = BackendFake()
        gateway = LLMGateway(backend, max_payload_bytes=80, max_tokens_contexto=4096)
        with self.assertRaises(ValueError):
            gateway.inferir(self.contexto("core-" + "x" * 200), "resumir_estado")
        self.assertEqual([], backend.solicitacoes)


if __name__ == "__main__":
    unittest.main()
