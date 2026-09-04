# Atlas Observation Runtime 24/7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o sistema nervoso 24/7 do Atlas no Pentium: observar fontes administradas, transformar mudanças em `Stimulus` normalizado, filtrar ruído, preservar critical sob pressão e publicar/journalizar eventos para consumidores futuros.

**Architecture:** `StimulusSource -> ObservationRuntime -> StimulusBus -> StimulusJournal`. O runtime calcula fingerprints/novelty de forma determinística, mantém estado por fonte, aplica timeout/backoff e nunca envia polling bruto para LLM. Consumidores futuros recebem apenas estímulos normalizados.

**Tech Stack:** Python 3.14+, stdlib, `unittest`, JSONL, GitHub Actions.

**Spec:** `docs/implementation/2026-09-03-atlas-observation-runtime-design.md`

## Global Constraints

- host autoritativo: `pentium`; observação contínua 24h/7d;
- sem LLM, áudio, STT, TTS, CONTROL/DESTRUCTIVE actions ou shell arbitrário;
- bus in-process e bounded; `critical` não pode ser descartado enquanto houver item não crítico removível;
- nenhuma alteração de rede, SSH, Tailscale, MikroTik ou systemd nesta implementação;
- payloads reduzidos, serializáveis e sem logs brutos/secrets;
- CI usa fontes fake e relógio injetável; certificação física é READ-only.

## File map

Create: `stimulus_model.py`, `stimulus_bus.py`, `stimulus_journal.py`, `stimulus_sources.py`, `observation_runtime.py` e testes dedicados. Modify: `install-user.sh` e `.github/workflows/foundation-ci.yml`. As-built só muda depois de evidência física.
---

### Task 1: Canonical `Stimulus` model and deterministic fingerprint

**Files:** Create `infrastructure/pentium/atlas/stimulus_model.py`, `infrastructure/pentium/atlas/tests/test_stimulus_model.py`.

**Interfaces:** Produces `StimulusSeverity`, frozen `Stimulus`, `stable_fingerprint(payload: Mapping[str, Any]) -> str`, `compute_novelty(previous_seen_count: int) -> float`.

- [ ] **Step 1: Write failing tests** for frozen dataclass, JSON-safe fields, severity enum, order-independent fingerprint and deterministic novelty (`0 -> 1.0`, repeated observations decay toward a floor).
- [ ] **Step 2: Run RED:** `python3 -m unittest infrastructure.pentium.atlas.tests.test_stimulus_model -v`; expected module import failure.
- [ ] **Step 3: Implement minimal model** using canonical `json.dumps(..., sort_keys=True, separators=(",", ":"))` + SHA-256; clamp novelty to `0.1..1.0` without LLM/input randomness.
- [ ] **Step 4: Run GREEN** with the same command; expected PASS.
- [ ] **Step 5: Commit:** `git add infrastructure/pentium/atlas/stimulus_model.py infrastructure/pentium/atlas/tests/test_stimulus_model.py && git commit -m "feat(atlas): define stimulus contract"`.

### Task 2: Bounded `StimulusBus` with critical preservation

**Files:** Create `infrastructure/pentium/atlas/stimulus_bus.py`, `infrastructure/pentium/atlas/tests/test_stimulus_bus.py`.

**Interfaces:** `StimulusBus(capacity: int)`, `publish(stimulus) -> PublishResult`, `poll() -> Stimulus | None`, `metrics() -> BusMetrics`.
- [ ] **Step 1: Write failing tests** proving FIFO under capacity, deterministic overflow, noncritical eviction before critical, explicit drop when queue is all-critical, and counters `published/dropped/critical_preserved`.
- [ ] **Step 2: Run RED:** `python3 -m unittest infrastructure.pentium.atlas.tests.test_stimulus_bus -v`; expected import failure.
- [ ] **Step 3: Implement minimal bounded queue** with `collections.deque`; on overflow remove the oldest noncritical item when incoming is critical, otherwise drop oldest item by deterministic policy.
- [ ] **Step 4: Run GREEN** and full Atlas tests.
- [ ] **Step 5: Commit:** `git add infrastructure/pentium/atlas/stimulus_bus.py infrastructure/pentium/atlas/tests/test_stimulus_bus.py && git commit -m "feat(atlas): add bounded stimulus bus"`.

### Task 3: Append-only `StimulusJournal`

**Files:** Create `infrastructure/pentium/atlas/stimulus_journal.py`, `infrastructure/pentium/atlas/tests/test_stimulus_journal.py`.

**Interfaces:** `append_stimulus(path: Path, stimulus: Stimulus, runtime_meta: Mapping[str, Any]) -> None`; raises `StimulusJournalError` on write failure.

- [ ] **Step 1: Write failing tests** for independent JSONL records, full canonical stimulus fields, runtime metadata and wrapped write failure.
- [ ] **Step 2: Run RED:** `python3 -m unittest infrastructure.pentium.atlas.tests.test_stimulus_journal -v`.
- [ ] **Step 3: Implement append-only writer** with UTF-8, one JSON object per line, `ensure_ascii=False`, `sort_keys=True`, explicit flush and no mutation of bus/state on error.
- [ ] **Step 4: Run GREEN** and full Atlas tests.
- [ ] **Step 5: Commit:** `git add infrastructure/pentium/atlas/stimulus_journal.py infrastructure/pentium/atlas/tests/test_stimulus_journal.py && git commit -m "feat(atlas): journal normalized stimuli"`.

### Task 4: `StimulusSource` contracts and initial adapters

**Files:** Create `infrastructure/pentium/atlas/stimulus_sources.py`, `infrastructure/pentium/atlas/tests/test_stimulus_sources.py`.

**Interfaces:** Protocol `StimulusSource.name`, `poll() -> SourceSnapshot`; adapters `PentiumSelfSource`, `CoreHealthSource`, `X99StatusSource` use existing versioned contracts via injected callables, never arbitrary shell.
- [ ] **Step 1: Write failing tests** with fake callables for healthy/degraded Pentium, Core and x99 snapshots; assert payload reduction and no raw command/log leakage.
- [ ] **Step 2: Run RED:** `python3 -m unittest infrastructure.pentium.atlas.tests.test_stimulus_sources -v`.
- [ ] **Step 3: Implement source adapters** that return frozen `SourceSnapshot(source, status, severity, payload)` and translate only stable fields from existing heartbeat/network/agent contracts.
- [ ] **Step 4: Run GREEN** and full Atlas tests.
- [ ] **Step 5: Commit:** `git add infrastructure/pentium/atlas/stimulus_sources.py infrastructure/pentium/atlas/tests/test_stimulus_sources.py && git commit -m "feat(atlas): add managed stimulus sources"`.

### Task 5: ObservationRuntime change detection, recovery and novelty

**Files:** Create `infrastructure/pentium/atlas/observation_runtime.py`, `infrastructure/pentium/atlas/tests/test_observation_runtime.py`.

**Interfaces:** `ObservationRuntime(sources, bus, journal, clock, sleeper, config)`; `run_once(source_name) -> Stimulus | None`; per-source state stores fingerprint, failure state, seen fingerprint counts and backoff.

- [ ] **Step 1: Write failing tests** for one-time `baseline_observed`, unchanged snapshot suppression, changed snapshot emission, repeated identical failure cooldown, explicit `recovered`, novelty decay, and correlation continuity across failure/recovery.
- [ ] **Step 2: Run RED:** `python3 -m unittest infrastructure.pentium.atlas.tests.test_observation_runtime -v`.
- [ ] **Step 3: Implement minimal state machine**: stable fingerprint -> change classification -> `Stimulus` -> journal -> bus; journal failure is recorded as runtime error but does not corrupt source state or bus.
- [ ] **Step 4: Run GREEN** and full Atlas tests.
- [ ] **Step 5: Commit:** `git add infrastructure/pentium/atlas/observation_runtime.py infrastructure/pentium/atlas/tests/test_observation_runtime.py && git commit -m "feat(atlas): observe and normalize state changes"`.

### Task 6: Cooperative 24/7 scheduling, timeout, backoff and shutdown

**Files:** Modify `observation_runtime.py`; extend `tests/test_observation_runtime.py`; create `infrastructure/pentium/atlas/observation_config.json`.

**Interfaces:** `run_forever(stop_event) -> None`; per-source config `interval_seconds`, `timeout_seconds`, `max_backoff_seconds`, optional `jitter_seconds`; no busy loop.
- [ ] **Step 1: Write failing scheduling tests** using injected fake clock/sleeper and source futures: due sources poll, non-due sources do not, one source timeout/failure does not block another, backoff is capped, stop event exits cleanly.
- [ ] **Step 2: Run RED** focused runtime tests.
- [ ] **Step 3: Implement cooperative scheduler** with monotonic injected clock, per-source next-due timestamps and bounded timeout execution; jitter disabled by default in tests.
- [ ] **Step 4: Validate config JSON** and run full Atlas suite; expected no real sleep/network in tests.
- [ ] **Step 5: Commit:** `git add infrastructure/pentium/atlas/observation_runtime.py infrastructure/pentium/atlas/observation_config.json infrastructure/pentium/atlas/tests/test_observation_runtime.py && git commit -m "feat(atlas): add continuous observation scheduler"`.

### Task 7: Install packaging and Foundation CI gate

**Files:** Modify `infrastructure/pentium/atlas/install-user.sh`, `.github/workflows/foundation-ci.yml`; add installer contract test if repository pattern allows shell inspection from unittest.

**Interfaces:** User-level install copies observation modules/config only; it does not enable/start a persistent service. CI marker: `DEVEX_HOMELAB_ATLAS_OBSERVATION_PASS`.

- [ ] **Step 1: Write failing installer/CI contract assertions** that expected modules/config are referenced and no `systemctl enable/start`, network modification or LLM dependency is introduced.
- [ ] **Step 2: Run RED** against current installer/workflow; expected missing Observation Runtime artifacts/gate.
- [ ] **Step 3: Extend installer** to copy `stimulus_model.py`, `stimulus_bus.py`, `stimulus_journal.py`, `stimulus_sources.py`, `observation_runtime.py`, `observation_config.json`; add `py_compile` and `json.tool` validation only.
- [ ] **Step 4: Extend Foundation CI** to compile observation modules, validate config and run all Atlas tests with fake sources; emit exact marker.
- [ ] **Step 5: Run full local gate:** Network 6 + Heartbeat 7 + Pentium Agent 10 + entire Atlas suite + `bash -n` + `git diff --check`.
- [ ] **Step 6: Commit:** `git add infrastructure/pentium/atlas/install-user.sh .github/workflows/foundation-ci.yml infrastructure/pentium/atlas/tests && git commit -m "ci(atlas): validate observation runtime"`.

### Task 8: Exact-HEAD CI, READ-only physical certification and checkpoint

**Files:** Update `docs/as-built/2026-09-02-baseline.md` and design evidence section only after observed proof.

**Interfaces:** Produces exact-head CI evidence and READ-only Pentium/Core/x99 observation evidence; no persistent service deployment in this slice.
- [ ] **Step 1: Push branch/update Draft PR only after local full gate passes**; record exact HEAD SHA.
- [ ] **Step 2: Require Foundation CI GREEN on that exact SHA** before any physical probe.
- [ ] **Step 3: Build a deterministic user-level package** from the exact HEAD and compute SHA-256 before transfer.
- [ ] **Step 4: On Pentium, perform READ-only prerequisite inspection** and install only under `~/pentium-agent/atlas`; do not enable/start systemd or alter network/SSH/Tailscale.
- [ ] **Step 5: Run bounded physical observation smoke** for `pentium.self`, `core` and `x99`; capture baseline stimuli, repeat unchanged probes to prove suppression, and where safely reproducible use fake/injected fixture for recovery rather than disrupting real equipment.
- [ ] **Step 6: Verify JSONL journal and bus metrics** match emitted/deduplicated events and contain no raw secrets/logs.
- [ ] **Step 7: Update as-built/design with observed evidence only**, commit documentation, push and require a fresh Foundation CI GREEN for the new final HEAD.
- [ ] **Step 8: Create/update `/checkpoint`** in pt-BR with final HEAD, implementation summary, exact test counts, CI run, READ-only physical evidence, blockers and next safe slice: Affective State Engine.

## Definition of Done

- `Stimulus`, fingerprint and novelty are deterministic and tested.
- `StimulusBus` is bounded and preserves critical over removable noncritical items.
- initial Pentium/Core/x99 source adapters expose only reduced stable payloads.
- ObservationRuntime deduplicates unchanged state, emits recovery, isolates source failure and uses bounded backoff/shutdown.
- journal is append-only JSONL and does not control technical state.
- no LLM, audio, TTS/STT, arbitrary action, systemd persistence or network mutation is introduced.
- all pre-existing tests remain GREEN; new Atlas tests are GREEN; exact final HEAD has Foundation CI GREEN.
- physical certification is READ-only and as-built/checkpoint contain only observed evidence.

## Plan self-review

- Spec coverage: model, fingerprint, novelty, initial sources, dedup, recovery, bus pressure, journal, scheduling, timeout/backoff, isolation, shutdown, CI and physical READ-only certification each map to an explicit task.
- Interface continuity: Task 1 types feed Tasks 2-5; Task 4 snapshots feed Task 5; Task 5 state machine is scheduled by Task 6; Tasks 7-8 package and certify the same contracts.
- Scope check: Affective Engine, LLM Reaction Loop, Audio Engine, Voice, MikroTik/DNS/Internet adapters and persistent systemd deployment remain outside this plan.
- No placeholder or ambiguous implementation step is intentionally left open.