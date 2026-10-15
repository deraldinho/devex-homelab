# Atlas Voice Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ativar e certificar o Voice do Atlas no Pentium sem quebrar observation, cognitive, dashboard ou os gates de SHA.

**Architecture:** Manter `VoiceRuntime` como owner de captura/STT/wake/cognição/TTS. Tornar certificações feature-aware, publicar health bounded do Voice, endurecer o unit systemd e usar um ativador fail-closed que só habilita o serviço quando dependências e acesso ALSA estiverem válidos.

**Tech Stack:** Python 3, unittest, systemd user services, ALSA, whisper.cpp, eSpeak NG, Hermes CLI.

**Spec:** `docs/superpowers/specs/2026-09-12-atlas-full-activation-design.md`

## Global Constraints

- Voice ativo continua usando o pipeline cognitivo canônico; não existe LLM paralelo.
- `ATLAS_EXPECTED_SHA` deve chegar ao Voice pelo mesmo `observation.env` usado pelos runtimes principais.
- Falha de áudio não pode derrubar observation/cognitive/dashboard.
- ANC permanece desligado nesta fase.
- Nenhuma expansão de autonomia/capabilities nesta fase.
- Deploy físico só ocorre com CI exact-HEAD GREEN e backup prévio.
- O usuário do serviço precisa ter acesso `rw` a `/dev/snd/*`; no Pentium isso exige grupo `audio`.

---
### Task 1: Certificações feature-aware para Voice

**Files:**
- Modify: `infrastructure/pentium/atlas/cognitive_context_bridge_certification.py`
- Modify: `infrastructure/pentium/atlas/hermes_physical_smoke.py`
- Test: `infrastructure/pentium/atlas/tests/test_cognitive_context_bridge_certification.py`
- Test: `infrastructure/pentium/atlas/tests/test_hermes_physical_smoke.py`

**Interfaces:**
- Consumes: estado systemd de `atlas-voice.service`.
- Produces: contrato `voice_expected_active: bool` que exige `active/enabled` quando verdadeiro e preserva `inactive/disabled` quando falso.

- [ ] **Step 1: Write failing tests** for enabled Voice acceptance and wrong-state rejection.
- [ ] **Step 2: Run focused tests** and verify failures are caused by the old hard-coded inactive rule.
- [ ] **Step 3: Implement minimal feature-aware checks**. `HermesPhysicalSmoke.check_runtime(..., voice_expected_active=False)` must compare the observed state against the requested mode instead of always rejecting active Voice.
- [ ] **Step 4: Run focused tests** until GREEN.
- [ ] **Step 5: Commit** with `fix(atlas): make voice certification feature aware`.

### Task 2: Voice health + deployment identity

**Files:**
- Create: `infrastructure/pentium/atlas/voice_health.py`
- Modify: `infrastructure/pentium/atlas/voice_daemon.py`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Test: `infrastructure/pentium/atlas/tests/test_voice_health.py`
- Test: `infrastructure/pentium/atlas/tests/test_v1_voice_daemon.py`

**Interfaces:**
- Produces: `VoiceHealthPublisher(path).publish(status, state, reason, expected_sha)` writing atomic JSON mode `0600`.
- Health schema: `schema_version=1`, `status`, `state`, `reason`, `expected_sha`, `generated_at`.

- [ ] **Step 1: Write failing tests** proving atomic bounded health and SHA propagation.
- [ ] **Step 2: Run tests** and confirm RED because health publisher/wiring do not exist.
- [ ] **Step 3: Implement publisher and daemon wiring**; publish `healthy/LISTENING` after successful cycles and `degraded` on caught exceptions.
- [ ] **Step 4: Package/compile the new module** in `install-user.sh` and run focused tests.
- [ ] **Step 5: Commit** with `feat(atlas): publish voice runtime health`.
### Task 3: Service hardening + preflight fail-closed

**Files:**
- Modify: `infrastructure/pentium/atlas/atlas-voice.service`
- Create: `infrastructure/pentium/atlas/voice_activation_preflight.py`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Test: `infrastructure/pentium/atlas/tests/test_voice_preflight.py`

**Interfaces:**
- `VoiceActivationPreflight.run()` retorna `ready=false` salvo quando grupo `audio`, acesso rw aos PCM, SHA implantado exato e bin?rios f?sicos est?o v?lidos.
- O preflight ? somente leitura: ele nunca altera o estado de servi?os; a promo??o f?sica permanece uma a??o expl?cita do operador ap?s `ready=true`.

- [ ] **Step 1: Write failing packaging/contract tests** for env loading, UMask, memory bounds and fail-closed preflight tokens.
- [ ] **Step 2: Run tests** and verify RED against the current permissive service/install packaging.
- [ ] **Step 3: Implement minimum hardening**: `EnvironmentFile=-%h/pentium-agent/atlas/runtime/observation.env`, `UMask=0077`, `MemoryHigh=256M`, `MemoryMax=384M`; package `voice_activation_preflight.py` sem autoativar Voice no installer gen?rico.
- [ ] **Step 4: Run focused tests + `bash -n`** for installer and preflight packaging.
- [ ] **Step 5: Commit** with `feat(atlas): add fail closed voice preflight`.

### Task 4: Full software gate and exact-HEAD CI

**Files:** no production changes expected.

- [ ] **Step 1:** Run the complete Atlas unittest suite.
- [ ] **Step 2:** Run Dashboard suite, `bash -n` and `git diff --check`.
- [ ] **Step 3:** Push branch and open PR based on current `main`.
- [ ] **Step 4:** Require Atlas Avatar/Foundation checks GREEN on the exact PR HEAD.
- [ ] **Step 5:** Merge only after all required checks are GREEN.

### Task 5: Physical entitlement, deploy and Voice smoke

**Physical prerequisite:** `deraldinho` must belong to Linux group `audio`. Current evidence shows `/dev/snd/*` is `0660 root:audio` and the user lacks that supplementary group.

- [ ] **Step 1:** Operator runs `sudo usermod -aG audio deraldinho`, then refreshes the login/user-manager session so new services inherit the group.
- [ ] **Step 2:** Verify `id` includes `audio` and `arecord -l`/`aplay -l` expose card 0/device 0.
- [ ] **Step 3:** Create backup of Atlas units/config/runtime metadata; deploy artifact built from the merged exact SHA with `ATLAS_DEPLOY_SHA=<merged-sha>`.
- [ ] **Step 4:** Run the Voice preflight and require `ready=true`; only then the operator explicitly promotes `atlas-voice.service` and verifies active state, `NRestarts=0`, fresh `voice-health.json`, exact SHA, and no restart loop.
- [ ] **Step 5:** Perform real capture/STT/wake/TTS smoke. A spoken `Atlas ...` must reach cognition and produce audible TTS while observation/cognitive/dashboard stay GREEN.
- [ ] **Step 6:** Run short soak and inspect Voice plus core service logs for OOM/tracebacks/CalledProcessError/TimeoutExpired.
- [ ] **Step 7:** If any physical gate fails, disable only `atlas-voice.service` and restore the pre-Voice backup; do not roll back stable Observation/Cognitive/Dashboard.

## Concrete implementation contracts

Task 1 dataclass/API shape:
```python
voice_expected_active: bool = False

def check_runtime(self, *, repo_root: Path, expected_sha: str,
                  voice_expected_active: bool = False) -> RuntimeCheck:
    ...
```
Enabled mode must fail with `voice_service_not_active` / `voice_service_not_enabled`; disabled mode preserves the existing inactive/disabled failures. CLI adds `--voice-expected-active` with `action="store_true"` and forwards it through `execute()`.

Task 2 publisher shape:
```python
class VoiceHealthPublisher:
    def __init__(self, path: Path): ...
    def publish(self, *, status: str, state: str,
                reason: str | None, expected_sha: str | None) -> None: ...
```
Implementation writes `<path>.tmp`, `chmod 0600`, then `os.replace(tmp, path)`. `voice_daemon.main()` publishes after each `run_once()` and on caught exceptions.

Task 3 preflight core:
```python
result = VoiceActivationPreflight(agent_root).run(expected_sha)
if not result["ready"]:
    raise SystemExit("voice_preflight_not_ready")
```
The preflight verifies audio entitlement, device access, exact SHA and executable runtime binaries, and intentionally performs no service mutation.
