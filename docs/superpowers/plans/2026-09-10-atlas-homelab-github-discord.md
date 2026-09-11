# Atlas HomeLab + GitHub + Discord Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o Atlas observar Pentium/Core/x99 e GitHub, e permitir conversa Hermes por dashboard ou Discord usando um Ãºnico pipeline cognitivo.

**Architecture:** Generalizar a composiÃ§Ã£o do ObservationRuntime para fontes locais, MANAGED e GitHub. Estender `ChatEnvelope` com rota multicanal e adicionar um gateway Discord fino que apenas ingressa mensagens e entrega respostas roteadas.

**Tech Stack:** Python 3.14+, stdlib, unittest, JSON/JSONL, GitHub CLI (`gh api`) READ-only, `discord.py` somente no processo Discord.

**Spec:** `docs/superpowers/specs/2026-09-10-atlas-homelab-github-discord-design.md`

## Global Constraints

- SSH somente via `ManagedReadService`.
- GitHub READ-only.
- Secrets somente via ambiente/secret file ignorado pelo Git.
- Nenhum token em Stimulus, journal, config versionada ou dashboard events.
- Falha GitHub/Discord nÃ£o derruba observaÃ§Ã£o fÃ­sica.
- TDD: teste deve existir antes da implementaÃ§Ã£o correspondente.

---

### Task 1: ComposiÃ§Ã£o fÃ­sica completa

**Files:** modificar `agent/config.json`, `atlas/observation_config.json`, `atlas/dual_zone_runtime.py`, `atlas/observation_daemon.py`; criar `atlas/local_health.py`; testar em `atlas/tests/test_homelab_observation_composition.py`.

**Interfaces:** `collect_pentium_self() -> dict`; `build_dual_zone_runtime(..., local_sources=(), extra_sources=()) -> ObservationRuntime`.

- [ ] Criar teste provando que `pentium.self`, `managed.core`, `managed.x99` e `wifi.presence` coexistem.
- [ ] Verificar RED por ausÃªncia de `local_sources`/`managed.core`.
- [ ] Implementar collector local bounded e composiÃ§Ã£o genÃ©rica.
- [ ] Verificar GREEN e regressÃ£o dos testes I1.
- [ ] Commit: `feat(atlas): observe full homelab topology`.
### Task 2: Fonte GitHub READ-only

**Files:** criar `atlas/github_observation.py`, `atlas/config_github.json`, `atlas/tests/test_github_observation.py`; modificar `atlas/observation_daemon.py` e `atlas/observation_config.json`.

**Interfaces:** `GitHubCliClient(runner=..., timeout_s=...)`; `GitHubObservationSource(repo, client)`; `build_github_sources(repositories, client=...) -> tuple[StimulusSource, ...]`.

- [ ] Testar normalizaÃ§Ã£o de PR, Issue e workflow run e ausÃªncia de headers/secrets no payload.
- [ ] Verificar RED por mÃ³dulo inexistente.
- [ ] Implementar cliente `gh api` bounded com `shell=False`, allowlist de repos e payload reduzido.
- [ ] Usar autenticação externa do GitHub CLI (`gh auth`/`GH_TOKEN`), sem token dentro do Atlas.
- [ ] Verificar GREEN e isolamento quando GitHub CLI/credencial estiver indisponível.
- [ ] Commit: `feat(atlas): observe github delivery state`.

### Task 3: ChatInbox multicanal

**Files:** modificar `atlas/chat_inbox.py`, `atlas/cognitive_daemon.py`, `dashboard/dashboard_chat.py`; modificar/criar testes `test_chat_inbox.py`, `test_cognitive_chat_runtime.py`, `test_dashboard_chat_api.py`.

**Interfaces:** `ChatInbox.enqueue(message, client_message_id, *, channel="dashboard", actor_id=None, conversation_id=None, reply_target=None)`.

- [ ] Testar defaults retrocompatÃ­veis e metadata Discord persistida.
- [ ] Verificar RED pelo novo argumento ausente.
- [ ] Implementar schema tolerante a mensagens v1 antigas.
- [ ] Propagar `human.<channel>` e rota para `chat_message` de resposta.
- [ ] Verificar GREEN para dashboard e ciclo cognitivo.
- [ ] Commit: `feat(atlas): route cognitive chat by channel`.
### Task 4: Gateway Discord

**Files:** criar `atlas/config_discord.json`, `atlas/config_discord.py`, `atlas/discord_gateway.py`, `atlas/tests/test_discord_gateway.py`, `atlas/atlas-discord.service`.

**Interfaces:** `DiscordConfig`; `DiscordChatBridge.accept_message(...)`; `DiscordChatBridge.responses_after(event_id)`; `main()` carrega `ATLAS_DISCORD_BOT_TOKEN` e `discord.py` apenas no processo dedicado.

- [ ] Testar allowlist de guild/channel/user, idempotÃªncia e resposta somente para rota Discord.
- [ ] Verificar RED por mÃ³dulo inexistente.
- [ ] Implementar bridge independente de `discord.py` para testes.
- [ ] Implementar launcher `discord.py` com message-content intent, sem capabilities diretas.
- [ ] Verificar GREEN com fake inbox/event store.
- [ ] Commit: `feat(atlas): add discord conversation gateway`.

### Task 5: Packaging e gates

**Files:** modificar `atlas/install-user.sh`, `.github/workflows/foundation-ci.yml` e documentaÃ§Ã£o de operaÃ§Ã£o.

**Interfaces:** pacote instala mÃ³dulos/configs sem secret; unit Discord Ã© instalada mas nÃ£o habilitada automaticamente sem credencial.

- [ ] Adicionar teste de packaging para mÃ³dulos/configs e ausÃªncia de token literal.
- [ ] Verificar RED no contrato atual.
- [ ] Atualizar installer/CI com marker `DEVEX_HOMELAB_ATLAS_MULTISOURCE_CHAT_PASS`.
- [ ] Rodar suÃ­te Atlas + dashboard + `git diff --check` + JSON validation.
- [ ] Registrar HEAD exato e checkpoint somente apÃ³s GREEN.
- [ ] Commit: `ci(atlas): certify multisource github discord integration`.

## Self-review

Cobertura: topologia fÃ­sica, GitHub, chat multicanal, Discord, secrets, packaging e CI tÃªm tarefas explÃ­citas. Nenhum token Ã© versionado. Interfaces de Task 4 dependem da rota criada na Task 3; GitHub Ã© independente de Discord e compartilha apenas o ObservationRuntime.
