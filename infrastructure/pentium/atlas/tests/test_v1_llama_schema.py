import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from infrastructure.pentium.atlas.llama_cpp_backend import LlamaCppBackend
from infrastructure.pentium.atlas.modelo_llm_gateway import SolicitacaoInferencia


class LlamaSchemaTests(unittest.TestCase):
    def test_backend_enforces_deterministic_json_schema(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); binary = root / 'llama-cli'; model = root / 'qwen.gguf'
            binary.write_text('x'); model.write_text('x')
            calls = []
            valid = '{"versao_schema":1,"texto":"ok","resumo":null,"intencao":null,"parametros_intencao":{},"confianca":1,"motivo":"ok","requer_confirmacao":false}'
            def executor(argv, **kwargs):
                calls.append(argv); return SimpleNamespace(returncode=0, stdout=valid, stderr='')
            backend = LlamaCppBackend(binary, model, timeout_s=5, max_saida_bytes=8192, executor=executor)
            backend.inferir(SolicitacaoInferencia(1,'x','{}',256,'off'))
            argv = calls[0]
            self.assertEqual(['--temp','0'], argv[argv.index('--temp'):argv.index('--temp')+2])
            schema = json.loads(argv[argv.index('--json-schema') + 1])
            self.assertEqual('object', schema['properties']['parametros_intencao']['type'])
            self.assertEqual('string', schema['properties']['motivo']['type'])


if __name__ == '__main__':
    unittest.main()
