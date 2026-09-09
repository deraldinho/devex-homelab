import sys
from pathlib import Path
from atlas.llama_cpp_backend import LlamaCppBackend
from atlas.modelo_llm_gateway import SolicitacaoInferencia
mode = sys.argv[1]
root = Path.home() / 'pentium-agent' / 'runtime' / 'llama'
backend = LlamaCppBackend(root/'build/bin/llama-cli', root/'models/Qwen3-0.6B-Q4_0.gguf', timeout_s=90, max_saida_bytes=8192)
req = SolicitacaoInferencia(1, 'teste_fisico', '{"mensagem":"responda de forma curta confirmando que esta ouvindo"}', 512, mode)
out = backend.inferir(req)
print(f'MODE={mode} SUCCESS={out.sucesso} ERROR={out.erro} MS={out.duracao_ms}')
print(out.texto or '')
