from pathlib import Path
from atlas.llama_cpp_backend import LlamaCppBackend
from atlas.modelo_llm_gateway import SolicitacaoInferencia

root = Path.home() / "pentium-agent" / "runtime" / "llama"
backend = LlamaCppBackend(
    root / "build/bin/llama-cli",
    root / "models/Qwen3-0.6B-Q4_0.gguf",
    timeout_s=60,
    max_saida_bytes=8192,
)
for mode in ("off", "on"):
    req = SolicitacaoInferencia(
        1,
        "teste_fisico",
        '{"mensagem":"responda somente com JSON valido e texto curto"}',
        512,
        mode,
    )
    out = backend.inferir(req)
    print(f"MODE={mode} SUCCESS={out.sucesso} ERROR={out.erro} MS={out.duracao_ms}")
    print((out.texto or "")[:600])
