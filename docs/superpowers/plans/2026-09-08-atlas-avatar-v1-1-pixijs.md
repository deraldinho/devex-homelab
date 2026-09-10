# Atlas Avatar v1.1 PixiJS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar o Avatar Atlas full-body com PixiJS, fallback SVG e integração read-only ao `EstadoVisualAtlas`.

**Architecture:** `dashboard.html` hospeda um stage Pixi e mantém o SVG fallback. `atlas-avatar-renderer.js` normaliza estado e escolhe engine/fallback; `atlas-avatar-engine.js` encapsula PixiJS, rig e animação. Bundle PixiJS é local e servido pelo dashboard.

**Tech Stack:** Python stdlib HTTP, JavaScript ES2020, PixiJS 8.20.1, SVG fallback, unittest.

**Spec:** `docs/superpowers/specs/2026-09-08-atlas-avatar-v1-1-pixijs-design.md`

## Global Constraints

- `EstadoVisualAtlas` é a única entrada semântica.
- dashboard permanece GET-only/read-only.
- sem CDN, LLM, áudio bruto ou controle operacional no renderer.
- fallback SVG deve funcionar se Pixi falhar.
- `prefers-reduced-motion` e aba oculta reduzem animação.

---

### Task 1: Contrato visual normalizado
- [ ] Criar testes RED para clamp de intensidade/movimento/transição e defaults.
- [ ] Implementar normalização no renderer sem reclassificar semântica.
- [ ] Validar RED→GREEN e commit.

### Task 2: Engine PixiJS e bundle local
- [ ] Criar testes RED exigindo bundle, engine e endpoints GET-only.
- [ ] Vendorizar `pixi.js@8.20.1` localmente.
- [ ] Implementar `AtlasAvatarEngine` com init assíncrono e fallback.
- [ ] Validar sintaxe/testes e commit.

### Task 3: Rig full-body e expressões
- [ ] Criar testes RED para corpo, cabeça, olhos, boca, braços e sete arquétipos.
- [ ] Implementar rig vetorial em `PIXI.Graphics` com pivôs e poses.
- [ ] Implementar olhar, blink, lip-sync estilizado, postura e gestos mínimos.
- [ ] Validar e commit.

### Task 4: State machine e motion policy
- [ ] Criar testes RED para quatro modos, reação prioritária, reduced-motion e visibility.
- [ ] Implementar transições, idle bounded e cancelamento por reação.
- [ ] Validar e commit.

### Task 5: Integração, packaging e certificação
- [ ] Integrar stage Pixi no card mantendo SVG fallback e metadados existentes.
- [ ] Empacotar todos os assets no instalador e servidor HTTP.
- [ ] Rodar suíte dashboard completa, checks de sintaxe e diff.
- [ ] Commit/push e registrar HEAD exato.
