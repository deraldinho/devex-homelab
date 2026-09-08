# Atlas Affective Runtime Boot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Executar continuamente no Pentium o pipeline observacional afetivo com restauração A1/A2/A3/A4, single-writer visual e interação efêmera da voz via IPC local bounded.

**Architecture:** `atlas-observation.service` possui o único processo que aplica impulsos e persiste A1/A2/A3/A4. `atlas-voice.service` permanece separado e envia somente flags efêmeras por Unix datagram; `AffectiveRuntime` no processo observacional continua único writer de `visual-state.json`.

**Tech Stack:** Python stdlib, `dataclasses`, Unix datagram sockets, JSON atômico, `unittest`, systemd user services, Foundation CI.

**Spec:** `docs/superpowers/specs/2026-09-08-atlas-affective-runtime-boot-design.md`

## Global Constraints
- Base funcional: `07a082c768a9f61033a7090a485f8fd24fdc1f54`.
- `atlas-observation.service` é o único owner de A1/A2/A3/A4 mutáveis.
- Voice/LLM nunca aplica `ImpulsoAfetivo`.
- `visual-state.json` tem single-writer no processo observacional.
- `wifi.presence` não entra no pipeline afetivo sem mapping explícito.
- `managed.x99` deve ser roteado explicitamente para a entidade/fonte afetiva `x99`.
- IPC não carrega áudio, transcript, comandos ou payload arbitrário.
- Nenhuma fila/cache/socket aceita crescimento ilimitado.
- CONTROL permanece fora do polling e default-deny.
- Nenhuma dependência operacional do x99 após deploy.

---
### Task 1: Restauração A3 e composition factory

**Files:**
- Modify: `infrastructure/pentium/atlas/correlacionador_incidentes.py`
- Modify: `infrastructure/pentium/atlas/pipeline_percepcao_correlacao.py`
- Create: `infrastructure/pentium/atlas/affective_composition.py`
- Test: `infrastructure/pentium/atlas/tests/test_affective_composition.py`

**Interfaces:**
- Produces: `restaurar(percepcoes, incidentes)` em A3, sem replay de estímulos.
- Produces: `build_affective_composition(...) -> AffectiveComposition`.
- `AffectiveComposition.processar(stimulus)` roteia allowlist, persiste A3→A2→A1→A4 e atualiza health bounded.

- [ ] Escrever testes falhos para restauração A3, mapping `managed.x99 -> x99`, ignore de `wifi.presence`, restauração A1/A2/A4 e persistência pós-evento.
- [ ] Rodar testes e confirmar RED pelas APIs ausentes.
- [ ] Implementar APIs mínimas de restauração e factory.
- [ ] Rodar testes focados + regressão A1/A2/A3/A4.
- [ ] Commitar `feat(atlas): montar composition afetiva persistente`.

### Task 2: IPC efêmero single-writer

**Files:**
- Create: `infrastructure/pentium/atlas/affective_interaction_ipc.py`
- Modify: `infrastructure/pentium/atlas/voice_daemon.py`
- Test: `infrastructure/pentium/atlas/tests/test_affective_interaction_ipc.py`
- Test: `infrastructure/pentium/atlas/tests/test_voice_daemon_visual_ipc.py`

**Interfaces:**
- Produces: `InteractionDatagramClient.send(EstadoInteracaoVisual) -> bool` fail-safe.
- Produces: `InteractionDatagramListener.run_once(timeout_s) -> bool`.
- Voice passa o client como `visual_state_sink`; listener é o único lado que chama `AffectiveRuntime.atualizar_interacao`.

- [ ] RED para schema/tamanho/socket stale, mensagens inválidas e indisponibilidade fail-safe.
- [ ] RED para `voice_daemon.build_runtime()` usar sink IPC sem writer visual próprio.
- [ ] Implementar client/listener Unix datagram bounded.
- [ ] Rodar IPC + voice regressão e commit.
### Task 3: Daemon observacional always-on

**Files:**
- Create: `infrastructure/pentium/atlas/observation_daemon.py`
- Modify: `infrastructure/pentium/atlas/dual_zone_runtime.py`
- Test: `infrastructure/pentium/atlas/tests/test_observation_daemon.py`
- Test: `infrastructure/pentium/atlas/tests/test_i1_dual_zone_runtime.py`

**Interfaces:**
- `build_dual_zone_runtime(..., accepted_stimulus_sink=None)` encaminha o sink ao único `ObservationRuntime`.
- `observation_daemon.build_runtime()` monta inventory/read service, Wi-Fi, bus/journal, schedules, composition e IPC listener.
- `main()` mantém scheduler + listener bounded, health atômico e shutdown SIGTERM/SIGINT.

- [ ] RED para sink no dual-zone, config real, health schema, shutdown e ausência de segundo ObservationRuntime.
- [ ] Implementar montagem mínima e health/readiness atômico.
- [ ] Rodar daemon/I1 regressão e commit.

### Task 4: Systemd, packaging e CI

**Files:**
- Create: `infrastructure/pentium/atlas/atlas-observation.service`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`
- Test: `infrastructure/pentium/atlas/tests/test_affective_boot_packaging.py`

- [ ] RED para módulos/unit/config/gate ausentes.
- [ ] Instalar/compilar observation daemon, composition e IPC; instalar/habilitar os dois user services.
- [ ] Validar unit files e emitir `DEVEX_HOMELAB_ATLAS_AFFECTIVE_BOOT_PASS`.
- [ ] Rodar packaging tests e commit.

### Task 5: Certificação local e física

**Files:**
- Create: `infrastructure/pentium/atlas/affective_boot_certification.py`
- Test: `infrastructure/pentium/atlas/tests/test_affective_boot_certification.py`

- [ ] RED para certificador que exige SHA, health, serviços, visual, IPC e restauração.
- [ ] Implementar coleta sem fabricar PASS físico.
- [ ] Rodar Atlas completo + dashboard + py_compile + JSON + bash -n + diff-check + UTF-8.
- [ ] Deploy no Pentium, restart, smoke, restart de restauração e certificação no SHA exato.
- [ ] Somente após evidência física emitir marcador `ATLAS_AFFECTIVE_BOOT_PHYSICAL_PASS` e checkpoint da PR.
