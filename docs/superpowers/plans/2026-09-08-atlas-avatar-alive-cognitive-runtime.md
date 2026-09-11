# Atlas Alive + Cognitive Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Entregar Motion Engine v1.2 e conectar Qwen ao runtime cognitivo 24/7 com isolamento de falhas.

**Architecture:** Motion é executado localmente no browser e consome somente `EstadoVisualAtlas`. Cognição roda em `atlas-cognitive.service`, consome o contexto publicado pelo Observation, usa o backend residente e projeta somente flags efêmeras e metadados seguros.

**Tech Stack:** Python 3 stdlib, systemd user services, Unix datagram/HTTP sockets, llama.cpp/Qwen3-0.6B, JavaScript ES2022, PixiJS 8.20.1, unittest, Node syntax checks.

**Spec:** `docs/superpowers/specs/2026-09-08-atlas-avatar-alive-cognitive-runtime-design.md`

## Global Constraints

- Observation/Affective nunca aguardam inferência LLM.
- Renderer não acessa LLM, memória, áudio bruto, shell ou telemetria bruta.
- Voz não é habilitada nem reiniciada por esta slice.
- Dashboard permanece GET-only.
- Modelo e socket residentes têm caminhos canônicos versionados.

### Task 1: Motion Engine v1.2
- [x] Criar testes RED para smoothing, blink, saccades e secondary motion.
- [x] Implementar `atlas-avatar-motion.js`.
- [x] Articular braços/antebraços/mãos e integrar motion ao Pixi renderer.
- [x] Empacotar e servir o novo asset.
- [x] Validar Node e testes do dashboard.

### Task 2: Integrar base afetiva e contexto cognitivo
- [x] Incorporar semanticamente o runtime afetivo visual certificado.
- [x] Incorporar a ponte Observation → contexto cognitivo e painel Mente do Atlas.
- [x] Preservar `AtlasAvatarRenderer.render(status.visual)` como fronteira estável.

### Task 3: Cognitive Runtime 24/7
- [x] Criar testes RED do daemon, sinais de ativação e packaging.
- [x] Implementar `cognitive_daemon.py` usando Reaction Loop, cache e memória existentes.
- [x] Usar `llama-server` residente com fallback `llama-cli`.
- [x] Criar `atlas-cognitive.service` isolado de Observation e Voice.
- [x] Corrigir o caminho canônico do modelo Qwen instalado.

### Task 4: Mux visual de cognição e voz
- [x] Criar socket cognitivo separado.
- [x] Publicar `pensando=true/false` ao redor da inferência.
- [x] Combinar cognição e voz no `AffectiveRuntime` sem clobber de flags.
- [x] Manter fallback no-op somente para ambiente sem AF_UNIX.

### Task 5: Dashboard Qwen e certificação
- [x] Expor metadados seguros de `cognitive-runtime.json`.
- [x] Adicionar serviço cognitivo e painel Qwen ao dashboard.
- [ ] Executar suíte completa e checks no HEAD final.
- [ ] Confirmar CI Foundation e Atlas Avatar no HEAD final.
- [ ] Implantar no Pentium e certificar Qwen residente + browser smoke.
