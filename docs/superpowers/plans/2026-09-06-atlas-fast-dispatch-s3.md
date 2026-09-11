# Atlas S3 Fast Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar um dispatcher tipado e bounded entre `DecisaoFastRouter` e os caminhos de reação, afeto, cache e LLM diferido.

**Architecture:** `FastDispatcher` preserva a ordem das lanes escolhidas pela S2 e delega cada lane a uma porta explícita. `DROP` é terminal; falhas são isoladas; `SLOW_LLM` apenas agenda uma intenção em fila bounded, sem importar ou chamar o gateway LLM.

**Tech Stack:** Python 3, `dataclasses`, `enum`, `typing.Protocol`, `collections.deque`, `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-06-atlas-fast-dispatch-reaction-integration-s3-design.md`

## Global Constraints

- Base exata: `9407af45c5070dc52de4cfea85bd08acc32187cc`.
- `FastRouter` continua puro e não executa lanes.
- Dispatcher não recalcula score, health, severidade ou autorização.
- `ReactionEngine`, `MotorEstadoAfetivo` e `CognitiveCache` mantêm ownership.
- `SLOW_LLM` nunca executa inferência inline.
- Nenhuma lane executa shell, SSH, rede ou CONTROL diretamente.
- TDD obrigatório em cada task; full regression e Foundation CI no HEAD exato.

---### Task 1: Modelo imutável de resultado de dispatch

**Files:**
- Create: `infrastructure/pentium/atlas/modelo_fast_dispatch.py`
- Test: `infrastructure/pentium/atlas/tests/test_modelo_fast_dispatch.py`

**Interfaces:**
- Consumes: `RotaSemantica` de `modelo_fast_router.py`.
- Produces: `EstadoLaneDispatch`, `ResultadoLaneDispatch`, `ResultadoFastDispatch`.

- [ ] **Step 1: Write the failing model tests**

Cobrir: lanes solicitadas preservam ordem; detalhe vazio/maior que 128 é rejeitado; `DROP` não pode coexistir; propriedades `entregues`, `deferidas`, `falhas` refletem resultados.

- [ ] **Step 2: Run RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_modelo_fast_dispatch -v`
Expected: FAIL por módulo/modelos inexistentes.

- [ ] **Step 3: Implement minimal immutable model**

Usar `Enum` para `DELIVERED`, `DEFERRED`, `FAILED`; dataclasses frozen; validar duplicidade, bounds e consistência entre rota solicitada e resultado.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_modelo_fast_dispatch -v`
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat(atlas): definir modelo do fast dispatch S3"`
### Task 2: Dispatcher e portas explícitas

**Files:**
- Create: `infrastructure/pentium/atlas/fast_dispatch.py`
- Test: `infrastructure/pentium/atlas/tests/test_fast_dispatch.py`

**Interfaces:**
- Consumes: `EventoSemantico`, `DecisaoFastRouter`, modelos Task 1.
- Produces: protocols `PortaFastReaction`, `PortaAffect`, `PortaCacheLookup`, `PortaSlowLlm`, classe `FastDispatcher.dispatch(evento, decisao)`.

- [ ] **Step 1: Write failing dispatcher tests**

Cobrir: `DROP` zero chamadas; ordem preservada; FAST_REACTION + AFFECT entregues; falha de uma porta não bloqueia a seguinte; CACHE_LOOKUP delegado; SLOW_LLM devolve `DEFERRED` e não executa gateway.

- [ ] **Step 2: Run RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_fast_dispatch -v`
Expected: FAIL por dispatcher inexistente.

- [ ] **Step 3: Implement minimal dispatcher**

Ports recebem apenas `EventoSemantico`; retorno da porta vira detalhe bounded. Ausência de porta para lane solicitada vira `FAILED` com detalhe canônico. Exceções são capturadas por lane e registradas sem interromper lanes seguintes.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_fast_dispatch -v`
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat(atlas): implementar fast dispatcher S3"`

### Task 3: Porta bounded para slow path

**Files:**
- Create: `infrastructure/pentium/atlas/slow_llm_defer_queue.py`
- Test: `infrastructure/pentium/atlas/tests/test_slow_llm_defer_queue.py`

**Interfaces:**
- Produces: `IntencaoSlowLlm`, `SlowLlmDeferQueue.defer(evento) -> str`, `pop() -> IntencaoSlowLlm | None`.

- [ ] **Step 1: Write failing queue tests**

Cobrir FIFO, bound positivo obrigatório, overflow fail-closed sem desalojar item antigo, payload imutável com `correlation_id` e entidade/tipo do evento.

- [ ] **Step 2: Run RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_slow_llm_defer_queue -v`
Expected: FAIL por módulo inexistente.

- [ ] **Step 3: Implement minimal bounded queue**

Usar `deque`; `defer` só enfileira intenção tipada e retorna detalhe canônico; não importar `llm_gateway`/`reaction_loop_cognitivo`.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_slow_llm_defer_queue -v`
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat(atlas): adicionar defer bounded do slow LLM S3"`
### Task 4: Packaging, docs e certificação

**Files:**
- Modify: `docs/architecture/atlas-local-intelligence-design.md`
- Modify: `docs/prd/PRD-0006-atlas-local-intelligence.md`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`
- Create: `infrastructure/pentium/atlas/tests/test_s3_fast_dispatch_empacotamento.py`

**Interfaces:**
- Produces marker canônico `DEVEX_HOMELAB_ATLAS_FAST_DISPATCH_S3_PASS`.

- [ ] **Step 1: Write failing packaging test**

Exigir docs S3, inclusão dos novos módulos no installer/CI, marker canônico e ausência de imports proibidos em `fast_dispatch.py`/`slow_llm_defer_queue.py`.

- [ ] **Step 2: Run RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_s3_fast_dispatch_empacotamento -v`
Expected: FAIL enquanto docs/packaging não estiverem atualizados.

- [ ] **Step 3: Apply minimal packaging/docs changes**

Documentar Fast Dispatch S3 e atualizar installer/CI somente com arquivos S3 e o teste canônico.

- [ ] **Step 4: Verify focused and full suite**

Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py'`
Run: `python -m py_compile infrastructure/pentium/atlas/modelo_fast_dispatch.py infrastructure/pentium/atlas/fast_dispatch.py infrastructure/pentium/atlas/slow_llm_defer_queue.py`
Run: `bash -n infrastructure/pentium/atlas/install-user.sh`
Run: `git diff --check 9407af45c5070dc52de4cfea85bd08acc32187cc..HEAD`
Expected: all GREEN.

- [ ] **Step 5: Commit, push, Draft PR, exact-head CI and checkpoint**

`git commit -m "docs(atlas): oficializar fast dispatch S3"`; push branch; abrir Draft PR baseada em `atlas/issue-20-s2-fast-router`; exigir Foundation CI GREEN no SHA exato; publicar `/checkpoint` com SHA, testes, marker e gates.
