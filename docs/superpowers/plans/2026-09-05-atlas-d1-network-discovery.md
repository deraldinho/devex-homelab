# Atlas D1 Network Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar descoberta IPv4/ARP bounded na interface `WIFI_OBSERVED` do Pentium e integrá-la minimamente ao `ObservationRuntime` existente.

**Architecture:** Um adaptador Linux deriva a rede IPv4 real da interface configurada com `ip -json -4 addr`, executa um único `arp-scan` restrito àquela interface e CIDR, normaliza respostas e entrega um snapshot bounded. Um `WifiPresenceSource` mantém apenas a janela efêmera necessária para D1 e produz `SourceSnapshot`; persistência e identidade durável ficam para D2.

**Tech Stack:** Python stdlib, `iproute2`, `arp-scan`, `unittest`, Atlas `StimulusSource`/`SourceSnapshot`/`ObservationRuntime`.

**Spec:** `docs/superpowers/specs/2026-09-05-atlas-dual-zone-observation-design.md`

## Global Constraints

- Operar somente na interface Wi-Fi explicitamente configurada.
- Derivar e validar a sub-rede IPv4 diretamente conectada; nunca atravessar gateway ou outra interface.
- Um ciclo usa no máximo um processo `arp-scan`; nenhuma thread/fila própria permanente.
- Rejeitar redes com mais de 512 endereços e snapshots com mais de 256 dispositivos.
- `arp-scan` usa `--interface`, `--plain`, `--ignoredups`, `--retry=1` e CIDR explícito.
- Nenhum port scan, login, SSH, alteração de rede ou privilégio administrativo na zona `WIFI_OBSERVED`.
- Ausência em uma rodada não significa `missing`; D1 usa janela efêmera de 180 s.
- D2 continuará responsável por persistência de identidade, hostname/vendor enriquecido e eventos duráveis `appeared/changed/missing/recovered`.

---
### Task 1: Adaptador Linux de escopo e ARP scan

**Files:**
- Create: `infrastructure/pentium/atlas/network_discovery.py`
- Test: `infrastructure/pentium/atlas/tests/test_network_discovery.py`

**Interfaces:**
- Produces: `InterfaceNetwork`, `DiscoveredNeighbor`, `LinuxArpScanner.scan(interface) -> tuple[DiscoveredNeighbor, ...]`.
- `LinuxArpScanner` receives injectable `command_runner(argv, timeout_s)` for deterministic tests.

- [ ] **Step 1: escrever RED para interface/CIDR e bounds**

```python
def test_scanner_restricts_arp_scan_to_configured_interface_and_direct_cidr():
    runner = RecordingRunner(interface_json='[{"ifname":"wlan0","addr_info":[{"family":"inet","local":"192.168.1.8","prefixlen":24}]}]')
    LinuxArpScanner(runner=runner).scan("wlan0")
    assert runner.last_scan[-1] == "192.168.1.0/24"
    assert "--interface=wlan0" in runner.last_scan
```

Também testar interface sem IPv4, múltiplos IPv4 ambíguos, rede maior que 512 endereços e resposta fora do CIDR.

- [ ] **Step 2: executar somente o teste e observar RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_network_discovery -v`
Expected: erro de importação de `network_discovery`.

- [ ] **Step 3: implementar o mínimo GREEN**
```python
@dataclass(frozen=True)
class InterfaceNetwork:
    interface: str
    address: ipaddress.IPv4Address
    network: ipaddress.IPv4Network

@dataclass(frozen=True)
class DiscoveredNeighbor:
    mac: str
    ipv4: str

class LinuxArpScanner:
    def scan(self, interface: str) -> tuple[DiscoveredNeighbor, ...]: ...
```

O adaptador chama `ip -json -4 addr show dev <interface>` e depois `arp-scan --interface=<interface> --plain --ignoredups --retry=1 <cidr>`. O parser aceita somente IPv4 dentro do CIDR derivado, MAC unicast válida, deduplica `(mac, ipv4)` e aplica `max_devices=256`.

- [ ] **Step 4: executar GREEN e suíte Atlas**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_network_discovery -v`
Expected: PASS.

Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -v`
Expected: toda a suíte PASS.

- [ ] **Step 5: commit**

```bash
git add infrastructure/pentium/atlas/network_discovery.py infrastructure/pentium/atlas/tests/test_network_discovery.py
git commit -m "feat(atlas): adicionar descoberta arp D1"
```
### Task 2: Fonte de presença Wi-Fi bounded

**Files:**
- Modify: `infrastructure/pentium/atlas/stimulus_sources.py`
- Test: `infrastructure/pentium/atlas/tests/test_stimulus_sources.py`

**Interfaces:**
- Consumes: `LinuxArpScanner.scan(interface)`.
- Produces: `WifiPresenceSource.poll() -> SourceSnapshot` com payload estável e bounded.

- [ ] **Step 1: escrever RED para presença e janela**

```python
def test_wifi_presence_source_keeps_device_present_across_single_empty_round():
    scanner = SequenceScanner([neighbors("aa:bb:cc:dd:ee:01", "192.168.1.10"), ()])
    clock = SequenceClock([1000.0, 1060.0])
    source = WifiPresenceSource("wlan0", scanner=scanner, clock=clock, presence_window_s=180)
    assert source.poll().payload["devices"][0]["presence"] == "present"
    assert source.poll().payload["devices"][0]["presence"] == "present"
```

Também testar expiração após 180 s, ordenação determinística, `zone=WIFI_OBSERVED`, `first_seen` estável e limite de 256 dispositivos.

- [ ] **Step 2: executar RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_stimulus_sources.StimulusSourceTests -v`
Expected: falha por ausência de `WifiPresenceSource`.

- [ ] **Step 3: implementar o mínimo GREEN**
```python
class WifiPresenceSource:
    name = "wifi.presence"
    required = False

    def poll(self) -> SourceSnapshot: ...
```

O source mantém estado efêmero indexado por MAC, atualiza `last_seen`, preserva o dispositivo durante a janela de presença e remove somente após expiração. O payload contém lista ordenada de dispositivos com `mac`, `ipv4`, `first_seen`, `last_seen`, `presence`, `zone`; nenhum hostname/vendor é obrigatório em D1.

- [ ] **Step 4: executar GREEN e regressão**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_stimulus_sources -v`
Expected: PASS.

Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -v`
Expected: toda a suíte PASS.

- [ ] **Step 5: commit**

```bash
git add infrastructure/pentium/atlas/stimulus_sources.py infrastructure/pentium/atlas/tests/test_stimulus_sources.py
git commit -m "feat(atlas): integrar presença wifi D1"
```

### Task 3: Configuração, empacotamento e gate D1

**Files:**
- Modify: `infrastructure/pentium/atlas/observation_config.json`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `infrastructure/pentium/atlas/tests/test_observation_runtime.py`
- Modify: `infrastructure/pentium/atlas/tests/test_observation_packaging.py`
- Modify: `.github/workflows/foundation-ci.yml`

**Interfaces:**
- Consumes: source `wifi.presence` e `network_discovery.py`.
- Produces: schedule D1 no runtime, pacote instalável e gate CI explícito.

- [ ] **Step 1: escrever RED de configuração/packaging**
```python
def test_repository_observation_config_covers_wifi_presence_source():
    schedules = load_observation_config(config_path)
    assert schedules["wifi.presence"].interval_seconds == 60.0
    assert schedules["wifi.presence"].timeout_seconds <= 10.0
```

Packaging deve exigir `network_discovery.py` e o workflow deve executar `test_network_discovery.py` e emitir `DEVEX_HOMELAB_ATLAS_D1_DISCOVERY_PASS`.

- [ ] **Step 2: executar RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_observation_runtime infrastructure.pentium.atlas.tests.test_observation_packaging -v`
Expected: falhas porque `wifi.presence` e `network_discovery.py` ainda não estão no config/install/gate.

- [ ] **Step 3: implementar o mínimo GREEN**

Adicionar `wifi.presence` com `interval_seconds=60`, `timeout_seconds=10`, `max_backoff_seconds=300`, `cooldown_seconds=60`, `jitter_seconds=5`. Incluir `network_discovery.py` no instalador. Adicionar ao Foundation CI o teste D1 e o marcador de sucesso, sem executar scan físico em CI.

- [ ] **Step 4: verificação completa**

Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -v`
Expected: toda a suíte Atlas PASS.

Run: `git diff --check`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add infrastructure/pentium/atlas/observation_config.json infrastructure/pentium/atlas/install-user.sh infrastructure/pentium/atlas/tests/test_observation_runtime.py infrastructure/pentium/atlas/tests/test_observation_packaging.py .github/workflows/foundation-ci.yml
git commit -m "ci(atlas): certificar discovery D1"
```

### Task 4: Certificação lógica D1 e PR Draft

**Files:**
- No production code expected unless a verification exposes a defect.
- Add checkpoint only after exact-HEAD evidence exists.

- [ ] **Step 1: executar regressão completa relevante**

Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -v`
Expected: PASS.

Run: `git diff --check`
Expected: PASS.

- [ ] **Step 2: push e abrir PR Draft empilhada sobre a branch da especificação**

Head: `atlas/issue-20-d1-network-discovery`
Base: `atlas/issue-20-ssh-architecture`

- [ ] **Step 3: verificar CI no HEAD exato**

Foundation CI deve terminar `success` para o SHA da PR D1. Nenhum resultado de SHA anterior conta como certificação.

- [ ] **Step 4: checkpoint**

Registrar `/checkpoint` com RED observado, implementação, testes locais, CI do HEAD, blockers e próximo passo seguro `D2 — Identity & Presence Registry`.
### Task 1: Adaptador Linux de escopo e ARP scan

**Files:**
- Create: `infrastructure/pentium/atlas/network_discovery.py`
- Test: `infrastructure/pentium/atlas/tests/test_network_discovery.py`

**Interfaces:**
- Produces: `InterfaceNetwork`, `DiscoveredNeighbor`, `LinuxArpScanner.scan(interface) -> tuple[DiscoveredNeighbor, ...]`.
- `LinuxArpScanner` receives injectable `command_runner(argv, timeout_s)` for deterministic tests.

- [ ] **Step 1: escrever RED para interface/CIDR e bounds**

```python
def test_scanner_restricts_arp_scan_to_configured_interface_and_direct_cidr():
    runner = RecordingRunner(interface_json='[{"ifname":"wlan0","addr_info":[{"family":"inet","local":"192.168.1.8","prefixlen":24}]}]')
    LinuxArpScanner(runner=runner).scan("wlan0")
    assert runner.last_scan[-1] == "192.168.1.0/24"
    assert "--interface=wlan0" in runner.last_scan
```

Também testar interface sem IPv4, múltiplos IPv4 ambíguos, rede maior que 512 endereços e resposta fora do CIDR.

- [ ] **Step 2: executar somente o teste e observar RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_network_discovery -v`
Expected: erro de importação de `network_discovery`.

- [ ] **Step 3: implementar o mínimo GREEN**
Implementar parsing estrito de `ip -json -4 addr show dev <interface>` com `ipaddress.ip_network(..., strict=False)`. Executar `arp-scan` por argv fixo e timeout explícito; parsear apenas linhas IPv4+MAC válidas, normalizar MAC lowercase e rejeitar qualquer IP fora da rede derivada.

- [ ] **Step 4: verificar GREEN e regressão local**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_network_discovery -v`
Expected: PASS.

Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -p "test_*.py" -v`
Expected: suíte Atlas completa PASS.

- [ ] **Step 5: commit**

```bash
git add infrastructure/pentium/atlas/network_discovery.py infrastructure/pentium/atlas/tests/test_network_discovery.py
git commit -m "feat(atlas): adicionar descoberta arp bounded D1"
```

### Task 2: Fonte Wi-Fi e janela efêmera de presença

**Files:**
- Modify: `infrastructure/pentium/atlas/stimulus_sources.py`
- Test: `infrastructure/pentium/atlas/tests/test_stimulus_sources.py`

**Interfaces:**
- Consumes: `LinuxArpScanner.scan(interface)` e `DiscoveredNeighbor`.
- Produces: `WifiPresenceSource(scanner, interface, clock, presence_window_s=180, max_devices=256)`.

- [ ] **Step 1: escrever RED para snapshot e ausência transitória**

```python
def test_wifi_presence_source_keeps_device_present_during_one_empty_round():
    scanner = SequenceScanner([[neighbor("aa:bb:cc:dd:ee:ff", "192.168.1.20")], []])
    source = WifiPresenceSource(scanner, "wlan0", clock=SequenceClock([100.0, 120.0]), presence_window_s=180)
    first = source.poll()
    second = source.poll()
    self.assertEqual(first.payload["device_count"], 1)
    self.assertEqual(second.payload["device_count"], 1)
```

Testar ordenação determinística por MAC/IP, limite de 256 dispositivos, `zone=WIFI_OBSERVED`, e expiração somente após 180 s.
- [ ] **Step 2: executar o teste e observar RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_stimulus_sources -v`
Expected: falha porque `WifiPresenceSource` ainda não existe.

- [ ] **Step 3: implementar o mínimo GREEN**

Manter estado efêmero `mac -> {ipv4, first_seen, last_seen}` dentro da fonte. Cada `poll()` atualiza vistos, conserva ausentes dentro da janela e remove expirados. O payload contém somente `zone`, `interface`, `device_count` e `devices` ordenados, sem hostname/vendor persistente nesta slice.

- [ ] **Step 4: verificar GREEN e regressão**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_stimulus_sources -v`
Expected: PASS.

Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -p "test_*.py" -v`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add infrastructure/pentium/atlas/stimulus_sources.py infrastructure/pentium/atlas/tests/test_stimulus_sources.py
git commit -m "feat(atlas): integrar presença wifi ao runtime D1"
```

### Task 3: Configuração, packaging e gate D1

**Files:**
- Modify: `infrastructure/pentium/atlas/observation_config.json`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `infrastructure/pentium/atlas/tests/test_observation_runtime.py`
- Modify: `infrastructure/pentium/atlas/tests/test_observation_packaging.py`

**Interfaces:**
- Adds source schedule `wifi.observed` com intervalo 60 s, timeout 10 s, max backoff 240 s, cooldown 60 s e jitter 5 s.
- Packaging must include `network_discovery.py` without enabling or modifying network services.
- [ ] **Step 1: escrever RED para config/packaging**

Atualizar primeiro os testes para exigir `wifi.observed` no config e `network_discovery.py` no instalador.

- [ ] **Step 2: executar e observar RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_observation_runtime infrastructure.pentium.atlas.tests.test_observation_packaging -v`
Expected: FAIL por source/config e arquivo de packaging ausentes.

- [ ] **Step 3: implementar o mínimo GREEN**

Adicionar `wifi.observed` ao JSON e incluir `network_discovery.py` no pacote do Atlas. Não criar serviço, alterar interface, rota, firewall, NetworkManager ou Tailscale.

- [ ] **Step 4: certificar a slice localmente**

Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -p "test_*.py" -v`
Expected: PASS.

Run: `git diff --check`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add infrastructure/pentium/atlas/observation_config.json infrastructure/pentium/atlas/install-user.sh infrastructure/pentium/atlas/tests/test_observation_runtime.py infrastructure/pentium/atlas/tests/test_observation_packaging.py
git commit -m "test(atlas): certificar configuracao D1"
```

### Task 4: PR Draft e checkpoint D1

**Files:**
- No production files beyond Tasks 1–3.

- [ ] Push branch de implementação e abrir PR Draft baseada em `atlas/issue-20-ssh-architecture`.
- [ ] Verificar CI no HEAD exato; não reutilizar resultado de SHA anterior.
- [ ] Se algum gate estiver RED/pending, parar e corrigir antes de avançar.
- [ ] Quando GREEN, publicar `/checkpoint` com implementação, RED/GREEN observado, testes, CI do HEAD e limites preservados.
- [ ] Não executar certificação física ARP no Pentium até o código e CI estarem GREEN; a certificação física é o próximo gate controlado da própria D1.

## Self-review

- Cobertura da spec D1: escopo de interface/CIDR, ARP bounded, deduplicação via snapshot/runtime, janela de presença, bounds, integração mínima e packaging estão mapeados nas Tasks 1–3.
- D2 não foi antecipada: não há persistência durável, OUI/hostname enrichment nem máquina durável de eventos.
- M1/M2 não foram antecipadas: nenhum SSH novo ou CONTROL entra em D1.
- APIs e nomes usados nas tarefas são definidos neste plano.
