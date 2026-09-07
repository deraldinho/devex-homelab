import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from infrastructure.pentium.atlas.llama_cpp_backend import LlamaCppBackend
from infrastructure.pentium.atlas.modelo_llm_gateway import ErroInferencia, SolicitacaoInferencia


class LlamaJsonExtractionTests(unittest.TestCase):
    def make_backend(self, stdout):
        td = tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        root = Path(td.name); binary = root / 'llama-cli'; model = root / 'qwen.gguf'
        binary.write_text('x'); model.write_text('x')
        executor = lambda *a, **k: SimpleNamespace(returncode=0, stdout=stdout, stderr='')
        return LlamaCppBackend(binary, model, timeout_s=5, max_saida_bytes=8192, executor=executor)

    def test_extracts_only_final_cognitive_json_from_cli_noise(self):
        final = '{"versao_schema":1,"texto":"Sim","resumo":null,"intencao":null,"parametros_intencao":{},"confianca":0.9,"motivo":"ok","requer_confirmacao":false}'
        out = self.make_backend('banner\n> prompt {not-json}\n' + final + '\n> ').inferir(SolicitacaoInferencia(1,'x','{}',256))
        self.assertTrue(out.sucesso)
        self.assertEqual(final, out.texto)

    def test_rejects_stdout_without_cognitive_schema_json(self):
        out = self.make_backend('banner\n{"estado":"healthy"}\n').inferir(SolicitacaoInferencia(1,'x','{}',256))
        self.assertFalse(out.sucesso)
        self.assertEqual(ErroInferencia.SAIDA_INVALIDA, out.erro)


if __name__ == '__main__':
    unittest.main()
