# Plano K2 — Prefix/KV Cache

1. TDD para `LlamaCppServerRuntime`: argv fixo, Unix socket, lifecycle e health bounded.
2. TDD para `LlamaCppResidentBackend`: POST `/completion`, `cache_prompt=true`, `n_cache_reuse` bounded e parsing de resposta.
3. TDD para fallback ao `LlamaCppBackend` CLI quando socket/runtime falhar.
4. Versionar configuração K2 sem persistir cache em disco.
5. Integrar installer/CI marker K2 sem iniciar serviço automaticamente.
6. Repetir Architecture & Business Rules Check no diff final.
7. Rodar regressão completa, gates estáticos, publicar PR Draft e exigir CI do HEAD exato.