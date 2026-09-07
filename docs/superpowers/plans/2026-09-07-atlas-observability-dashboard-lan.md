# Atlas Observability Dashboard LAN Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar um dashboard web read-only no Pentium, acessível pelo x99 em `http://192.168.88.3:8765`, que explique o estado técnico do Atlas sem oferecer qualquer caminho de CONTROL ou escrita.

**Architecture:** Criar um subsistema isolado em `infrastructure/pentium/dashboard/`. `dashboard_collectors.py` coleta fontes locais bounded e sanitizadas; `atlas_dashboard.py` expõe somente GET usando Python stdlib; `dashboard.html` renderiza o snapshot e faz polling a cada 2 s. O serviço systemd de usuário faz bind exclusivamente em `192.168.88.3:8765` e não altera `atlas-voice.service`.

**Tech Stack:** Python 3 stdlib (`http.server`, `json`, `subprocess`, `/proc`, `/sys`), HTML/CSS/JS sem dependências externas, systemd user service, `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-07-atlas-observability-dashboard-lan-design.md`

## Global Constraints

- Pentium LAN autoritativa: `enp4s0`, `192.168.88.3/24`.
- x99 LAN autoritativa: `Ethernet 2`, `192.168.88.4/24`.
- Bind obrigatório: `192.168.88.3:8765`; proibido `0.0.0.0`.
- API somente GET; qualquer método de escrita responde `405 Method Not Allowed`.
- Sem shell/SSH/CONTROL/restart/config mutation/upload/eval.
- Não importar nem instanciar `ManagedControlService`.
- Não persistir áudio bruto nem exibir/armazenar transcrições.
- Journal contribui apenas com markers técnicos allowlisted.
- Falha de um coletor degrada apenas seu grupo, nunca derruba o snapshot inteiro.
- `atlas-voice.service` deve permanecer `disabled/inactive` durante implantação e certificação.
- Sem dependências Python externas obrigatórias.

---## File Structure

- Create `infrastructure/pentium/dashboard/dashboard_collectors.py` — collectors bounded, modelagem do snapshot, sanitização de config e journal.
- Create `infrastructure/pentium/dashboard/atlas_dashboard.py` — servidor HTTP GET-only, roteamento e respostas bounded.
- Create `infrastructure/pentium/dashboard/dashboard.html` — UI dark responsiva e polling de 2 s.
- Create `infrastructure/pentium/dashboard/config.json` — bind LAN, porta, paths locais e limites.
- Create `infrastructure/pentium/dashboard/systemd/atlas-dashboard.service` — unit user hardenizada.
- Create `infrastructure/pentium/dashboard/install-user.sh` — instalação idempotente do dashboard.
- Create `infrastructure/pentium/dashboard/tests/test_dashboard_collectors.py` — contratos de coleta/sanitização.
- Create `infrastructure/pentium/dashboard/tests/test_atlas_dashboard.py` — contratos HTTP/read-only.
- Create `infrastructure/pentium/dashboard/tests/test_dashboard_packaging.py` — config, HTML, service e installer.
- Modify `docs/superpowers/specs/2026-09-07-atlas-observability-dashboard-lan-design.md` somente se a implementação revelar uma divergência factual; não expandir escopo.

### Interfaces estáveis

`dashboard_collectors.collect_status(config: dict, *, command_runner=run_command) -> dict`

`dashboard_collectors.collect_events(config: dict, *, command_runner=run_command) -> list[dict]`

`dashboard_collectors.load_config(path: Path) -> dict`

`atlas_dashboard.build_server(config: dict, *, collectors=dashboard_collectors) -> ThreadingHTTPServer`

O schema de `/api/status` preserva os grupos: `atlas`, `services`, `voice`, `audio`, `anc`, `system`, `network`.
---

### Task 1: Configuration and bounded system collectors

**Files:**
- Create: `infrastructure/pentium/dashboard/config.json`
- Create: `infrastructure/pentium/dashboard/dashboard_collectors.py`
- Test: `infrastructure/pentium/dashboard/tests/test_dashboard_collectors.py`

**Interfaces:**
- Consumes: heartbeat snapshot at `~/pentium-agent/data/health/latest.json`, `/proc/meminfo`, `/proc/uptime`, deploy marker.
- Produces: `load_config()`, `CommandResult`, `run_command()`, `collect_system()`, `collect_services()`, `read_deploy_sha()`.

- [ ] **Step 1: Write failing config and collector tests**

```python
class DashboardConfigTests(unittest.TestCase):
    def test_config_is_pinned_to_lan_and_rejects_wildcard(self):
        cfg = collectors.load_config(ROOT / "config.json")
        self.assertEqual("192.168.88.3", cfg["bind_host"])
        self.assertEqual(8765, cfg["port"])
        bad = dict(cfg, bind_host="0.0.0.0")
        with self.assertRaises(ValueError):
            collectors.validate_config(bad)

    def test_service_probe_uses_fixed_systemctl_argv(self):
        calls = []
        def runner(argv, timeout):
            calls.append(argv)
            return collectors.CommandResult(0, "active\n", "")
        state = collectors.read_user_unit("pentium-agent.service", command_runner=runner)
        self.assertEqual("active", state["active"])
        self.assertEqual([["systemctl", "--user", "is-active", "pentium-agent.service"]], calls)
```
- [ ] **Step 2: Run tests and verify RED**

Run:
```bash
python -m unittest infrastructure.pentium.dashboard.tests.test_dashboard_collectors -v
```
Expected: import/file failures because `dashboard_collectors.py` and `config.json` do not exist.

- [ ] **Step 3: Implement config validation and fixed command runner**

```python
@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

def validate_config(cfg: dict) -> dict:
    if cfg.get("schema_version") != 1:
        raise ValueError("dashboard schema_version must be 1")
    if cfg.get("bind_host") != "192.168.88.3" or int(cfg.get("port", 0)) != 8765:
        raise ValueError("dashboard bind must be 192.168.88.3:8765")
    return cfg

def run_command(argv: list[str], timeout: float) -> CommandResult:
    completed = subprocess.run(argv, capture_output=True, text=True,
                               timeout=timeout, check=False)
    return CommandResult(completed.returncode, completed.stdout[:65536], completed.stderr[:8192])
```
- [ ] **Step 4: Add bounded `/proc` and service collection**

Implement `read_meminfo()`, `read_uptime_s()`, `read_deploy_sha()` and `collect_services()` with fixed paths/argv. Service state must include `active` and `enabled`; command failures return `unknown` plus a short `error`, never raise past the group collector.

```python
def read_user_unit(unit: str, *, command_runner=run_command) -> dict:
    active = command_runner(["systemctl", "--user", "is-active", unit], 2.0)
    enabled = command_runner(["systemctl", "--user", "is-enabled", unit], 2.0)
    return {
        "active": active.stdout.strip() if active.returncode == 0 else "inactive",
        "enabled": enabled.stdout.strip() if enabled.returncode == 0 else "disabled",
    }
```

- [ ] **Step 5: Run collector tests GREEN and commit**

Run:
```bash
python -m unittest infrastructure.pentium.dashboard.tests.test_dashboard_collectors -v
git diff --check
```
Expected: PASS.

Commit:
```bash
git add infrastructure/pentium/dashboard/config.json infrastructure/pentium/dashboard/dashboard_collectors.py infrastructure/pentium/dashboard/tests/test_dashboard_collectors.py
git commit -m "feat(atlas): adicionar coletores bounded do dashboard"
```

---

### Task 2: Voice, audio, ANC and network observability

**Files:**
- Modify: `infrastructure/pentium/dashboard/dashboard_collectors.py`
- Test: `infrastructure/pentium/dashboard/tests/test_dashboard_collectors.py`

**Interfaces:**
- Consumes: `config_voice.json`, `/proc/asound/cards`, `arecord -l`, `ip -4 -br addr`, journal markers.
- Produces: `collect_voice()`, `collect_audio()`, `collect_anc()`, `collect_network()`.

- [ ] **Step 1: Write failing tests for sanitization and audio state**

```python
def test_voice_config_exposes_only_allowlisted_fields(self):
    cfg = {"wake_phrase": "Atlas", "anc_enabled": False,
           "llm_model": "/secret/model.gguf", "tts_device": "plughw:0,0"}
    safe = collectors.sanitize_voice_config(cfg)
    self.assertEqual({"wake_phrase": "Atlas", "anc_enabled": False,
                      "tts_device": "plughw:0,0"}, safe)
    self.assertNotIn("llm_model", safe)

def test_zero_signal_usb_is_degraded(self):
    audio = collectors.classify_audio_probe({"name": "USB", "rms": 0.0, "peak": 0})
    self.assertEqual("degraded", audio["status"])
    self.assertEqual("signal_zero", audio["reason"])
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:
```bash
python -m unittest infrastructure.pentium.dashboard.tests.test_dashboard_collectors -v
```
Expected: FAIL because sanitizers/audio collectors are undefined.

- [ ] **Step 3: Implement allowlisted config and technical journal parsing**

Allow only technical voice markers matching:
```python
VOICE_MARKERS = (
    "ATLAS_V1_VOICE_DAEMON_LISTENING",
    "ATLAS_V1_VOICE_STATE=",
    "ATLAS_V1_VOICE_DEGRADED",
)
```
Never return transcript text, raw journal lines outside this allowlist, or arbitrary environment/config values.
- [ ] **Step 4: Implement audio/ANC/network collectors with bounded subprocesses**

Use fixed argv only:
```python
["arecord", "-l"]
["ip", "-4", "-br", "addr"]
["journalctl", "--user", "-u", "atlas-voice.service", "-n", "80", "--no-pager"]
```

`collect_anc()` derives status from sanitized config plus current audio observations. If `anc_enabled` is false, return `off`; if a configured reference is absent/zero-signal, return `degraded` with explicit reason. Never auto-enable ANC.

- [ ] **Step 5: Run focused tests GREEN and commit**

Run:
```bash
python -m unittest infrastructure.pentium.dashboard.tests.test_dashboard_collectors -v
git diff --check
```
Expected: PASS.

Commit:
```bash
git add infrastructure/pentium/dashboard/dashboard_collectors.py infrastructure/pentium/dashboard/tests/test_dashboard_collectors.py
git commit -m "feat(atlas): observar voz audio anc e rede no dashboard"
```

---

### Task 3: Consolidated snapshot and technical timeline

**Files:**
- Modify: `infrastructure/pentium/dashboard/dashboard_collectors.py`
- Test: `infrastructure/pentium/dashboard/tests/test_dashboard_collectors.py`

**Interfaces:**
- Consumes: all collectors from Tasks 1-2.
- Produces: `collect_status(config, command_runner=...) -> dict`, `collect_events(config, command_runner=...) -> list[dict]`.

- [ ] **Step 1: Write failing partial-degradation tests**

```python
def test_one_collector_failure_does_not_break_snapshot(self):
    status = collectors.merge_groups({
        "atlas": {"status": "green"},
        "audio": RuntimeError("probe failed"),
    })
    self.assertEqual("green", status["atlas"]["status"])
    self.assertEqual("unknown", status["audio"]["status"])
    self.assertIn("probe failed", status["audio"]["error"])
```
- [ ] **Step 2: Implement bounded group merge and event normalization**

`collect_status()` must always return all seven stable groups. `collect_events()` returns at most 50 events shaped as `{timestamp, source, severity, message}` and strips arbitrary journal payloads.

- [ ] **Step 3: Run tests GREEN and commit**

Run:
```bash
python -m unittest infrastructure.pentium.dashboard.tests.test_dashboard_collectors -v
```
Expected: PASS.

Commit:
```bash
git add infrastructure/pentium/dashboard/dashboard_collectors.py infrastructure/pentium/dashboard/tests/test_dashboard_collectors.py
git commit -m "feat(atlas): consolidar snapshot e timeline tecnica"
```

---

### Task 4: GET-only HTTP server

**Files:**
- Create: `infrastructure/pentium/dashboard/atlas_dashboard.py`
- Test: `infrastructure/pentium/dashboard/tests/test_atlas_dashboard.py`

**Interfaces:**
- Consumes: `collect_status()`, `collect_events()`, `dashboard.html`, `config.json`.
- Produces: `build_server(config, collectors=dashboard_collectors)` and HTTP routes `/`, `/api/status`, `/api/events`, `/healthz`.

- [ ] **Step 1: Write failing route/method tests**

Use an ephemeral localhost test server only in unit tests. Assert GET=200, POST/PUT/DELETE=405, unknown path=404, JSON content-type, `Cache-Control: no-store`, and response body below configured max bytes.

- [ ] **Step 2: Implement minimal stdlib handler**

Use `ThreadingHTTPServer` plus a handler with explicit `do_GET`; all write verbs call one `_method_not_allowed()` path. No request body is parsed and no user-controlled subprocess input exists.

- [ ] **Step 3: Run HTTP tests GREEN and commit**

Run:
```bash
python -m unittest infrastructure.pentium.dashboard.tests.test_atlas_dashboard -v
```
Expected: PASS.

Commit:
```bash
git add infrastructure/pentium/dashboard/atlas_dashboard.py infrastructure/pentium/dashboard/tests/test_atlas_dashboard.py
git commit -m "feat(atlas): expor dashboard http somente leitura"
```

---

### Task 5: Dashboard UI

**Files:**
- Create: `infrastructure/pentium/dashboard/dashboard.html`
- Test: `infrastructure/pentium/dashboard/tests/test_dashboard_packaging.py`

**Interfaces:**
- Consumes: `/api/status` and `/api/events`.
- Produces: browser UI with 2-second polling and textual status labels.

- [ ] **Step 1: Write failing static-contract tests**

Assert the HTML contains the seven status sections, the pipeline labels `MIC`, `ANC`, `VAD`, `Whisper`, `Wake`, `Qwen`, `TTS`, and `setInterval(refresh, 2000)` or equivalent fixed 2-second polling.

- [ ] **Step 2: Implement dependency-free HTML/CSS/JS**

Render cards for Atlas, services, voice, audio, ANC, system/network and timeline. Every state must display text (`GREEN`, `YELLOW`, `RED`, `PAUSED`, `UNKNOWN`) in addition to color. A failed fetch changes only the affected region to `UNKNOWN`.

- [ ] **Step 3: Run packaging/UI tests GREEN and commit**

Run:
```bash
python -m unittest infrastructure.pentium.dashboard.tests.test_dashboard_packaging -v
```
Expected: PASS.

Commit:
```bash
git add infrastructure/pentium/dashboard/dashboard.html infrastructure/pentium/dashboard/tests/test_dashboard_packaging.py
git commit -m "feat(atlas): adicionar interface web de observabilidade"
```

---

### Task 6: systemd service and installer

**Files:**
- Create: `infrastructure/pentium/dashboard/systemd/atlas-dashboard.service`
- Create: `infrastructure/pentium/dashboard/install-user.sh`
- Modify: `infrastructure/pentium/dashboard/tests/test_dashboard_packaging.py`

**Interfaces:**
- Consumes: dashboard Python/HTML/config files.
- Produces: installed user service `atlas-dashboard.service`.

- [ ] **Step 1: Write failing packaging/security tests**

Assert service contains `NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectSystem=strict`, `ProtectHome=read-only`, bind config exactly `192.168.88.3`, and installer never references `enable --now atlas-voice.service` or `start atlas-voice.service`.

- [ ] **Step 2: Implement service and idempotent installer**

Install under `%h/pentium-agent/dashboard`, copy the unit to `%h/.config/systemd/user`, `py_compile` Python files, `daemon-reload`, then `enable --now atlas-dashboard.service` only.

- [ ] **Step 3: Run syntax/packaging tests GREEN and commit**

Run:
```bash
python -m unittest infrastructure.pentium.dashboard.tests.test_dashboard_packaging -v
bash -n infrastructure/pentium/dashboard/install-user.sh
```
Expected: PASS.

Commit:
```bash
git add infrastructure/pentium/dashboard/systemd/atlas-dashboard.service infrastructure/pentium/dashboard/install-user.sh infrastructure/pentium/dashboard/tests/test_dashboard_packaging.py
git commit -m "feat(atlas): empacotar dashboard como servico user"
```

---

### Task 7: Full regression and exact-SHA certification

**Files:**
- No production file changes expected unless a verified regression requires a fix.

**Interfaces:**
- Consumes: completed dashboard subsystem.
- Produces: exact SHA ready for physical deployment.

- [ ] **Step 1: Run dashboard and Atlas regressions**

Run:
```bash
python -m unittest discover -s infrastructure/pentium/dashboard/tests -v
python -m unittest discover -s infrastructure/pentium/atlas/tests
python -m py_compile infrastructure/pentium/dashboard/*.py
python -m json.tool infrastructure/pentium/dashboard/config.json > NUL
bash -n infrastructure/pentium/dashboard/install-user.sh
git diff --check
```
Expected: all GREEN.

- [ ] **Step 2: Verify read-only source contract**

Search dashboard source for forbidden symbols/verbs:
```bash
git grep -n -E "ManagedControlService|managed_control|subprocess.*shell=True|do_POST|do_PUT|do_DELETE" -- infrastructure/pentium/dashboard
```
Expected: no production matches except explicit 405 handlers/tests where applicable; no CONTROL import.

- [ ] **Step 3: Commit any certification-only tests, push and record exact SHA**

```bash
git status --short
git push -u origin atlas/issue-20-observability-dashboard
git rev-parse HEAD
```
Expected: clean worktree and authoritative SHA recorded.

---

### Task 8: Physical deployment and LAN validation

**Files:**
- Deployed artifacts only; repository should remain unchanged.

**Interfaces:**
- Consumes: exact committed SHA from Task 7.
- Produces: live dashboard on Pentium LAN and x99 browser reachability evidence.

- [ ] **Step 1: Archive exact HEAD and verify checksum on x99/Pentium**

Create archive from exact HEAD, copy under `~/pentium-agent/runtime/deploy/`, compare SHA-256 before installation, and install via `infrastructure/pentium/dashboard/install-user.sh`.

- [ ] **Step 2: Verify effective bind and service state**

Run on Pentium:
```bash
systemctl --user show atlas-dashboard.service -p ActiveState -p SubState -p NRestarts
ss -ltnp | grep '192.168.88.3:8765'
systemctl --user is-enabled atlas-voice.service || true
systemctl --user is-active atlas-voice.service || true
```
Expected: dashboard `active/running`, listener only `192.168.88.3:8765`, voice `disabled/inactive`.

- [ ] **Step 3: Validate from x99 over LAN**

Run on x99:
```powershell
Invoke-WebRequest http://192.168.88.3:8765/healthz -UseBasicParsing
Invoke-RestMethod http://192.168.88.3:8765/api/status
Invoke-RestMethod http://192.168.88.3:8765/api/events
```
Expected: HTTP 200, bounded payloads, current technical state visible, no Tailscale dependency.

- [ ] **Step 4: Prove write methods are denied from x99**

Send POST/PUT/DELETE to a representative endpoint and assert HTTP 405; do not send any operational command body.

- [ ] **Step 5: Open dashboard in x99 browser and visually validate**

Open `http://192.168.88.3:8765` and verify cards update every 2 s, USB microphone zero-signal/degraded state is understandable, pipeline is visible, and no controls/buttons can mutate Atlas.

---

### Task 9: GitHub PR, CI and checkpoint

**Files:**
- Repository changes only if CI reveals a confirmed defect.

**Interfaces:**
- Consumes: physically validated exact SHA.
- Produces: PR/checkpoint evidence for the dashboard slice.

- [ ] **Step 1: Open/update the dashboard PR against the current voice branch base**

PR title suggestion:
```text
feat(atlas): dashboard de observabilidade via LAN
```
Body must state explicitly that the dashboard is read-only, bound only to `192.168.88.3:8765`, and leaves voice disabled.

- [ ] **Step 2: Inspect CI for the exact head SHA**

Require the relevant workflow(s) to complete GREEN on the same SHA deployed physically. If any workflow fails, inspect the failing job/step/log marker before changing code.

- [ ] **Step 3: Post `/checkpoint`-style evidence to the PR**

Include:
- exact SHA;
- dashboard tests/regression counts;
- CI run ID and conclusion;
- deployment checksum;
- Pentium bind/service evidence;
- x99 LAN GET/405 evidence;
- confirmation that `atlas-voice.service` remained `disabled/inactive`;
- known blockers/degraded cards such as USB microphone signal zero, if still current.

- [ ] **Step 4: Final acceptance gate**

Do not call the dashboard complete unless repository tests, exact-SHA CI, physical deploy, LAN access, read-only proof and voice-paused proof are all satisfied on the same authoritative SHA.
