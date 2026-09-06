# Atlas I1 Observation Integration & Certification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrar `WIFI_OBSERVED` e `MANAGED` no unico `ObservationRuntime` e certificar isolamento, bounds e policy no HEAD vigente.

**Architecture:** `WifiPresenceSource` continua owner da observacao Wi-Fi. Uma nova `ManagedObservationSource` adapta `ManagedReadService` para `SourceSnapshot` estruturado, sem CONTROL no polling. Um composition root I1 monta ambas as zonas no `ObservationRuntime`; um certificador exercita sucesso e falha independente das duas zonas.

**Tech Stack:** Python stdlib, unittest, OpenSSH adapter existente, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-05-atlas-dual-zone-observation-design.md`

## Global Constraints
- Um unico `ObservationRuntime` e scheduler.
- `WIFI_OBSERVED` nunca promove entidade para MANAGED.
- READ MANAGED e tipado e bounded; CONTROL nunca roda em polling.
- Falha de uma zona nao bloqueia a outra.
- Falha SSH e evidencia do canal administrativo, nao prova de host offline.
- Nenhuma API publica aceita shell arbitrario.
- Certificacao fisica nao pode ser inventada por CI.

---
### Task 1: ManagedObservationSource

**Files:**
- Modify: `infrastructure/pentium/atlas/stimulus_sources.py`
- Test: `infrastructure/pentium/atlas/tests/test_i1_managed_observation_source.py`

**Interfaces:**
- Consumes: `ManagedReadService.read(host_id, operation)`.
- Produces: `ManagedObservationSource(name, host_id, read_service, operations).poll() -> SourceSnapshot`.

- [ ] RED: host MANAGED saudavel gera snapshot `zone=MANAGED` com reads tipados.
- [ ] RED: falha SSH em um READ produz snapshot `degraded` sem classificar host offline.
- [ ] RED: source nao expoe CONTROL nem shell.
- [ ] GREEN: implementar adaptador minimo e rerodar regressao Atlas.
- [ ] Commitar task.

### Task 2: Composition root dual-zone

**Files:**
- Create: `infrastructure/pentium/atlas/dual_zone_runtime.py`
- Test: `infrastructure/pentium/atlas/tests/test_i1_dual_zone_runtime.py`

**Interfaces:**
- Produces: `build_dual_zone_runtime(...) -> ObservationRuntime`.
- Fontes obrigatorias: `wifi.presence` e uma ou mais `managed.<host_id>`.

- [ ] RED: runtime contem as duas zonas e usa schedules do config existente.
- [ ] RED: falha/timeout MANAGED nao impede ciclo Wi-Fi e vice-versa.
- [ ] GREEN: montar fontes no mesmo `ObservationRuntime`, sem loop paralelo.
- [ ] Commitar task.
### Task 3: I1 certification harness

**Files:**
- Create: `infrastructure/pentium/atlas/i1_certification.py`
- Test: `infrastructure/pentium/atlas/tests/test_i1_certification.py`

**Interfaces:**
- Produces: `certify_dual_zone(runtime, ...) -> I1CertificationResult`.
- Certifica somente invariantes exercitadas; nao emite physical PASS em ambiente simulado.

- [ ] RED: cenarios healthy, falha Wi-Fi isolada, falha MANAGED isolada e default-deny CONTROL.
- [ ] RED: resultado exige evidencias de ambas as zonas no mesmo HEAD/runtime.
- [ ] GREEN: implementar resultado bounded e markers tecnicos sem falsificar certificacao fisica.
- [ ] Commitar task.

### Task 4: Packaging, docs e CI

**Files:**
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`
- Modify: `docs/architecture/atlas-local-intelligence-design.md`
- Modify: `docs/prd/PRD-0006-atlas-local-intelligence.md`
- Test: `infrastructure/pentium/atlas/tests/test_i1_observation_integration_packaging.py`

- [ ] RED: installer/CI/docs ainda nao possuem I1.
- [ ] GREEN: empacotar modulos, compilar, executar testes e emitir `DEVEX_HOMELAB_ATLAS_I1_OBSERVATION_INTEGRATION_PASS`.
- [ ] Rodar Agent + Atlas completos, py_compile, JSON, bash -n, diff-check e ancestry.
- [ ] Push, PR Draft empilhada sobre M2, Foundation CI no HEAD exato e `/checkpoint` somente apos GREEN.
