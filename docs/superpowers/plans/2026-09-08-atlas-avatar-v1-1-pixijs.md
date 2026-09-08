# Atlas Avatar v1.1 PixiJS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o avatar full-body PixiJS do Atlas mantendo `EstadoVisualAtlas` como contrato único e SVG como fallback seguro.

**Architecture:** O dashboard carrega PixiJS localmente, inicializa `AtlasAvatarEngine` de forma assíncrona e continua atualizando o SVG fallback. `AtlasAvatarRenderer` normaliza o contrato, atualiza metadados e delega ao engine somente quando ele está pronto. O servidor permanece read-only e trata assets estáticos separadamente das respostas dinâmicas.

**Tech Stack:** Python stdlib HTTP server, JavaScript ES2022, PixiJS 8.20.1, SVG/CSS fallback, unittest.

**Spec:** `docs/superpowers/specs/2026-09-08-atlas-avatar-v1-1-pixijs-design.md`

## Global Constraints

- `EstadoVisualAtlas` é a única entrada semântica.
- Dashboard permanece GET-only.
- PixiJS é local em runtime e validado por SHA-256.
- SVG atual permanece fallback.
- Sem LLM, áudio bruto, shell ou telemetria bruta na camada visual.
- Respostas dinâmicas permanecem limitadas a 256 KiB.

---

### Task 1: Normalização e engine PixiJS

**Files:**
- Create: `infrastructure/pentium/dashboard/atlas-avatar-engine.js`
- Modify: `infrastructure/pentium/dashboard/atlas-avatar-renderer.js`
- Test: `infrastructure/pentium/dashboard/tests/test_avatar_pixijs.py`

- [x] Criar testes para modos, arquétipos, rig full-body e normalização.
- [x] Implementar `AtlasAvatarEngine` com init fail-safe.
- [x] Implementar clamp e defaults em `AtlasAvatarRenderer.normalize`.
- [x] Preservar SVG como fallback enquanto Pixi não estiver ready.

### Task 2: Runtime local e integridade

**Files:**
- Create: `infrastructure/pentium/dashboard/fetch-pixi.sh`
- Modify: `infrastructure/pentium/dashboard/install-user.sh`
- Test: `infrastructure/pentium/dashboard/tests/test_dashboard_packaging.py`

- [x] Fixar PixiJS 8.20.1.
- [x] Fixar SHA-256 do asset oficial.
- [x] Baixar somente na instalação e instalar localmente.
- [x] Validar sintaxe JS antes do restart do serviço.

### Task 3: Dashboard e servidor read-only

**Files:**
- Modify: `infrastructure/pentium/dashboard/dashboard.html`
- Modify: `infrastructure/pentium/dashboard/atlas_dashboard.py`
- Test: `infrastructure/pentium/dashboard/tests/test_dashboard_ui.py`

- [x] Adicionar stage Pixi sem remover SVG.
- [x] Carregar bundle, engine e renderer localmente.
- [x] Servir assets JavaScript via GET.
- [x] Manter métodos de escrita em 405.
- [x] Limitar assets a 1 MiB e respostas dinâmicas a 256 KiB.

### Task 4: Certificação

- [ ] Executar suíte dashboard completa no HEAD exato.
- [ ] Executar `node --check` nos assets próprios.
- [ ] Executar `python -m py_compile` e `bash -n`.
- [ ] Confirmar workflow CI do HEAD.
- [ ] Executar smoke físico/headless quando x99/Pentium estiverem acessíveis.
