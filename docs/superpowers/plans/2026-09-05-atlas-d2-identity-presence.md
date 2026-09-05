# Atlas D2 Identity & Presence Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persistir identidade estável dos dispositivos `WIFI_OBSERVED`, correlacionar mudanças sem duplicação por troca de IP e produzir eventos bounded `appeared`, `changed`, `missing` e `recovered`.

**Architecture:** `PresenceRegistry` será a única fonte de verdade da identidade/presença D2, indexada por MAC normalizado. `WifiPresenceSource` deixa de manter estado efêmero próprio e delega a correlação ao registry, que usa persistência JSON atômica/versionada e retorna uma projeção reduzida para `SourceSnapshot`.

**Tech Stack:** Python stdlib, `dataclasses`, JSON atômico, `unittest`, Atlas `WifiPresenceSource`/`SourceSnapshot`/`ObservationRuntime`.

**Spec:** `docs/superpowers/specs/2026-09-05-atlas-dual-zone-observation-design.md`

## Global Constraints

- MAC é a chave estável D2; mudança de IPv4 nunca cria nova entidade.
- `hostname` e `vendor` são pistas opcionais e nunca identidade criptográfica.
- Uma ausência isolada não gera `missing`; somente expiração da janela configurada.
- Falha de discovery não chama o registry e não marca todos os dispositivos como ausentes.
- Registry limitado a 256 dispositivos e eventos por ciclo limitados ao mesmo bound.
- Persistência usa schema versionado, escrita atômica e nenhum secret.
- `WIFI_OBSERVED` continua sem port scan, login, SSH ou promoção automática para `MANAGED`.

---### Task 1: Registry de identidade e transições de presença

**Files:**
- Create: `infrastructure/pentium/atlas/presence_registry.py`
- Test: `infrastructure/pentium/atlas/tests/test_presence_registry.py`

**Interfaces:**
- Produces: `PresenceDevice`, `PresenceEvent`, `PresenceUpdate`.
- Produces: `PresenceRegistry.observe(neighbors, observed_at) -> PresenceUpdate`.
- Consumes: objetos com `mac`, `ipv4` e opcionais `hostname`, `vendor`.

- [ ] **Step 1: escrever RED para identidade estável e eventos**

```python
def test_same_mac_new_ip_is_changed_not_new_entity():
    registry = PresenceRegistry(presence_window_s=180, max_devices=256)
    registry.observe([neighbor("aa:bb:cc:dd:ee:01", "192.168.1.10")], 1000.0)
    update = registry.observe([neighbor("aa:bb:cc:dd:ee:01", "192.168.1.20")], 1060.0)
    assert len(update.devices) == 1
    assert [(e.kind, e.mac) for e in update.events] == [("changed", "aa:bb:cc:dd:ee:01")]
```

Também cobrir `appeared`, ausência única sem evento, `missing` após 180 s, `recovered`, metadata opcional e bound de 256.

- [ ] **Step 2: executar RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_presence_registry -v`
Expected: falha de importação de `presence_registry`.
- [ ] **Step 3: implementar o mínimo GREEN**

```python
@dataclass(frozen=True)
class PresenceEvent:
    kind: str
    mac: str

class PresenceRegistry:
    def observe(self, neighbors, observed_at: float) -> PresenceUpdate: ...
```

O registry preserva `first_seen`, atualiza `last_seen`, mantém registros `present|missing`, emite eventos ordenados deterministicamente e nunca remove a identidade apenas porque o host ficou `missing`.

- [ ] **Step 4: verificar GREEN e regressão**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_presence_registry -v`
Expected: PASS.

Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -p "test_*.py" -q`
Expected: toda a suíte PASS.

- [ ] **Step 5: commit**

```bash
git add infrastructure/pentium/atlas/presence_registry.py infrastructure/pentium/atlas/tests/test_presence_registry.py
git commit -m "feat(atlas): adicionar registry de identidade D2"
```

### Task 2: Persistência atômica do registry

**Files:**
- Create: `infrastructure/pentium/atlas/presence_persistence.py`
- Test: `infrastructure/pentium/atlas/tests/test_presence_persistence.py`
**Interfaces:**
- Produces: `PresenceRepository(path, max_devices)` com `save(registry)` e `load(*, presence_window_s) -> PresenceRegistry | None`.
- Persisted schema: `schema_version=1`, `devices=[...]`; ordem estável por MAC.

- [ ] **Step 1: escrever RED para round-trip e corrupção**

```python
def test_repository_round_trip_preserves_missing_state(tmp_path):
    repo = PresenceRepository(tmp_path / "presence.json", max_devices=256)
    registry = PresenceRegistry(presence_window_s=180, max_devices=256)
    registry.observe([neighbor("aa:bb:cc:dd:ee:01", "192.168.1.10")], 1000.0)
    registry.observe([], 1181.0)
    repo.save(registry)
    restored = repo.load()
    assert restored.devices()[0].presence == "missing"
```

Também testar ausência do arquivo, schema inválido, mais de 256 registros e arquivo temporário não remanescente.

- [ ] **Step 2: executar RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_presence_persistence -v`
Expected: falha de importação de `presence_persistence`.

- [ ] **Step 3: implementar escrita atômica e restore estrito**

Usar `json.dump(..., sort_keys=True)`, `flush`, `os.fsync`, `os.replace` e fsync do diretório em POSIX. Dados inválidos levantam `PresenceStateInvalid`; ausência retorna `None`.

- [ ] **Step 4: executar GREEN + suíte**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_presence_persistence -v`
Expected: PASS.

Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -p "test_*.py" -q`
Expected: PASS.
- [ ] **Step 5: commit**

```bash
git add infrastructure/pentium/atlas/presence_persistence.py infrastructure/pentium/atlas/tests/test_presence_persistence.py
git commit -m "feat(atlas): persistir registry de presença D2"
```

### Task 3: Integrar D2 ao WifiPresenceSource

**Files:**
- Modify: `infrastructure/pentium/atlas/stimulus_sources.py`
- Modify: `infrastructure/pentium/atlas/tests/test_stimulus_sources.py`

**Interfaces:**
- `WifiPresenceSource` recebe `registry` opcional; quando ausente cria registry efêmero compatível com D1.
- `poll()` publica `devices` persistentes e `events` D2; fingerprint ignora `last_seen` e inclui somente identidade/presença/eventos relevantes.

- [ ] **Step 1: escrever RED de integração**

```python
def test_wifi_presence_source_emits_recovered_after_missing():
    registry = PresenceRegistry(presence_window_s=180, max_devices=256)
    scanner = SequenceScanner([(neighbor(...),), (), (neighbor(...),)])
    source = WifiPresenceSource("wlan0", scanner=scanner, registry=registry,
                                clock=SequenceClock([1000.0, 1181.0, 1240.0]))
    source.poll()
    assert source.poll().payload["events"][0]["kind"] == "missing"
    assert source.poll().payload["events"][0]["kind"] == "recovered"
```

Também manter compatibilidade dos testes D1 e verificar que troca de IP gera `changed` sem duplicação.
- [ ] **Step 2: executar RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_stimulus_sources -v`
Expected: falha porque `WifiPresenceSource` ainda não delega ao registry nem expõe eventos D2.

- [ ] **Step 3: implementar o mínimo GREEN**

Remover `_WifiPresenceRecord` e `_devices` privados de `WifiPresenceSource`. Delegar cada scan bem-sucedido ao registry e serializar `PresenceUpdate` para payload reduzido. Exceções do scanner continuam propagando antes de qualquer `observe()`.

- [ ] **Step 4: executar GREEN + regressão**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_stimulus_sources -v`
Expected: PASS.

Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -p "test_*.py" -q`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add infrastructure/pentium/atlas/stimulus_sources.py infrastructure/pentium/atlas/tests/test_stimulus_sources.py
git commit -m "feat(atlas): integrar eventos de presença D2"
```

### Task 4: Packaging, CI e certificação lógica D2

**Files:**
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `infrastructure/pentium/atlas/tests/test_observation_packaging.py`
- Modify: `.github/workflows/foundation-ci.yml`
- Modify: `docs/as-built/` somente após evidência real.
**Interfaces:**
- Installer inclui `presence_registry.py` e `presence_persistence.py`.
- Foundation CI executa testes D2 e emite `DEVEX_HOMELAB_ATLAS_D2_IDENTITY_PRESENCE_PASS`.

- [ ] **Step 1: escrever RED de packaging/gate**

Adicionar asserts no teste de packaging para os dois módulos D2 e para o marcador dedicado do workflow.

- [ ] **Step 2: executar RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_observation_packaging -v`
Expected: falha por módulos/gate ausentes.

- [ ] **Step 3: atualizar installer e Foundation CI**

Adicionar ambos os módulos à cópia e `py_compile`; adicionar os testes D2 ao gate Atlas sem executar rede física.

- [ ] **Step 4: verificação local final**

Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -p "test_*.py" -q`
Expected: toda a suíte PASS.

Run: `python -m py_compile infrastructure/pentium/atlas/presence_registry.py infrastructure/pentium/atlas/presence_persistence.py infrastructure/pentium/atlas/stimulus_sources.py`
Expected: PASS.

Run: `bash -n infrastructure/pentium/atlas/install-user.sh`
Expected: PASS.

Run: `git diff --check`
Expected: PASS.
- [ ] **Step 5: commit e push**

```bash
git add infrastructure/pentium/atlas/install-user.sh infrastructure/pentium/atlas/tests/test_observation_packaging.py .github/workflows/foundation-ci.yml
git commit -m "ci(atlas): certificar identity presence D2"
git push -u origin atlas/issue-20-d2-identity-presence
```

- [ ] **Step 6: abrir Draft PR empilhada sobre D1**

Head: `atlas/issue-20-d2-identity-presence`
Base: `atlas/issue-20-d1-network-discovery`

A PR só recebe checkpoint de conclusão depois de Foundation CI GREEN no HEAD exato. A certificação física continua controlada no Pentium; ausência de acesso físico/SSH não autoriza inventar evidência.

## Self-review

- Spec coverage: identidade por MAC, IP mutável, metadata opcional, persistência, quatro eventos e bounds cobertos.
- Falha de discovery permanece fora do registry porque `scan()` ocorre antes de `observe()`.
- D2 não promove entidade para `ENROLLED`/`MANAGED` e não introduz SSH.
- Não há placeholders de implementação nem dependências externas novas.
