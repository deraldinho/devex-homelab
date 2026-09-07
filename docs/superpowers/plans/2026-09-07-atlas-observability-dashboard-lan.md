# Atlas Observability Dashboard LAN Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar um dashboard web read-only do Atlas no Pentium, acessível pelo x99 pela LAN em `http://192.168.88.3:8765`, sem CONTROL, shell, SSH ou mutação.

**Architecture:** Um serviço Python stdlib (`atlas-dashboard.service`) coleta estado bounded de arquivos locais, systemd, `/proc`, `/sys`, ALSA e journal sanitizado; expõe somente endpoints GET e serve uma UI estática dark que atualiza a cada 2 segundos. O bind é exclusivo em `192.168.88.3:8765` e a voz continua pausada.

**Tech Stack:** Python 3 stdlib (`http.server`, `json`, `subprocess`, `pathlib`), HTML/CSS/JS sem CDN, systemd user service, unittest.

**Spec:** `docs/superpowers/specs/2026-09-07-atlas-observability-dashboard-lan-design.md`

## Global Constraints

- Pentium LAN: `192.168.88.3/24`; x99 LAN: `192.168.88.4/24`.
- Bind obrigatório: `192.168.88.3:8765`; proibido `0.0.0.0`.
- Endpoints permitidos: `GET /`, `GET /api/status`, `GET /api/events`, `GET /healthz`.
- Métodos diferentes de GET retornam `405 Method Not Allowed`.
- Sem CONTROL, `ManagedControlService`, SSH dispatcher, shell recebido por HTTP, restart, upload ou escrita de configuração.
- Não persistir áudio bruto nem expor transcrições.
- Cada coletor possui timeout e tamanho de saída bounded; campos desconhecidos retornam `null`/`unknown`.
- `atlas-voice.service` permanece `disabled/inactive` durante instalação e certificação.

---

## File Structure

- `infrastructure/pentium/atlas/dashboard_collectors.py`: coleta bounded, parsing e sanitização do snapshot.
- `infrastructure/pentium/atlas/atlas_dashboard.py`: servidor HTTP GET-only e serialização JSON.
- `infrastructure/pentium/atlas/dashboard.html`: UI estática responsiva.
- `infrastructure/pentium/atlas/config_dashboard.json`: bind, porta, limites e caminhos permitidos.
- `infrastructure/pentium/atlas/atlas-dashboard.service`: unit systemd user.
- `infrastructure/pentium/atlas/install-user.sh`: packaging, py_compile, unit install e enable sem tocar na voz.
- `infrastructure/pentium/atlas/tests/test_dashboard_collectors.py`: contratos dos coletores.
- `infrastructure/pentium/atlas/tests/test_atlas_dashboard_http.py`: roteamento HTTP e métodos negados.
- `infrastructure/pentium/atlas/tests/test_dashboard_security.py`: ausência de superfícies CONTROL/SSH/write.
- `infrastructure/pentium/atlas/tests/test_dashboard_packaging.py`: config, installer e service unit.

### Task 1: Bounded Collectors and Sanitized Status Model

**Files:**
- Create: `infrastructure/pentium/atlas/dashboard_collectors.py`
- Create: `infrastructure/pentium/atlas/tests/test_dashboard_collectors.py`

**Interfaces:**
- Produces: `CommandResult`, `run_command(argv, timeout_s, max_output_bytes)`, `collect_status(config, *, command_runner=run_command) -> dict`, `collect_events(config, *, command_runner=run_command) -> list[dict]`.
- Produces stable groups: `atlas`, `services`, `voice`, `audio`, `anc`, `system`, `network`.

- [ ] **Step 1: Write failing collector tests**

```python
def test_collect_status_returns_stable_groups_without_transcripts(tmp_path):
    health = tmp_path / "latest.json"
    health.write_text('{"status":"healthy","checks":{},"metrics":{}}')
    cfg = make_config(health_path=str(health))
    status = collect_status(cfg, command_runner=fake_runner)
    assert set(status) == {"atlas","services","voice","audio","anc","system","network"}
    assert "transcript" not in json.dumps(status).lower()

def test_collect_events_keeps_only_allowlisted_voice_markers():
    events = collect_events(make_config(), command_runner=fake_journal_runner)
    assert all(e["marker"].startswith("ATLAS_V1_") for e in events)
    assert all("user said" not in json.dumps(e).lower() for e in events)
```

- [ ] **Step 2: Run RED**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_dashboard_collectors -v`
Expected: FAIL because `dashboard_collectors` does not exist.
- [ ] **Step 3: Implement minimal bounded collectors**

```python
@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

def run_command(argv: list[str], timeout_s: float, max_output_bytes: int = 16384) -> CommandResult:
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s, check=False)
    return CommandResult(p.returncode, p.stdout[:max_output_bytes], p.stderr[:max_output_bytes])

def collect_status(config: dict, *, command_runner=run_command) -> dict:
    return {
        "atlas": collect_atlas(config),
        "services": collect_services(config, command_runner),
        "voice": collect_voice(config, command_runner),
        "audio": collect_audio(config, command_runner),
        "anc": collect_anc(config),
        "system": collect_system(config),
        "network": collect_network(config),
    }
```

Collector rules: read `health/latest.json` bounded to 64 KiB; `systemctl --user show`/`is-active` with 2 s timeout; `/proc/meminfo`, `/proc/uptime`, `shutil.disk_usage`; `/proc/asound/cards` plus `arecord -l`; sanitize config to explicit allowlist only; journal command fixed to `journalctl --user -u atlas-voice.service -n 40 --no-pager -o cat` and accept only `ATLAS_V1_*` technical markers.

- [ ] **Step 4: Run GREEN**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_dashboard_collectors -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git add infrastructure/pentium/atlas/dashboard_collectors.py infrastructure/pentium/atlas/tests/test_dashboard_collectors.py && git commit -m "feat(atlas): coletar observabilidade bounded"`

### Task 2: GET-only HTTP API

**Files:**
- Create: `infrastructure/pentium/atlas/atlas_dashboard.py`
- Create: `infrastructure/pentium/atlas/tests/test_atlas_dashboard_http.py`

**Interfaces:**
- Consumes: `collect_status`, `collect_events`.
- Produces: `DashboardRequestHandler`, `build_server(config_path: Path) -> HTTPServer`, `main() -> int`.

- [ ] **Step 1: Write failing HTTP contract tests**

```python
def test_get_status_returns_json(handler_client):
    response = handler_client.get("/api/status")
    assert response.status == 200
    assert response.headers["Content-Type"].startswith("application/json")

def test_write_methods_are_rejected(handler_client):
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        response = handler_client.request(method, "/api/status")
        assert response.status == 405

def test_unknown_route_is_404(handler_client):
    assert handler_client.get("/shell").status == 404
```

- [ ] **Step 2: Run RED**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_atlas_dashboard_http -v`
Expected: FAIL because `atlas_dashboard` does not exist.

- [ ] **Step 3: Implement GET-only router and bounded JSON**

```python
class DashboardRequestHandler(BaseHTTPRequestHandler):
    MAX_RESPONSE_BYTES = 131072
    def do_GET(self):
        if self.path == "/": return self._serve_html()
        if self.path == "/api/status": return self._serve_json(self.server.collect_status())
        if self.path == "/api/events": return self._serve_json(self.server.collect_events())
        if self.path == "/healthz": return self._serve_json({"status": "ok"})
        self.send_error(404)
    def do_POST(self): self.send_error(405)
    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST
```

`build_server()` must read `bind_host`/`port` from config, reject `0.0.0.0`, `::`, empty host and ports outside `1024..65535`, then construct `HTTPServer((host, port), DashboardRequestHandler)`.

- [ ] **Step 4: Run GREEN**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_atlas_dashboard_http -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git add infrastructure/pentium/atlas/atlas_dashboard.py infrastructure/pentium/atlas/tests/test_atlas_dashboard_http.py && git commit -m "feat(atlas): expor dashboard http somente leitura"`

### Task 3: Static Dashboard UI

**Files:**
- Create: `infrastructure/pentium/atlas/dashboard.html`
- Modify: `infrastructure/pentium/atlas/tests/test_atlas_dashboard_http.py`

**Interfaces:**
- Consumes: `/api/status`, `/api/events`.
- Produces: one self-contained HTML page with no external network dependency.

- [ ] **Step 1: Write failing UI delivery test**

```python
def test_root_serves_self_contained_dashboard(handler_client):
    response = handler_client.get("/")
    body = response.text
    assert response.status == 200
    assert "Atlas Observability" in body
    assert "/api/status" in body
    assert "setInterval" in body
    assert "https://" not in body and "http://" not in body
    assert "MIC" in body and "ANC" in body and "Whisper" in body and "Qwen" in body
```

- [ ] **Step 2: Run RED**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_atlas_dashboard_http -v`
Expected: FAIL because `dashboard.html` is absent/not served.

- [ ] **Step 3: Implement UI**
Create semantic cards for Atlas summary, pipeline, services, audio, ANC, system/network and timeline. Use inline CSS variables and vanilla JS only. Poll both APIs every 2000 ms with `Promise.allSettled`; update each card independently and render textual states `GREEN`, `YELLOW`, `RED`, `PAUSED`, `UNKNOWN`. Never render a transcript field even if an unexpected backend field appears.

```javascript
async function refresh() {
  const [status, events] = await Promise.allSettled([
    fetch('/api/status', {cache:'no-store'}).then(r => r.json()),
    fetch('/api/events', {cache:'no-store'}).then(r => r.json())
  ]);
  if (status.status === 'fulfilled') renderStatus(status.value);
  else markStatusSourceDegraded();
  if (events.status === 'fulfilled') renderEvents(events.value);
  else markEventsSourceDegraded();
}
refresh();
setInterval(refresh, 2000);
```

- [ ] **Step 4: Run GREEN**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_atlas_dashboard_http -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git add infrastructure/pentium/atlas/dashboard.html infrastructure/pentium/atlas/tests/test_atlas_dashboard_http.py && git commit -m "feat(atlas): adicionar interface web de observabilidade"`

### Task 4: Configuration, systemd and Installer Packaging

**Files:**
- Create: `infrastructure/pentium/atlas/config_dashboard.json`
- Create: `infrastructure/pentium/atlas/atlas-dashboard.service`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Create: `infrastructure/pentium/atlas/tests/test_dashboard_packaging.py`

**Interfaces:**
- Produces config schema version 1 with `bind_host`, `port`, `health_path`, `deploy_sha_path`, `dashboard_html`, command timeouts and output limits.
- Produces user service `atlas-dashboard.service` using `python3 -m atlas.atlas_dashboard`.

- [ ] **Step 1: Write failing packaging tests**

```python
def test_dashboard_config_binds_only_lan():
    cfg = json.loads((ATLAS / "config_dashboard.json").read_text())
    assert cfg["bind_host"] == "192.168.88.3"
    assert cfg["port"] == 8765
    assert cfg["bind_host"] not in {"0.0.0.0", "::", ""}

def test_installer_packages_dashboard_without_enabling_voice():
    text = (ATLAS / "install-user.sh").read_text()
    assert "atlas_dashboard.py" in text and "dashboard_collectors.py" in text
    assert "atlas-dashboard.service" in text
    assert "enable --now atlas-dashboard.service" in text
    assert "enable atlas-voice.service" not in dashboard_install_section(text)
```

- [ ] **Step 2: Run RED**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_dashboard_packaging -v`
Expected: FAIL because config/unit/packaging do not exist.

- [ ] **Step 3: Implement config, hardened unit and installer changes**
Use this unit shape:

```ini
[Unit]
Description=Atlas read-only observability dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/pentium-agent
ExecStart=/usr/bin/python3 -m atlas.atlas_dashboard
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only

[Install]
WantedBy=default.target
```

Installer additions: copy both Python modules and HTML; copy/validate `config_dashboard.json`; `py_compile` dashboard modules; install unit to `%h/.config/systemd/user`; `daemon-reload`; `enable --now atlas-dashboard.service`. Do not run `enable`, `start` or `restart` for `atlas-voice.service` in the dashboard installation path.

- [ ] **Step 4: Run packaging validation**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_dashboard_packaging -v && bash -n infrastructure/pentium/atlas/install-user.sh && python -m json.tool infrastructure/pentium/atlas/config_dashboard.json >/dev/null`
Expected: PASS.

- [ ] **Step 5: Commit**
`git add infrastructure/pentium/atlas/config_dashboard.json infrastructure/pentium/atlas/atlas-dashboard.service infrastructure/pentium/atlas/install-user.sh infrastructure/pentium/atlas/tests/test_dashboard_packaging.py && git commit -m "feat(atlas): empacotar dashboard de observabilidade"`

### Task 5: Negative Security Gates

**Files:**
- Create: `infrastructure/pentium/atlas/tests/test_dashboard_security.py`
- Modify only if a gate exposes a violation: dashboard files from Tasks 1–4.

**Interfaces:**
- Certifies dashboard cannot dispatch CONTROL/SSH/write actions and never binds wildcard interfaces.

- [ ] **Step 1: Write security tests**

```python
def test_dashboard_has_no_control_or_ssh_dispatcher():
    source = dashboard_sources().lower()
    for forbidden in ("managedcontrolservice", "managed_control", "ssh_transport", "reboot_host", "restart_service"):
        assert forbidden not in source

def test_http_surface_contains_no_write_route():
    source = (ATLAS / "atlas_dashboard.py").read_text().lower()
    assert "do_post" in source and "send_error(405)" in source
    for route in ("/control", "/shell", "/ssh", "/restart", "/upload"):
        assert route not in source
```

- [ ] **Step 2: Run RED/GREEN security gate**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_dashboard_security -v`
Expected: PASS only if Tasks 1–4 expose no forbidden surface. If it fails, fix only the violating dashboard code and rerun.

- [ ] **Step 3: Add wildcard-bind and transcript leakage gates**

```python
def test_dashboard_config_rejects_wildcard_bind():
    with self.assertRaises(ValueError):
        validate_config({**valid_config(), "bind_host": "0.0.0.0"})

def test_status_and_events_never_serialize_transcript_keys():
    payload = json.dumps({"status": collect_status(valid_config(), command_runner=fake_runner),
                          "events": collect_events(valid_config(), command_runner=fake_runner)}).lower()
    assert "transcript" not in payload
```

- [ ] **Step 4: Run whole security-focused set**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_dashboard_collectors infrastructure.pentium.atlas.tests.test_atlas_dashboard_http infrastructure.pentium.atlas.tests.test_dashboard_security infrastructure.pentium.atlas.tests.test_dashboard_packaging -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git add infrastructure/pentium/atlas/tests/test_dashboard_security.py infrastructure/pentium/atlas && git commit -m "test(atlas): certificar isolamento do dashboard"`

### Task 6: Regression, Exact-SHA Deploy and LAN Certification

**Files:**
- Modify only if verification reveals defects.
- Update PR checkpoint after evidence is complete.

**Interfaces:**
- Produces final exact SHA, deploy archive checksum, live service evidence and x99 LAN access proof.

- [ ] **Step 1: Run complete local regression**
Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -v`
Expected: all Atlas tests GREEN.
Run additionally: `python -m py_compile infrastructure/pentium/atlas/*.py && bash -n infrastructure/pentium/atlas/install-user.sh && git diff --check`
Expected: all exit 0.

- [ ] **Step 2: Verify branch cleanliness and commit final fixes if any**
Run: `git status --short && git rev-parse HEAD`
Expected: clean worktree and one exact HEAD SHA.

- [ ] **Step 3: Push exact HEAD and require CI GREEN**
Run: `git push -u origin atlas/issue-20-observability-dashboard`
Then verify Foundation CI belongs to that exact SHA and concludes `success`; do not certify with a run from an ancestor SHA.

- [ ] **Step 4: Build deterministic deploy archive and verify checksum**
Create the archive from the exact committed HEAD, copy it to `~/pentium-agent/runtime/deploy/`, calculate SHA256 locally and remotely, and require exact equality before extraction. Extract into a stage directory, run `infrastructure/pentium/atlas/install-user.sh`, then write the exact Git SHA to `~/pentium-agent/runtime/deploy/ATLAS_DASHBOARD_DEPLOY_SHA`.

- [ ] **Step 5: Verify physical service and bind on Pentium**
Run on Pentium:

```bash
systemctl --user is-enabled atlas-dashboard.service
systemctl --user is-active atlas-dashboard.service
systemctl --user show atlas-dashboard.service -p NRestarts --value
ss -ltnp | grep '192.168.88.3:8765'
systemctl --user is-enabled atlas-voice.service || true
systemctl --user is-active atlas-voice.service || true
```

Expected: dashboard `enabled/active`, `NRestarts=0`, listener exactly `192.168.88.3:8765`; voice remains `disabled/inactive`.

- [ ] **Step 6: Verify LAN access from x99**
Run on x99:

```powershell
Invoke-WebRequest http://192.168.88.3:8765/healthz -UseBasicParsing
Invoke-RestMethod http://192.168.88.3:8765/api/status
Invoke-RestMethod http://192.168.88.3:8765/api/events
(Invoke-WebRequest http://192.168.88.3:8765/ -UseBasicParsing).StatusCode
```

Expected: HTTP 200, bounded valid JSON, root HTML status 200. Verify `http://192.168.1.105:8765` and `http://100.107.230.78:8765` do not provide the dashboard because the server is not bound there.

- [ ] **Step 7: Verify negative HTTP methods physically**
From x99 send `POST`, `PUT`, `PATCH`, `DELETE` to `/api/status`; each must return HTTP 405. Confirm `/shell`, `/control`, `/ssh`, `/restart` return 404.

- [ ] **Step 8: Observe short runtime stability**
Sample service state, `NRestarts`, RSS and endpoint responsiveness three times across at least 60 seconds. Require no restart growth and no sustained unbounded RSS increase.

- [ ] **Step 9: Create/update PR and checkpoint**
PR base remains the dashboard branch's intended Atlas ancestor. Checkpoint must include: final SHA, CI run ID/conclusion, test count, deploy archive SHA256, exact bind, x99 LAN proof, negative-method proof, `voice=disabled/inactive`, and any remaining non-dashboard blocker such as the USB reference microphone signal issue.

## Final Certification Gate

The dashboard is complete only when the same exact final SHA is GREEN locally, GREEN in CI, deployed on Pentium with matching archive checksum, listening only on `192.168.88.3:8765`, reachable from x99 over `192.168.88.4/24`, read-only gates pass, and `atlas-voice.service` remains paused.
