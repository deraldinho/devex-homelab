# Atlas S1 Semantic Event + Adapter Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar o vocabulário semântico interno do Atlas e adapters explícitos para Stimulus existentes sem alterar contratos de serviços externos.

**Architecture:** `StimulusSource` continua reduzindo contratos externos. A nova `FronteiraSemantica` traduz `Stimulus` para `EventoSemantico` bounded/versionado; um `RegistroSemantico` é o único dono dos códigos compactos. S2 consumirá estes eventos no Fast Router.

**Tech Stack:** Python 3 stdlib, dataclasses, Enum, hashlib/json, unittest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-06-atlas-semantic-event-adapter-boundary-design.md`

## Global Constraints

- Nenhum serviço externo conhece códigos ou registry interno do Atlas.
- Máximo 16 atributos escalares, strings de atributo até 128 chars e fan-out máximo 32.
- Fonte desconhecida ou significado inválido falha fechado.
- S1 não adiciona LLM, embedding, cache vetorial, áudio ou Action Engine.
- Existing technical observation remains authoritative and unaffected by semantic translation failures.

---

### Task 1: Canonical Semantic Model + Registry

**Files:**
- Create: `infrastructure/pentium/atlas/modelo_evento_semantico.py`
- Create: `infrastructure/pentium/atlas/registro_semantico.py`
- Test: `infrastructure/pentium/atlas/tests/test_modelo_evento_semantico.py`
- Test: `infrastructure/pentium/atlas/tests/test_registro_semantico.py`

**Interfaces:** `EventoSemantico`, `EntidadeSemantica`, `TipoEventoSemantico`, `EstadoSemantico`, `RegistroSemantico.compactar()`, `RegistroSemantico.fingerprint()`.
- [ ] **Step 1: Write failing model/registry tests**

Test immutable validation, attribute bounds, stable numeric compact payload and fingerprint equality for semantically identical events.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_modelo_evento_semantico infrastructure.pentium.atlas.tests.test_registro_semantico -v`
Expected: import/module failure because S1 model does not exist.

- [ ] **Step 3: Implement minimal model and registry**

Use readable string enums in normal code. Registry maps enums to stable integer codes and hashes canonical compact JSON; do not expose external protocol helpers.

- [ ] **Step 4: Re-run focused tests and commit GREEN**

Commit: `feat(atlas): adicionar modelo semantico S1`

### Task 2: Explicit Domain Adapters

**Files:**
- Create: `infrastructure/pentium/atlas/adaptadores_semanticos.py`
- Test: `infrastructure/pentium/atlas/tests/test_adaptadores_semanticos.py`

**Interfaces:** `AdaptadorStatusHost`, `AdaptadorPresencaWifi`, `FronteiraSemantica.traduzir(stimulus) -> tuple[EventoSemantico, ...]`, `criar_fronteira_semantica_padrao()`.

- [ ] **Step 1: Write failing adapter tests**

Cover `pentium.self`, `core`, `x99`, `wifi.presence`, source error, recovery, unknown source and fan-out >32 rejection.

- [ ] **Step 2: Confirm RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_adaptadores_semanticos -v`
Expected: module missing.
- [ ] **Step 3: Implement adapters minimally**

Host adapter maps existing Stimulus kinds/status into semantic enums. Wi-Fi adapter emits one bounded semantic event per presence event and carries only scalar identifiers/changed-field count, never the source list itself.

- [ ] **Step 4: Re-run focused tests and commit GREEN**

Commit: `feat(atlas): traduzir stimuli na fronteira semantica`

### Task 3: Architecture/PRD + Packaging Contract

**Files:**
- Modify: `docs/architecture/atlas-local-intelligence-design.md`
- Modify: `docs/prd/PRD-0006-atlas-local-intelligence.md`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`
- Test: `infrastructure/pentium/atlas/tests/test_s1_semantic_boundary_empacotamento.py`

- [ ] **Step 1: Write failing packaging/governance test**

Require architecture and PRD to state that external services do not depend on Atlas semantic vocabulary; require installer/CI to include all S1 modules and marker `DEVEX_HOMELAB_ATLAS_SEMANTIC_S1_PASS`.

- [ ] **Step 2: Confirm RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_s1_semantic_boundary_empacotamento -v`
Expected: missing docs/module/marker assertions.

- [ ] **Step 3: Update docs, installer and Foundation CI**

Document `external contract -> StimulusSource -> Stimulus -> FronteiraSemantica -> EventoSemantico`; add py_compile/package entries and S1 marker.

- [ ] **Step 4: Verify and commit GREEN**

Run focused packaging test, `bash -n infrastructure/pentium/atlas/install-user.sh`, JSON validation and `git diff --check`.
Commit: `docs(atlas): oficializar fronteira semantica S1`.
### Task 4: Full Verification, PR and Checkpoint

**Files:** no new production files unless verification exposes a defect.

- [ ] **Step 1: Run complete Atlas suite**

Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py'`
Expected: all tests GREEN.

- [ ] **Step 2: Run repository hygiene checks**

Run: `git diff --check`, `bash -n infrastructure/pentium/atlas/install-user.sh`, and inspect `git status --short`.

- [ ] **Step 3: Push branch and open Draft PR based on C5 recovery branch**

Base: `atlas/issue-20-c5-physical-certification-recovery` so S1 preserves the exact physical findings and readiness fix. PR remains Draft until exact-head CI is GREEN.

- [ ] **Step 4: Require exact-head Foundation CI**

No previous SHA evidence is reusable. Inspect job steps/logs and require `DEVEX_HOMELAB_ATLAS_SEMANTIC_S1_PASS`, existing Atlas/C5/K1/K2 markers and Foundation pass on the new SHA.

- [ ] **Step 5: Add `/checkpoint`**

Record exact HEAD, implementation, tests, CI, no external service contract changes, C5 physical blocker preserved, and next single step `S2 — Fast Router`.
