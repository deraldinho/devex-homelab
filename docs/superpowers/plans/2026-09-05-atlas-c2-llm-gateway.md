# Atlas C2 LLM Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans task-by-task. Steps use checkbox syntax.

**Goal:** Implementar um gateway local substituível para mini LLM que consome apenas `ContextoCognitivo` validado e nunca expõe shell, rede ou arquivos arbitrários ao modelo.

**Architecture:** C2 introduz uma interface `LLMBackend` e um `LlamaCppGateway` que monta argv fixo para um binário configurado de `llama.cpp`, com modelo configurado, timeout e limites de entrada/saída. Testes usam backend fake e executor injetável; C3 não é antecipado.

**Tech Stack:** Python stdlib, `subprocess`, `unittest`, JSON versionado.

**Spec:** `docs/superpowers/specs/2026-09-05-atlas-cognitive-llm-reaction-loop-design.md`

## Global Constraints
- C2 depende de C1 e permanece empilhado sobre o HEAD exato de C1.
- C2 não altera estado técnico, estado afetivo, enrollment ou policies de ação.
- Nenhum shell textual, `shell=True`, URL, secret ou acesso de rede é permitido.
- O modelo inicial configurável é Qwen3-0.6B GGUF Q4, mas nenhum arquivo de modelo será versionado ou baixado nesta slice.
- Entrada aceita somente `ContextoCognitivo`; payload acima do limite é rejeitado antes do backend.
- Toda execução possui timeout, stdout/stderr bounded e erro estruturado.

---
### Task 1: Contratos C2 e configuração

**Files:**
- Create: `infrastructure/pentium/atlas/modelo_llm_gateway.py`
- Create: `infrastructure/pentium/atlas/configuracao_llm.py`
- Create: `infrastructure/pentium/atlas/config_llm.json`
- Test: `infrastructure/pentium/atlas/tests/test_modelo_llm_gateway.py`
- Test: `infrastructure/pentium/atlas/tests/test_configuracao_llm.py`

- [ ] RED: testar `SolicitacaoInferencia`, `ResultadoInferencia`, erros estruturados e bounds.
- [ ] RED: testar loader de config com `backend=llama_cpp`, timeout positivo, limites de bytes/tokens e caminhos explícitos.
- [ ] GREEN: implementar modelos imutáveis, serialização e loader estrito.
- [ ] VERIFY: rodar os dois módulos de teste e `json.tool`.
- [ ] COMMIT: `feat(atlas): definir contratos do LLM Gateway C2`.

### Task 2: Gateway substituível e backend fake

**Files:**
- Create: `infrastructure/pentium/atlas/llm_gateway.py`
- Test: `infrastructure/pentium/atlas/tests/test_llm_gateway.py`

- [ ] RED: contexto válido é convertido em solicitação versionada; contexto oversized é rejeitado antes do backend.
- [ ] RED: backend fake recebe somente payload cognitivo + instrução versionada e retorna texto bounded.
- [ ] GREEN: implementar `LLMGateway.inferir(contexto, tarefa)` com protocolo de backend injetável.
- [ ] VERIFY: testes C1 + gateway.
- [ ] COMMIT: `feat(atlas): adicionar gateway substituivel de inferencia`.

### Task 3: Adapter `llama.cpp` seguro

**Files:**
- Create: `infrastructure/pentium/atlas/llama_cpp_backend.py`
- Test: `infrastructure/pentium/atlas/tests/test_llama_cpp_backend.py`

- [ ] RED: argv não usa shell; contém apenas binário, modelo, contexto/tokens e prompt gerado internamente.
- [ ] RED: modelo/binário ausente falham fechado; timeout e saída acima do bound retornam erro estruturado.
- [ ] GREEN: implementar executor injetável com `subprocess.run(argv, shell=False, timeout=...)`, `stdin`/prompt controlado e captura bounded.
- [ ] VERIFY: nenhum `os.system`, `Popen(...shell=True)`, URL ou download.
- [ ] COMMIT: `feat(atlas): integrar adapter seguro llama.cpp`.

### Task 4: Empacotamento e CI C2

**Files:**
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`
- Create: `infrastructure/pentium/atlas/tests/test_c2_llm_gateway_empacotamento.py`

- [ ] RED: instalador/CI ainda não conhecem C2.
- [ ] GREEN: empacotar código/configuração C2 sem modelo, download ou start de serviço.
- [ ] VERIFY: `bash -n`, `json.tool`, full Atlas suite, `diff --check`.
- [ ] COMMIT: `ci(atlas): integrar gate do LLM Gateway C2`.

### Task 5: Publicação empilhada

- [ ] Validar full suite e static gates.
- [ ] Push da branch C2.
- [ ] Abrir PR C2 com base `atlas/issue-20-c1-contexto-cognitivo`, nunca `main` enquanto C1 não estiver mergeada.
- [ ] Exigir CI GREEN no HEAD exato antes de qualquer restack/merge.
- [ ] Próximo passo somente C3 após C2 certificado.
