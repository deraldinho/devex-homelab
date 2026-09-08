# Atlas Affective Runtime Boot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Colocar o pipeline observacional afetivo em operação contínua no Pentium com restauração/persistência A1-A4, IPC efêmero de voz e certificação física no SHA exato.

**Architecture:** `atlas-observation.service` mantém o único `ObservationRuntime` e o único writer afetivo/visual. `affective_composition.py` monta/restaura A1/A2/A3/A4 e persiste após cada evento; `voice_daemon` envia somente flags efêmeras por Unix datagram para o processo observacional.

**Tech Stack:** Python stdlib, dataclasses, Unix datagram sockets, systemd user services, unittest, JSON versionado, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-08-atlas-affective-runtime-boot-design.md`

## Global Constraints
- Base funcional: `07a082c768a9f61033a7090a485f8fd24fdc1f54`.
- `atlas-observation.service` é o único processo que aplica `ImpulsoAfetivo` e persiste A1/A2/A3/A4.
- `atlas-voice.service` não altera A1/A2/A3/A4 e não escreve `visual-state.json` diretamente.
- Não criar segundo `ObservationRuntime`, segundo scheduler ou supervisor global.
- `wifi.presence` não entra no afeto sem mapping explícito; `managed.x99` mapeia explicitamente para `x99`.
- IPC local aceita somente schema bounded de flags efêmeras, sem áudio/transcript/comandos.
- Nenhum PASS físico pode ser inferido de CI ou simulação local.
- Nenhuma dependência operacional do x99; nenhuma mudança em L2jToren.

---
### Task 1: Restauracao A3 explicita e bounded

**Files:**
- Modify: `infrastructure/pentium/atlas/pipeline_percepcao_correlacao.py`
- Modify: `infrastructure/pentium/atlas/correlacionador_incidentes.py`
- Test: `infrastructure/pentium/atlas/tests/test_pipeline_percepcao_restauracao.py`

**Interfaces:**
- Produces: `PipelinePercepcaoCorrelacao.restaurar_estado(percepcoes, incidentes) -> None`.
- Produces: `CorrelacionadorIncidentes.restaurar_incidentes(incidentes) -> None`.
- Restauracao não adiciona stimulus IDs e não chama A1/A4.

- [ ] Escrever testes que restauram percepção/incidente válido, rejeitam entidade incompatível, respeitam capacities e não tratam estado restaurado como novo estímulo.
- [ ] Rodar somente os novos testes e observar RED por ausência das APIs.
- [ ] Implementar restauração mínima validando entidades configuradas, unicidade e limites atuais.
- [ ] Rodar novos testes + regressão de percepção/correlação e obter GREEN.
- [ ] Commit: `feat(atlas): restaurar estado de percepcao correlacionada`.

### Task 2: Composition factory afetivo e persistencia pos-evento

**Files:**
- Create: `infrastructure/pentium/atlas/affective_composition.py`
- Test: `infrastructure/pentium/atlas/tests/test_affective_composition.py`

**Interfaces:**
- Produces: `build_affective_composition(paths, now, incident_id_factory) -> AffectiveComposition`.
- `AffectiveComposition.processar(stimulus) -> ResultadoPipelineAfetivoObservacional | None` filtra fontes sem mapping.
- `AffectiveComposition.persistir() -> tuple[str, ...]` persiste A3 -> A2 -> A1 -> A4 e retorna diagnósticos bounded.

- [ ] Testar RED para restore A1/A2/A3/A4, `managed.x99 -> x99`, ignore de `wifi.presence`, persistência após evento e corrupção fail-safe.
- [ ] Implementar factory usando os loaders/repositórios existentes e o novo restore A3.
- [ ] Garantir que `managed.x99` seja normalizado sem promover falha SSH isolada a host offline.
- [ ] Rodar testes da composition + pipeline observacional afetivo e obter GREEN.
- [ ] Commit: `feat(atlas): montar composicao afetiva persistente`.
### Task 3: IPC efemero de interacao da voz

**Files:**
- Create: `infrastructure/pentium/atlas/affective_interaction_ipc.py`
- Modify: `infrastructure/pentium/atlas/voice_daemon.py`
- Test: `infrastructure/pentium/atlas/tests/test_affective_interaction_ipc.py`
- Test: `infrastructure/pentium/atlas/tests/test_voice_daemon_affective_ipc.py`

**Interfaces:**
- Produces: `AffectiveInteractionServer(path, runtime_visual, ...)` com `serve_once(timeout_s)` e `close()`.
- Produces: `AffectiveInteractionClient(path, max_bytes=...)` com `publish(**flags) -> bool` fail-safe.
- Payload schema 1: somente `ouvindo`, `pensando`, `falando`, `duvida_identidade`, `timestamp`.

- [ ] Escrever RED para datagrama válido, schema/tamanho inválido, socket stale-safe, cleanup e indisponibilidade fail-safe no client.
- [ ] Implementar server/client Unix datagram bounded sem fila ilimitada.
- [ ] Escrever RED provando que `voice_daemon` publica transições efêmeras mas continua funcionando com socket ausente.
- [ ] Integrar o client ao runtime de voz sem permitir acesso a `ImpulsoAfetivo` ou persistência.
- [ ] Rodar testes IPC + voz e obter GREEN.
- [ ] Commit: `feat(atlas): integrar interacao efemera da voz`.

### Task 4: Daemon observacional always-on e wiring do dual-zone

**Files:**
- Modify: `infrastructure/pentium/atlas/dual_zone_runtime.py`
- Create: `infrastructure/pentium/atlas/observation_daemon.py`
- Test: `infrastructure/pentium/atlas/tests/test_i1_dual_zone_runtime.py`
- Test: `infrastructure/pentium/atlas/tests/test_observation_daemon.py`

**Interfaces:**
- `build_dual_zone_runtime(..., accepted_stimulus_sink=None)` encaminha o callback para o único `ObservationRuntime`.
- `build_observation_daemon(...) -> ObservationDaemon` monta composition, dual-zone e IPC server.
- Health JSON schema 1 registra readiness, SHA esperado, último ciclo, restaurações e diagnósticos bounded.

- [ ] Escrever RED para callback no dual-zone, single runtime/scheduler, shutdown limpo e health versionado.
- [ ] Implementar callback opcional preservando compatibilidade I1.
- [ ] Implementar daemon com SIGTERM/SIGINT, listener IPC com timeout bounded e scheduler existente.
- [ ] Testar que erro afetivo/IPC não invalida journal/coleta e que `wifi.presence` sem mapping não derruba o daemon.
- [ ] Rodar testes de observation runtime/I1/daemon e obter GREEN.
- [ ] Commit: `feat(atlas): executar runtime afetivo observacional always-on`.
### Task 5: Systemd, installer, CI e certificacao local

**Files:**
- Create: `infrastructure/pentium/atlas/atlas-observation.service`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`
- Test: `infrastructure/pentium/atlas/tests/test_affective_boot_packaging.py`

**Interfaces:**
- User service: `python3 -m atlas.observation_daemon` em `%h/pentium-agent`.
- Gate CI: `DEVEX_HOMELAB_ATLAS_AFFECTIVE_BOOT_PASS`.
- Installer marker: `ATLAS_AFFECTIVE_BOOT_INSTALL_PASS`.

- [ ] Escrever RED exigindo novos módulos/configs/unit file no installer e gate dedicado no Foundation CI.
- [ ] Implementar unit file, instalação/compilação/config parsing e enable/restart seguro sem tornar x99 dependência.
- [ ] Rodar `python -m unittest discover` Atlas e dashboard, `py_compile`, JSON, Git Bash `bash -n`, `git diff --check` e guard UTF-8.
- [ ] Commit: `ci(atlas): certificar boot do runtime afetivo`.

### Task 6: Deploy e certificacao fisica Pentium

**Files:**
- Evidence only; não alterar código para fazer o teste passar no host.

**Interfaces:**
- Expected SHA = HEAD final da branch após Task 5.
- Evidência física deve incluir serviço, health, visual, persistência/restart e IPC efêmero.

- [ ] Publicar/transferir o HEAD exato para o Pentium pelo fluxo de deploy já autorizado do homelab.
- [ ] Executar installer e confirmar `ATLAS_AFFECTIVE_BOOT_INSTALL_PASS` no SHA exato.
- [ ] Verificar `atlas-observation.service` active, PID estável e health schema 1 sem fatal.
- [ ] Confirmar evento real do próprio Pentium/infra entra no único ObservationRuntime e atualiza `visual-state.json`.
- [ ] Enviar um payload IPC efêmero válido e confirmar alteração visual sem mutação de A1 persistido.
- [ ] Reiniciar observation service e confirmar restauração A1/A2/A3/A4 e continuidade visual.
- [ ] Verificar que ausência/desligamento do x99 não impede boot/operação do Pentium.
- [ ] Registrar evidência física com HEAD exato; só então afirmar always-on operacional.

### Final verification
- [ ] `git status --short --branch` limpo.
- [ ] `git diff --check 07a082c768a9f61033a7090a485f8fd24fdc1f54...HEAD` limpo.
- [ ] Suite Atlas e dashboard GREEN no HEAD exato.
- [ ] CI/checks do HEAD exato GREEN quando disponíveis.
- [ ] Certificação física pertence ao mesmo HEAD exato.
- [ ] Preparar checkpoint `/checkpoint` da PR com implementação, evidências, gates e próximos passos.
