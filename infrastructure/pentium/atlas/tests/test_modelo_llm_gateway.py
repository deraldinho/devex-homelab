import unittest

from infrastructure.pentium.atlas.modelo_llm_gateway import (
    ErroInferencia,
    ResultadoInferencia,
    SolicitacaoInferencia,
)


class ModeloLlmGatewayTests(unittest.TestCase):
    def test_solicitacao_e_resultado_sao_bounded_e_estruturados(self):
        req = SolicitacaoInferencia(1, "resumir_estado", '{"estado":"healthy"}', 2048)
        self.assertEqual("resumir_estado", req.tarefa)
        self.assertEqual(2048, req.max_tokens_contexto)
        out = ResultadoInferencia(True, "Tudo normal.", None, 12, "llama_cpp")
        self.assertTrue(out.sucesso)
        self.assertEqual("Tudo normal.", out.texto)

    def test_modelos_rejeitam_limites_invalidos(self):
        with self.assertRaises(ValueError):
            SolicitacaoInferencia(1, "", "{}", 2048)
        with self.assertRaises(ValueError):
            ResultadoInferencia(False, None, ErroInferencia.TIMEOUT, -1, "llama_cpp")


if __name__ == "__main__":
    unittest.main()
