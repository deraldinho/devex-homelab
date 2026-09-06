# Atlas Fast Router S2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o roteador semântico fast/slow determinístico do Atlas sem colocar LLM, cache ou I/O no caminho crítico.

**Architecture:** `EventoSemantico` entra em um `FastRouter` puro que calcula score bounded e devolve lanes tipadas. `DROP` é exclusivo; fast reaction/affect podem coexistir e slow LLM é apenas uma deferência assíncrona para faixa ambígua.

**Tech Stack:** Python 3 stdlib, dataclasses/enums, JSON config, unittest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-06-atlas-fast-router-s2-design.md`

## Global Constraints

- Router sem I/O e sem imports de LLM/cache/áudio/shell/SSH/rede.
- Nenhum serviço externo conhece o vocabulário interno.
- LLM não decide saúde, criticidade, autorização ou ação.
- TDD RED → GREEN por tarefa.
- `DROP` nunca coexiste com outra lane.

---

### Task 1: Modelo e política S2

**Files:**
- Create: `infrastructure/pentium/atlas/modelo_fast_router.py`
- Create: `infrastructure/pentium/atlas/configuracao_fast_router.py`
- Create: `infrastructure/pentium/atlas/config_fast_router.json`
- Test: `infrastructure/pentium/atlas/tests/test_modelo_fast_router.py`
- Test: `infrastructure/pentium/atlas/tests/test_configuracao_fast_router.py`
**Interfaces:**
- Produces: `RotaSemantica`, `DecisaoFastRouter`, `PoliticaFastRouter`, `carregar_politica_fast_router(path)`.

- [ ] Escrever testes RED para imutabilidade, lanes válidas e `DROP` exclusivo.
- [ ] Escrever testes RED para schema/config e coerência dos thresholds.
- [ ] Executar os testes e confirmar falha por módulos ausentes.
- [ ] Implementar somente modelo/config necessários.
- [ ] Reexecutar testes, `py_compile` e `git diff --check`.
- [ ] Commit: `feat(atlas): definir politica do fast router S2`.

### Task 2: Roteamento determinístico

**Files:**
- Create: `infrastructure/pentium/atlas/fast_router.py`
- Test: `infrastructure/pentium/atlas/tests/test_fast_router.py`

**Interfaces:**
- Consumes: `EventoSemantico`, `PoliticaFastRouter`.
- Produces: `FastRouter.decidir(evento: EventoSemantico) -> DecisaoFastRouter`.

- [ ] Escrever RED para baseline saudável → `DROP`.
- [ ] Escrever RED para critical → `FAST_REACTION + AFFECT`, sem cache/LLM.
- [ ] Escrever RED para recovery → `FAST_REACTION + AFFECT`.
- [ ] Escrever RED para baixa novidade → `AFFECT + CACHE_LOOKUP`.
- [ ] Escrever RED para evento novo de score alto → fast path sem LLM.
- [ ] Escrever RED para evento novo ambíguo → `AFFECT + SLOW_LLM`.
- [ ] Escrever RED garantindo que presença Wi-Fi nunca acorda LLM na S2.
- [ ] Implementar score e precedência mínima; reexecutar testes.
- [ ] Commit: `feat(atlas): implementar fast router S2`.
### Task 3: Governança e empacotamento

**Files:**
- Modify: `docs/architecture/atlas-local-intelligence-design.md`
- Modify: `docs/prd/PRD-0006-atlas-local-intelligence.md`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`
- Test: `infrastructure/pentium/atlas/tests/test_s2_fast_router_empacotamento.py`

- [ ] Escrever RED exigindo regra fast/slow, ausência de dependência externa e marker S2.
- [ ] Atualizar Architecture/PRD com a precedência do router e LLM fora do critical path.
- [ ] Empacotar modelo/config/router no installer e Foundation CI.
- [ ] Emitir `DEVEX_HOMELAB_ATLAS_FAST_ROUTER_S2_PASS` somente após testes.
- [ ] Executar teste focado, `bash -n` e `git diff --check`.
- [ ] Commit: `docs(atlas): oficializar fast router S2`.

### Task 4: Certificação da slice

- [ ] Executar `python -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py'`.
- [ ] Executar `python -m py_compile` nos módulos S2.
- [ ] Executar `bash -n infrastructure/pentium/atlas/install-user.sh`.
- [ ] Executar `git diff --check` e verificar ancestry sobre o HEAD S1 `5cb448e7d6cb9bb0936a2a37c6066fc783908af6`.
- [ ] Push da branch `atlas/issue-20-s2-fast-router` e criar PR Draft com base na branch S1.
- [ ] Exigir Foundation CI GREEN no HEAD exato.
- [ ] Publicar `/checkpoint` com SHA, implementação, CI, gates e próximo passo S3.

## Self-review

Cobertura: modelo, política, roteamento, baixo acoplamento, packaging, CI e checkpoint estão mapeados. Não há implementação de cache, reaction palette ou integração LLM nesta slice.