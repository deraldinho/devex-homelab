# Atlas Hermes v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o owner cognitivo llama.cpp por um backend Hermes one-shot seguro, mantendo o domínio cognitivo, policy e executores existentes.

**Architecture:** `LLMGateway` continua sendo a fronteira do runtime. Um novo `HermesAdapter` executa `hermes -p atlas -z <prompt> --provider openai-codex`, sem shell/tools concedidos pela Atlas, valida limites e devolve `ResultadoInferencia`. O `CognitiveRuntimeOwner` deixa de possuir `llama-server`; indisponibilidade de Hermes degrada somente a cognição.

**Tech Stack:** Python 3, subprocess, dataclasses, pytest, systemd user service, Hermes Agent CLI.

**Spec:** `docs/superpowers/specs/2026-09-09-atlas-hermes-codex-migration-design.md`

## Global Constraints

- Provider único nesta slice: `openai-codex`.
- Profile dedicado: `atlas`.
- Nenhum token OAuth em Git, runtime JSON, dashboard, logs ou eventos.
- Nenhum acesso direto do Hermes a SSH, systemd, filesystem de projeto ou capabilities Atlas.
- Voice permanece disabled/inactive.
- Observation, Affective, memória, chat, SSE, plano de ações, policy e avatar continuam funcionando.
- Falha cognitiva usa razão neutra `cognitive_backend_unavailable`.

---

### Task 1: Contrato e configuração Hermes

**Files:**
- Create: `infrastructure/pentium/atlas/config_hermes.py`
- Create: `infrastructure/pentium/atlas/config_hermes.json`
- Test: `infrastructure/pentium/atlas/tests/test_config_hermes.py`

**Interfaces:**
- Produces: `HermesConfig`, `load_hermes_config(path)`.
- Bounds: timeout > 0, response bytes > 0, provider exactly `openai-codex`, profile non-empty.

- [ ] Escrever testes RED para configuração válida e provider inválido.
- [ ] Executar o teste e confirmar RED por módulo ausente.
- [ ] Implementar configuração mínima sem segredo.
- [ ] Executar o teste e confirmar GREEN.

### Task 2: HermesAdapter one-shot

**Files:**
- Create: `infrastructure/pentium/atlas/hermes_adapter.py`
- Test: `infrastructure/pentium/atlas/tests/test_hermes_adapter.py`

**Interfaces:**
- Consumes: `HermesConfig`, `SolicitacaoInferencia`.
- Produces: `HermesAdapter.inferir(...) -> ResultadoInferencia`.
- Command: `hermes -p atlas -z <prompt> --provider openai-codex`.

- [ ] Escrever testes RED para sucesso JSON, timeout, auth/backend failure, oversized e provider fixo.
- [ ] Confirmar RED.
- [ ] Implementar subprocess bounded, UTF-8 estrito e sanitização de erro.
- [ ] Confirmar GREEN.

### Task 3: Wiring do cognitive daemon

**Files:**
- Modify: `infrastructure/pentium/atlas/cognitive_daemon.py`
- Modify: `infrastructure/pentium/atlas/reaction_loop_cognitivo.py`
- Test: `infrastructure/pentium/atlas/tests/test_cognitive_daemon.py`
- Test: `infrastructure/pentium/atlas/tests/test_cognitive_chat_runtime.py`

**Interfaces:**
- `build_owner()` cria `HermesAdapter` e `LLMGateway` sem iniciar `llama-server`.
- `CognitiveRuntimeOwner.start()` não espera socket de LLM.
- Falha de inferência retorna `RespostaCognitiva.razao == "cognitive_backend_unavailable"`.

- [ ] Escrever/ajustar testes RED para owner sem llama e razão degradada neutra.
- [ ] Confirmar RED.
- [ ] Substituir wiring llama pelo Hermes e simplificar lifecycle do owner.
- [ ] Confirmar GREEN dos testes cognitivos afetados.

### Task 4: Packaging e regressão

**Files:**
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `.github/workflows/atlas-avatar-ci.yml` ou gate Atlas equivalente, se necessário.
- Test: `infrastructure/pentium/atlas/tests/test_action_chat_packaging.py`
- Create: `infrastructure/pentium/atlas/tests/test_hermes_packaging.py`

**Interfaces:**
- Installer valida binário Hermes e deixa OAuth para etapa humana.
- CI rejeita reintrodução de wiring produtivo para Qwen/llama no daemon cognitivo.

- [ ] Criar teste RED de packaging e ausência de wiring llama no daemon.
- [ ] Confirmar RED.
- [ ] Ajustar installer/gate mínimo.
- [ ] Confirmar GREEN.

### Task 5: Certificação da slice

- [ ] Rodar testes Hermes direcionados.
- [ ] Rodar toda suíte `infrastructure/pentium/atlas/tests`.
- [ ] Rodar checks de sintaxe/packaging aplicáveis.
- [ ] Verificar `git diff --check` e `git status`.
- [ ] Commitar com mensagem objetiva e registrar HEAD exato no checkpoint da PR.

## Critérios de aceite desta slice

1. O runtime cognitivo de produção não instancia nem inicia llama.cpp.
2. Hermes usa profile `atlas` e provider `openai-codex` explicitamente.
3. O adapter não persiste ou publica segredo OAuth.
4. Timeout, saída inválida/oversized e falha do processo degradam de modo bounded.
5. Chat e plano de ações continuam atravessando `ReactionLoopCognitivo`/`ActionPolicy`.
6. A suíte Atlas permanece GREEN no mesmo HEAD local antes de push/checkpoint.
