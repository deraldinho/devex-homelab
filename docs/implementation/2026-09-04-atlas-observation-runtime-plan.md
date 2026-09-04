# Atlas Observation Runtime 24/7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Implementar o sistema nervoso 24/7 do Atlas no Pentium: observar fontes administradas, transformar mudanÃƒÂ§as em `Stimulus` normalizado, filtrar ruÃƒÂ­do, preservar critical sob pressÃƒÂ£o e publicar/journalizar eventos para consumidores futuros.

**Architecture:** `StimulusSource -> ObservationRuntime -> StimulusBus -> StimulusJournal`. O runtime calcula fingerprints/novelty de forma determinÃƒÂ­stica, mantÃƒÂ©m estado por fonte, aplica timeout/backoff e nunca envia polling bruto para LLM. Consumidores futuros recebem apenas estÃƒÂ­mulos normalizados.

**Tech Stack:** Python 3.14+, stdlib, `unittest`, JSONL, GitHub Actions.

**Spec:** `docs/implementation/2026-09-03-atlas-observation-runtime-design.md`

## Global Constraints

- host autoritativo: `pentium`; observaÃƒÂ§ÃƒÂ£o contÃƒÂ­nua 24h/7d;
- sem LLM, ÃƒÂ¡udio, STT, TTS, CONTROL/DESTRUCTIVE actions ou shell arbitrÃƒÂ¡rio;
- bus in-process e bounded; `critical` nÃƒÂ£o pode ser descartado enquanto houver item nÃƒÂ£o crÃƒÂ­tico removÃƒÂ­vel;
- nenhuma alteraÃƒÂ§ÃƒÂ£o de rede, SSH, Tailscale, MikroTik ou systemd nesta implementaÃƒÂ§ÃƒÂ£o;
- payloads reduzidos, serializÃƒÂ¡veis e sem logs brutos/secrets;
- CI usa fontes fake e relÃƒÂ³gio injetÃƒÂ¡vel; certificaÃƒÂ§ÃƒÂ£o fÃƒÂ­sica ÃƒÂ© READ-only.

## File map

Create: `stimulus_model.py`, `stimulus_bus.py`, `stimulus_journal.py`, `stimulus_sources.py`, `observation_runtime.py` e testes dedicados. Modify: `install-user.sh` e `.github/workflows/foundation-ci.yml`. As-built sÃƒÂ³ muda depois de evidÃƒÂªncia fÃƒÂ­sica.
---

### Task 1: Canonical Stimulus model, fingerprint and novelty

**Files:** Create `infrastructure/pentium/atlas/stimulus_model.py`; create `tests/test_stimulus_model.py`.

**Interfaces:** `StimulusSeverity`, frozen `Stimulus`; `stable_fingerprint(payload) -> str`; `novelty_score(previous_fingerprint, current_fingerprint, repeat_count) -> float`; `compute_novelty(seen_count)` permanece como compatibilidade interna.

- [x] **Step 1: Write failing tests** for frozen dataclass, JSON serialization, deterministic fingerprint independent of dict key order, novelty `1.0` for first/new fingerprint and lower bounded novelty for repeats.
- [x] **Step 2: Run RED:** `python3 -m unittest infrastructure.pentium.atlas.tests.test_stimulus_model -v`; expected import failure.
- [x] **Step 3: Implement minimal model** using stdlib `dataclasses`, canonical JSON and SHA-256; clamp novelty to `0.0..1.0`.
- [x] **Step 4: Run GREEN** with the same command; expected PASS.
- [x] **Step 5: Commit:** `git add infrastructure/pentium/atlas/stimulus_model.py infrastructure/pentium/atlas/tests/test_stimulus_model.py && git commit -m "feat(atlas): define canonical stimulus model"`.

### Task 2: Bounded StimulusBus with critical preservation

**Files:** Create `stimulus_bus.py`; create `tests/test_stimulus_bus.py`.

**Interfaces:** `StimulusBus(capacity: int)`, `publish(stimulus) -> PublishResult`, `poll() -> Stimulus | None`, `metrics() -> BusMetrics`.

- [x] **Step 1: Write failing tests** for FIFO under capacity, bounded overflow, oldest non-critical eviction, critical preservation and counters `published`, `dropped`, `critical_preserved`.
- [x] **Step 2: Run RED:** `python3 -m unittest infrastructure.pentium.atlas.tests.test_stimulus_bus -v`; expected import failure.
- [x] **Step 3: Implement deterministic queue policy** with `collections.deque`; when full and publishing critical, evict the oldest non-critical if one exists; never exceed capacity.
- [x] **Step 4: Run GREEN** and then Task 1+2 tests together.
- [x] **Step 5: Commit:** `git add infrastructure/pentium/atlas/stimulus_bus.py infrastructure/pentium/atlas/tests/test_stimulus_bus.py && git commit -m "feat(atlas): add bounded stimulus bus"`.
### Task 3: StimulusJournal JSONL

**Files:** Create `stimulus_journal.py`; create `tests/test_stimulus_journal.py`.

**Interfaces:** `append_stimulus(path: Path, stimulus: Stimulus, runtime_meta: dict[str, object]) -> None`; `StimulusJournalError`.

- [x] **Step 1: Write failing tests** proving one JSON object per line, stable required fields and write-error wrapping.
- [x] **Step 2: Run RED:** `python3 -m unittest infrastructure.pentium.atlas.tests.test_stimulus_journal -v`; expected import failure.
- [x] **Step 3: Implement append-only JSONL** with UTF-8, newline, flush and explicit `StimulusJournalError` on `OSError`.
- [x] **Step 4: Run GREEN** and full Atlas tests.
- [x] **Step 5: Commit:** `git add infrastructure/pentium/atlas/stimulus_journal.py infrastructure/pentium/atlas/tests/test_stimulus_journal.py && git commit -m "feat(atlas): journal normalized stimuli"`.

### Task 4: StimulusSource contract and existing read-only adapters

**Files:** Create `stimulus_sources.py`; create `tests/test_stimulus_sources.py`.

**Interfaces:** protocol `StimulusSource.name`/`required`, `poll() -> SourceSnapshot`; frozen `SourceSnapshot(source, status, severity, payload, observed_at=None)`; adapters para `pentium.self`, `core`, `x99` reutilizam collectors existentes.

- [x] **Step 1: Write failing tests** with injected fake collectors proving payload reduction, stable source names, no raw stdout/log retention and no command construction inside adapters.
- [x] **Step 2: Run RED:** `python3 -m unittest infrastructure.pentium.atlas.tests.test_stimulus_sources -v`; expected import failure.
- [x] **Step 3: Implement callable-based adapters** that normalize existing summaries into small payloads such as `status`, selected checks and bounded metrics; no network/config mutation.
- [x] **Step 4: Run GREEN** and all Atlas tests.
- [x] **Step 5: Commit:** `git add infrastructure/pentium/atlas/stimulus_sources.py infrastructure/pentium/atlas/tests/test_stimulus_sources.py && git commit -m "feat(atlas): add read only stimulus sources"`.
### Task 5: ObservationRuntime change detection, recovery and backoff

**Files:** Create `observation_runtime.py`; create `tests/test_observation_runtime.py`.

**Interfaces:** `SourcePolicy(interval_s, timeout_s, max_backoff_s, cooldown_s)` Ã© o contrato canÃ´nico; `SourceSchedule` permanece compatÃ­vel para callers anteriores. `ObservationRuntime` aceita `policies=` ou `schedule=`, nunca ambos.

- [x] **Step 1: Write failing tests** for first `baseline_observed`, unchanged fingerprint suppression, changed snapshot publication, repeated failure cooldown, explicit `recovered`, per-source backoff, failure isolation and clean stop.
- [x] **Step 2: Run RED:** `python3 -m unittest infrastructure.pentium.atlas.tests.test_observation_runtime -v`; expected import failure.
- [x] **Step 3: Implement per-source state machine** storing last fingerprint/status, repeat count, failure count and next due time. Severity mapping is deterministic: healthy baseline=`info`, ordinary change=`notice`, degraded/error=`warning`, required/unavailable critical snapshot=`critical`, recovery=`notice`.
- [x] **Step 4: Implement cooperative scheduler** with injected monotonic clock/sleeper, bounded exponential backoff and no busy-loop. One source exception becomes a normalized failure observation and cannot prevent other due sources from polling.
- [x] **Step 5: Run GREEN**, then full Atlas suite.
- [x] **Step 6: Commit:** `git add infrastructure/pentium/atlas/observation_runtime.py infrastructure/pentium/atlas/tests/test_observation_runtime.py && git commit -m "feat(atlas): add continuous observation runtime"`.

### Task 6: Installation contract and CI gate

**Files:** Modify `infrastructure/pentium/atlas/install-user.sh`; modify `.github/workflows/foundation-ci.yml`; extend/add installer test as appropriate.

**Interfaces:** user-level install copies observation modules; CI validates them without running a permanent process.

- [x] **Step 1: Write failing installer/CI contract test** proving all new modules are packaged and no systemd/network mutation is introduced.
- [x] **Step 2: Run RED** against current installer; expected new files missing.
- [x] **Step 3: Modify installer** to copy/`py_compile` observation files only; do not create/enable/start any service.
- [x] **Step 4: Extend Foundation CI** to compile observation modules, run complete Atlas `unittest` discovery and emit `DEVEX_HOMELAB_ATLAS_OBSERVATION_RUNTIME_PASS`.
- [x] **Step 5: Run local full gate:** Network, Heartbeat, Pentium Agent, Atlas, `bash -n infrastructure/pentium/atlas/install-user.sh`, JSON validation and `git diff --check`.
- [x] **Step 6: Commit:** `git add infrastructure/pentium/atlas/install-user.sh .github/workflows/foundation-ci.yml infrastructure/pentium/atlas/tests && git commit -m "ci(atlas): validate observation runtime"`.
### Task 7: Exact-HEAD CI and read-only physical certification

**Files:** Modify `docs/as-built/2026-09-02-baseline.md` only after observed evidence; optionally append certification section to the design.

**Interfaces:** consumes pushed branch HEAD; produces exact-head CI evidence and READ-only Pentium/Core/x99 stimulus evidence.

- [x] **Step 1: Push/update Draft PR** only after local full gate passes; record exact HEAD SHA.
- [x] **Step 2: Require Foundation CI GREEN on that exact SHA** before physical observation.
- [x] **Step 3: Prepare deterministic user-level package** and transfer to Pentium without network/SSH/Tailscale/systemd changes.
- [x] **Step 4: Run READ-only smoke** against `pentium.self`, `core`, `x99`: verify baseline stimuli, no duplicate publication for unchanged snapshot, an injected/fake local transition for recovery semantics if no real incident occurs, and valid JSONL journal.
- [x] **Step 5: Do not install a persistent service yet.** Certification executes the runtime in foreground/bounded duration only.
- [x] **Step 6: Record exact source SHA, package hash, observed sources, stimulus counts, bus metrics and journal path in as-built; never claim unobserved 24h soak.**
- [x] **Step 7: Commit evidence:** `git add docs && git commit -m "docs(atlas): record observation runtime certification"`.


#### Contract Closure â€” 2026-09-04

Reconciliado antes da Task 8: `novelty_score` canÃ´nico, `SourceSnapshot.observed_at`, `SourcePolicy` com cooldown por fonte, severidade `critical` para indisponibilidade/falha de fonte requerida e loader de policies a partir de `observation_config.json`. A compatibilidade de `compute_novelty`, `SourceSchedule` e `schedule=` foi preservada.

A certificaÃ§Ã£o da closure usa pacote determinÃ­stico construÃ­do diretamente dos blobs Git; `git archive` no Windows foi rejeitado para certificaÃ§Ã£o apÃ³s converter LF em CRLF no tar.

### Task 8: Final HEAD, checkpoint and next-slice handoff

**Files:** documentation/checkpoint only.

- [x] **Step 1: Re-run complete local gate** after evidence docs and capture new final HEAD.
- [x] **Step 2: Push final HEAD and require fresh Foundation CI GREEN** for that exact SHA.
- [x] **Step 3: Update/create PR `/checkpoint` in pt-BR** with implementation, exact test counts, exact-head CI, physical READ-only evidence, blockers and explicit statement that persistent 24/7 service activation is not yet performed.
- [x] **Step 4: Declare next safe slice** as Affective State Engine only after Observation Runtime is GREEN/certified.

## Definition of Done

The slice is complete only when all TDD tests pass; `Stimulus` contracts are stable; bus is bounded and preserves critical under pressure; unchanged snapshots do not spam; failures/backoff are isolated; recovery is explicit; journal is valid; existing 43-test baseline remains GREEN plus new tests; final exact HEAD has Foundation CI GREEN; READ-only Pentium/Core/x99 smoke is evidenced; and `/checkpoint` matches the final SHA.

## Plan self-review

- Spec coverage: model, fingerprint, novelty, bus, journal, initial sources, dedup, recovery, timeout/backoff, failure isolation, shutdown, CI and READ-only certification each map to explicit tasks.
- Type continuity: `Stimulus` is produced by runtime and consumed by bus/journal; source adapters only produce `SourceSnapshot`.
- Scope: no LLM, emotional state, audio/voice, persistent service activation, network mutation or action authority.
- No placeholder or deferred implementation language remains inside implementation steps.
