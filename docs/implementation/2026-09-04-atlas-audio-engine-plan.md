# Atlas Audio Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar `ReactionDecision` em playback físico real no dispositivo de áudio padrão do Pentium, com biblioteca Creative Commons verificável, fila bounded e preempção crítica.

**Architecture:** `ReactionEngine` continua dono da decisão semântica. `AudioLibrary -> AudioResolver -> AudioEngine -> AudioBackend` resolve mídia versionada, agenda playback num worker único em processo e usa `ffplay` como backend primário; `aplay` é fallback exclusivo para WAV. Download e validação de licença/hash ficam fora do hot path.

**Tech Stack:** Python 3.14+, stdlib, `ffplay`/FFmpeg, `aplay`, Bash, unittest, GitHub Actions.

**Spec:** `docs/implementation/2026-09-03-atlas-audio-engine-design.md`

## Global Constraints

- execução e toda saída física: somente `pentium`, sempre no dispositivo de áudio padrão;
- formatos iniciais: `wav`, `mp3`, `ogg`/Vorbis e `flac`;
- licenças: `CC0`, `CC-BY`, `CC-BY-SA`, preferência `CC0 > CC-BY > CC-BY-SA`;
- binários de áudio não entram no Git; manifesto guarda origem, licença, atribuição e SHA-256;
- `critical` preempta imediatamente playback não crítico; fila é curta e bounded;
- sem transcoding no hot path, URL arbitrária no runtime, `shell=True`, novo daemon ou nova unidade systemd;
- CI usa backend fake; certificação física só inicia após CI GREEN do HEAD exato.

## File map

Create: `audio_model.py`, `audio_library.py`, `audio_resolver.py`, `audio_backend.py`, `audio_engine.py`, `audio_journal.py`, `audio-library.json`, `sync-audio-library.py` e testes dedicados. Modify: `install-user.sh`, `.github/workflows/foundation-ci.yml`; as-built somente após evidência física.
### Task 1: Canonical audio model and manifest parser

**Files:** Create `audio_model.py`, `audio_library.py`, `tests/test_audio_model.py`, `tests/test_audio_library.py`.

**Interfaces:** `AudioAsset`, `PlaybackRequest`, `PlaybackResult`; `load_audio_library(path: Path) -> tuple[AudioAsset, ...]`.

- [ ] **Step 1: Write failing tests.** Cover frozen dataclasses; exact accepted formats `wav|mp3|ogg|flac`; exact licenses `CC0|CC-BY|CC-BY-SA`; required fields; unknown license/format rejection.
- [ ] **Step 2: Run RED.** `python3 -m unittest infrastructure.pentium.atlas.tests.test_audio_model infrastructure.pentium.atlas.tests.test_audio_library -v`; expected import failure.
- [ ] **Step 3: Implement minimal parser/types.** `AudioAsset` requires `asset_id`, `reaction_id`, `category`, `source_page_url`, `source_url`, `author`, `license`, `license_url`, `attribution`, `sha256`, `format`, `filename`, optional `duration_ms`.
- [ ] **Step 4: Run GREEN.** Same command; expected PASS.
- [ ] **Step 5: Commit.** `git add infrastructure/pentium/atlas/audio_model.py infrastructure/pentium/atlas/audio_library.py infrastructure/pentium/atlas/tests/test_audio_model.py infrastructure/pentium/atlas/tests/test_audio_library.py && git commit -m "feat(atlas): define audio library contract"`

### Task 2: Resolve local verified assets

**Files:** Create `audio_resolver.py`, `tests/test_audio_resolver.py`.

**Interfaces:** `ResolvedAudio(asset: AudioAsset, path: Path)`; `resolve_audio(assets, reaction_id, category, media_root) -> ResolvedAudio | None`.

- [ ] **Step 1: Write failing tests.** Exact `reaction_id`, category fallback, missing file, absolute/`..` filename rejection and SHA mismatch raising `AudioIntegrityError`.
- [ ] **Step 2: Run RED.** `python3 -m unittest infrastructure.pentium.atlas.tests.test_audio_resolver -v`.
- [ ] **Step 3: Implement resolver.** Resolve only `media_root / filename`, compute local SHA-256, never access network.
- [ ] **Step 4: Run GREEN** then all Atlas tests.
- [ ] **Step 5: Commit.** `git add infrastructure/pentium/atlas/audio_resolver.py infrastructure/pentium/atlas/tests/test_audio_resolver.py && git commit -m "feat(atlas): resolve verified audio assets"`
### Task 3: Playback backend with multi-format support

**Files:** Create `audio_backend.py`, `tests/test_audio_backend.py`.

**Interfaces:** `AudioBackend.play(path: Path, timeout_s: float) -> BackendPlayback`; `AudioBackend.stop() -> None`; `FfplayBackend`, `AplayWavFallbackBackend`, `FakeAudioBackend`.

- [ ] **Step 1: Write failing tests.** Cover fixed argv, `shell=False`, `ffplay` primary, no explicit device id, WAV-only `aplay` fallback, timeout, non-zero exit, idempotent `stop()`.
- [ ] **Step 2: Run RED.** `python3 -m unittest infrastructure.pentium.atlas.tests.test_audio_backend -v`.
- [ ] **Step 3: Implement backend.** Primary argv: `ffplay -nodisp -autoexit -loglevel error <path>`; fallback argv: `aplay <path>` only for `.wav`; never construct argv from manifest text beyond the validated local path.
- [ ] **Step 4: Run GREEN.** Patch `subprocess.Popen`; no real playback in tests.
- [ ] **Step 5: Commit.** `git add infrastructure/pentium/atlas/audio_backend.py infrastructure/pentium/atlas/tests/test_audio_backend.py && git commit -m "feat(atlas): add multi-format audio backend"`

### Task 4: Bounded audio engine and critical preemption

**Files:** Create `audio_engine.py`, `tests/test_audio_engine.py`.

**Interfaces:** `AudioEngine(backend, queue_size, max_age_s, result_sink)` with `start()`, `submit(request, resolved_audio)`, `stop()`.

- [ ] **Step 1: Write failing tests.** Cover bounded capacity, obsolete non-critical drop, priority ordering, one worker, `critical` stopping active non-critical before playback, timeout propagation and clean shutdown.
- [ ] **Step 2: Run RED.** `python3 -m unittest infrastructure.pentium.atlas.tests.test_audio_engine -v`.
- [ ] **Step 3: Implement engine.** Use `queue.PriorityQueue(maxsize=queue_size)`, monotonic sequence for ties and one worker thread owning backend calls; critical submission invokes backend `stop()` against active non-critical playback.
- [ ] **Step 4: Run GREEN** repeatedly, then run all Atlas tests.
- [ ] **Step 5: Commit.** `git add infrastructure/pentium/atlas/audio_engine.py infrastructure/pentium/atlas/tests/test_audio_engine.py && git commit -m "feat(atlas): add bounded audio playback engine"`
### Task 5: Playback result journal

**Files:** Create `audio_journal.py`, `tests/test_audio_journal.py`.

**Interfaces:** `append_playback_event(path: Path, result: PlaybackResult) -> None`.

- [ ] **Step 1: Write failing tests.** Verify JSONL for `played`, `preempted`, `asset_missing`, `timeout`, observed duration and optional error cause.
- [ ] **Step 2: Run RED.** `python3 -m unittest infrastructure.pentium.atlas.tests.test_audio_journal -v`.
- [ ] **Step 3: Implement journal.** Append sorted UTF-8 JSON per line, flush, create parent directory, raise typed `AudioJournalError` on `OSError`; keep separate from semantic journal.
- [ ] **Step 4: Run GREEN** and parse each line independently with `json.loads`.
- [ ] **Step 5: Commit.** `git add infrastructure/pentium/atlas/audio_journal.py infrastructure/pentium/atlas/tests/test_audio_journal.py && git commit -m "feat(atlas): journal audio playback results"`

### Task 6: Creative Commons manifest and atomic media sync

**Files:** Create `audio-library.json`, `sync-audio-library.py`, `tests/test_sync_audio_library.py`.

**Interfaces:** Sync reads only manifest URLs and writes validated files under `~/pentium-agent/atlas/media/`.

- [ ] **Step 1: Curate real assets.** Use source pages with verifiable `CC0`, `CC-BY` or `CC-BY-SA`; record source page/direct URL, author, license, license URL, attribution, format, filename and SHA-256. Cover `healthy/calm`, `busy/working`, `critical.canonical`, `recovered/relief`.
- [ ] **Step 2: Write failing sync tests.** Inject opener/reader; verify `.part` staging, hash rejection, preservation of valid existing asset and atomic `Path.replace()`.
- [ ] **Step 3: Run RED.** `python3 -m unittest infrastructure.pentium.atlas.tests.test_sync_audio_library -v`.
- [ ] **Step 4: Implement sync.** No shell; only manifest URLs; stream to temp file, hash, then promote atomically.
- [ ] **Step 5: Validate manifest.** `python3 -m json.tool infrastructure/pentium/atlas/audio-library.json >/dev/null` and load with `load_audio_library()`.
- [ ] **Step 6: Run GREEN** for sync and complete Atlas suite.
- [ ] **Step 7: Commit.** `git add infrastructure/pentium/atlas/audio-library.json infrastructure/pentium/atlas/sync-audio-library.py infrastructure/pentium/atlas/tests/test_sync_audio_library.py && git commit -m "feat(atlas): add Creative Commons audio library sync"`
### Task 7: User-level installer and CI gate

**Files:** Modify `install-user.sh`, `.github/workflows/foundation-ci.yml`; add installer contract test if required by existing test style.

- [ ] **Step 1: Write failing installer contract test.** Require new modules, manifest and sync script to be installed; require `media/`; assert no configured device id/name.
- [ ] **Step 2: Run RED** against current installer.
- [ ] **Step 3: Modify installer.** Install new modules + manifest + sync tool, create `media/`, detect `ffplay` and emit explicit diagnostics without installing packages automatically; `aplay` remains optional WAV fallback.
- [ ] **Step 4: Extend CI.** Compile all Atlas modules, validate both JSON files, run entire Atlas suite with fake backend, emit `DEVEX_HOMELAB_ATLAS_AUDIO_ENGINE_PASS`.
- [ ] **Step 5: Run full local gate.** Network, Heartbeat, Pentium Agent, Atlas, `bash -n`, JSON validation and `git diff --check` all pass.
- [ ] **Step 6: Commit.** `git add infrastructure/pentium/atlas/install-user.sh .github/workflows/foundation-ci.yml infrastructure/pentium/atlas/tests && git commit -m "ci(atlas): validate audio engine foundation"`

### Task 8: Exact-HEAD CI, physical Pentium certification, as-built and checkpoint

**Files:** Modify `docs/as-built/2026-09-02-baseline.md` and Audio Engine design only after physical evidence exists.

- [ ] **Step 1: Push/update PR stack** only after the full local gate; record exact HEAD SHA.
- [ ] **Step 2: Require Foundation CI GREEN** on that exact SHA before physical work.
- [ ] **Step 3: Build deterministic deployment package** with source SHA, modules, manifest and sync tool; compute package SHA-256.
- [ ] **Step 4: Verify Pentium prerequisites READ-only.** Confirm `ffplay` and default audio route/device visibility; do not alter network, SSH, Tailscale or systemd.
- [ ] **Step 5: Install user-level package** at `~/pentium-agent/atlas`, sync only curated CC assets and verify every installed asset SHA.
- [ ] **Step 6: Run audible smoke.** Play `healthy`, `busy`, start normal audio then inject `critical.canonical` to prove immediate preemption, then play `recovered`; all output comes from Pentium default device.
- [ ] **Step 7: Verify playback journal** includes `played` plus explicit `preempted` for the interrupted non-critical playback.
- [ ] **Step 8: Update as-built/design** with only observed evidence: implementation SHA, package SHA, backend/device observation, asset hashes/licenses, CI IDs, smoke and journal location.
- [ ] **Step 9: Re-run local full gate after docs**, commit evidence, push final HEAD and require fresh exact-HEAD Foundation CI GREEN.
- [ ] **Step 10: Update PR `/checkpoint`** in pt-BR with final HEAD, implementation, tests, CI, physical evidence, licenses, blockers and next safe slice.
## Definition of Done

- Tasks 1-7 implemented RED -> GREEN with reviewable commits.
- WAV, MP3, OGG/Vorbis and FLAC supported; no hot-path transcoding.
- Manifest contains only verified CC0/CC-BY/CC-BY-SA assets with SHA-256 and attribution metadata.
- `critical.canonical` has an independent required asset and physically preempts normal playback.
- No audio binary is versioned in Git.
- Final exact HEAD has Foundation CI GREEN.
- Physical Pentium certification is audibly GREEN on the default output device.
- Playback journal, as-built and `/checkpoint` agree with final evidence.

## Plan self-review

- Spec coverage: resolver, formats, licenses, hash validation, default device, bounded queue, obsolescence, preemption, backend, journal, installer, CI and physical certification map to explicit tasks.
- Interfaces: model -> library -> resolver -> backend/engine -> journal; sync remains outside runtime hot path.
- Scope: no LLM, STT, TTS, microphone, new daemon/systemd, arbitrary shell or audio output from x99/Core/MikroTik.
- Execution invariant: every production component begins with focused RED test and ends with GREEN + commit.
## Definition of Done

A slice só termina quando todos os testes TDD passam; o manifesto contém apenas assets CC0/CC-BY/CC-BY-SA verificáveis; WAV/MP3/OGG/FLAC são suportados pelo contrato certificado; a mídia permanece fora do Git e é validada por SHA-256; `critical` preempta playback normal; toda saída física ocorre exclusivamente pelo dispositivo padrão do Pentium; o journal registra resultados; o HEAD final com documentação possui Foundation CI GREEN; o smoke físico audível passa; e o `/checkpoint` usa exatamente essas evidências.