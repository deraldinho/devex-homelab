# Atlas Dashboard Cognitive Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expor no dashboard LAN do Pentium o contexto observacional/cognitivo certificado do Atlas como painel read-only com A1, A3, A4, freshness e mudanças recentes.

**Architecture:** `dashboard_collectors.py` valida e projeta `cognitive-observation-context.json` + health em uma seção `cognition` dentro de `/api/status`. `dashboard.html` renderiza essa seção sem controlar o avatar, sem novo endpoint e sem qualquer caminho de escrita.

**Tech Stack:** Python 3 stdlib, `http.server`, HTML/CSS/JavaScript sem framework, systemd user service, unittest.

**Spec:** `docs/superpowers/specs/2026-09-08-atlas-dashboard-cognitive-panel-design.md`

## Global Constraints
- Dashboard permanece estritamente read-only e bindado em `192.168.88.3:8765`.
- Snapshot cognitivo máximo: 180 segundos.
- Estados permitidos: `available`, `stale`, `unavailable`.
- Sem fallback afetivo/perceptivo sintético.
- `recent_changes` limitado a 8 itens e sem payload arbitrário.
- Avatar continua governado exclusivamente por `visual-state.json`.
- Voz deve permanecer `inactive/disabled`.
- Nenhuma mudança em L2jToren.

---
### Task 1: Collector cognitivo read-only

**Files:**
- Modify: `infrastructure/pentium/dashboard/dashboard_collectors.py`
- Modify: `infrastructure/pentium/dashboard/config.json`
- Test: `infrastructure/pentium/dashboard/tests/test_dashboard_collectors.py`

**Interfaces:**
- Consumes: snapshot schema v1 e observation health schema v1.
- Produces: `collect_cognition(config, now=...) -> dict` e `status["cognition"]`.

- [ ] **Step 1: Write failing tests** para snapshot válido, stale, ausente/corrompido/schema inválido, SHA mismatch, sanitização de `recent_changes` e ausência de fallback sintético.
- [ ] **Step 2: Run RED** com `python -m unittest infrastructure.pentium.dashboard.tests.test_dashboard_collectors` e confirmar falhas novas.
- [ ] **Step 3: Implement minimal collector** lendo caminhos configuráveis, calculando idade UTC, validando schema/SHA e projetando apenas campos permitidos.
- [ ] **Step 4: Integrate `cognition` into `collect_status`** sem permitir falha cognitiva derrubar os demais cards.
- [ ] **Step 5: Run GREEN** na suíte de collectors.
- [ ] **Step 6: Commit** `feat(atlas): expor contexto cognitivo no dashboard`.

### Task 2: UI Mente do Atlas

**Files:**
- Modify: `infrastructure/pentium/dashboard/dashboard.html`
- Test: `infrastructure/pentium/dashboard/tests/test_dashboard_ui.py`

**Interfaces:**
- Consumes: `status.cognition` de Task 1.
- Produces: seção visual Mente do Atlas integrada ao dashboard atual.

- [ ] **Step 1: Write failing UI tests** para headline, pipeline, A1/A3/A4, estados available/stale/unavailable e mudanças recentes.
- [ ] **Step 2: Run RED** na suíte `test_dashboard_ui.py`.
- [ ] **Step 3: Implement markup/CSS** mantendo layout responsivo e avatar separado do ownership cognitivo.
- [ ] **Step 4: Implement renderer JS** com percentuais somente de apresentação, escaping e mensagem explícita de indisponibilidade.
- [ ] **Step 5: Run GREEN** nos testes UI e dashboard completo.
- [ ] **Step 6: Commit** `feat(atlas): adicionar painel mente do atlas`.
### Task 3: Packaging, gates e certificação

**Files:**
- Modify if required: `infrastructure/pentium/dashboard/install-user.sh`
- Modify: `infrastructure/pentium/dashboard/tests/test_dashboard_packaging.py`
- Create: `infrastructure/pentium/dashboard/cognitive_panel_certification.py`
- Create: `infrastructure/pentium/dashboard/tests/test_cognitive_panel_certification.py`

**Interfaces:**
- Consumes: `/api/status`, service states, expected SHA e snapshot live.
- Produces: marker `ATLAS_DASHBOARD_COGNITIVE_PANEL_PHYSICAL_PASS` somente com evidência completa.

- [ ] **Step 1: Write RED certification/packaging tests** cobrindo paths, read-only HTTP, voice inactive/disabled e SHA exato.
- [ ] **Step 2: Implement certifier mínimo** que rejeita status cognitivo não available, entidade diferente, SHA mismatch, serviços incorretos ou métodos de escrita aceitos.
- [ ] **Step 3: Update packaging only where necessary** sem habilitar voz.
- [ ] **Step 4: Run dashboard suite GREEN**, `py_compile`, JSON parse, `bash -n`, `git diff --check` e UTF-8 guard.
- [ ] **Step 5: Run Atlas regression** (508+ testes) e dashboard full suite no HEAD exato.
- [ ] **Step 6: Commit** `ci(atlas): certificar painel cognitivo do dashboard`.

### Task 4: Deploy físico no Pentium

**Files:**
- Runtime deploy under `~/pentium-agent/` only; no source mutation outside the certified archive.

**Interfaces:**
- Consumes: exact feature HEAD from Tasks 1-3.
- Produces: dashboard LAN serving live cognition and physical certification JSON.

- [ ] **Step 1: Backup and deploy exact SHA archive** to Pentium.
- [ ] **Step 2: Restart only dashboard service as needed**; observation remains active and voice remains inactive/disabled.
- [ ] **Step 3: Verify `/api/status`** returns `cognition.status=available`, exact SHA and `entity_id=x99` for a fresh real snapshot.
- [ ] **Step 4: Verify isolated stale/unavailable cases** without modifying production runtime files.
- [ ] **Step 5: Verify HTTP POST/PUT/PATCH/DELETE remain 405** and dashboard health stays available.
- [ ] **Step 6: Run deployed certifier** and require `ATLAS_DASHBOARD_COGNITIVE_PANEL_PHYSICAL_PASS`.
- [ ] **Step 7: Run verification-before-completion**, then use finishing-a-development-branch and present the three integration choices.
