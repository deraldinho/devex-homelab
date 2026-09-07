# Atlas C1 — Contexto Cognitivo bounded Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar C1 com `ContextoCognitivo` bounded, serialização auditável e `ActivationPolicy` determinística, sem qualquer inferência LLM ou side effect operacional.

**Architecture:** C1 recebe somente contratos já normalizados de Health/A1–A4/percepção/correlação. A política avalia primeiro o sinal de ativação; quando aprovada, o builder compõe um snapshot cognitivo reduzido usando o motivo aprovado, respeitando limites de listas, strings e bytes. C2 consumirá esse contrato posteriormente sem conhecer os detalhes de A1–A4.

**Tech Stack:** Python 3 stdlib, `dataclasses`, `enum`, `json`, `unittest`, GitHub Actions Foundation CI.

**Spec:** `docs/superpowers/specs/2026-09-05-atlas-cognitive-llm-reaction-loop-design.md`

## Global Constraints

- C1 não chama LLM, `llama.cpp`, rede, SSH, shell, subprocesso, logs brutos ou arquivos arbitrários.
- Estado técnico, percepção, correlação, estado afetivo, emoção e foco permanecem autoritativos em seus módulos atuais; C1 apenas reduz/compõe.
- A1–A4 permanecem autoritativas; D1/D2 permanecem válidas; A5 distribuída é histórica e A6 multiprotocolo continua cancelada.
- Todas as listas e strings do contexto têm limites explícitos; payload final possui limite de bytes e truncamento auditável.
- Interação humana é sempre um motivo cognitivo válido; orçamento/cooldown de C1 limita ativações autônomas, não impede uma nova interação humana explícita.
- Nenhum novo pacote Python externo será adicionado em C1.
- Toda mudança segue TDD RED → implementação mínima → GREEN → revisão → commit.
- Foundation CI precisa estar GREEN no HEAD exato antes da promoção da slice.

---
## File map

- Create `infrastructure/pentium/atlas/modelo_contexto_cognitivo.py`: enums e dataclasses imutáveis do contrato cognitivo e da decisão de ativação.
- Create `infrastructure/pentium/atlas/configuracao_cognitiva.py`: leitura/validação tipada dos limites de C1.
- Create `infrastructure/pentium/atlas/config_cognitiva.json`: valores iniciais versionados e bounded.
- Create `infrastructure/pentium/atlas/contexto_cognitivo.py`: builder puro que reduz contratos autoritativos para `ContextoCognitivo`.
- Create `infrastructure/pentium/atlas/politica_ativacao_cognitiva.py`: cooldown, deduplicação e orçamento de ativações autônomas.
- Create `infrastructure/pentium/atlas/tests/test_modelo_contexto_cognitivo.py`.
- Create `infrastructure/pentium/atlas/tests/test_configuracao_cognitiva.py`.
- Create `infrastructure/pentium/atlas/tests/test_contexto_cognitivo.py`.
- Create `infrastructure/pentium/atlas/tests/test_politica_ativacao_cognitiva.py`.
- Create `infrastructure/pentium/atlas/tests/test_c1_contexto_cognitivo_empacotamento.py`.
- Modify `infrastructure/pentium/atlas/install-user.sh`: instalar/compilar C1 e emitir gate de instalação.
- Modify `.github/workflows/foundation-ci.yml`: compilar/validar C1 e emitir marker de CI.

### Valores iniciais versionados de `config_cognitiva.json`

```json
{
  "schema_version": 1,
  "contexto": {
    "max_string_chars": 256,
    "max_mudancas_recentes": 8,
    "max_dependencias_afetadas": 8,
    "max_nuances": 2,
    "max_payload_bytes": 8192
  },
  "ativacao": {
    "novidade_minima": 0.75,
    "delta_afetivo_minimo": 0.20,
    "cooldown_s": 120,
    "janela_orcamento_s": 300,
    "max_ativacoes_autonomas_janela": 4
  }
}
```

Os valores são configuração inicial da slice, não limites universais do produto. C5 poderá recalibrá-los somente com evidência física.

### Interfaces centrais

```python
class MotivoAtivacaoCognitiva(str, Enum):
    CRITICIDADE_TECNICA = "criticidade_tecnica"
    NOVIDADE_RELEVANTE = "novidade_relevante"
    MUDANCA_ESTADO = "mudanca_estado"
    MUDANCA_AFETIVA = "mudanca_afetiva"
    RECUPERACAO_IMPORTANTE = "recuperacao_importante"
    EXPECTATIVA_QUEBRADA = "expectativa_quebrada"
    INTERACAO_HUMANA = "interacao_humana"
    REFLEXAO_PERIODICA = "reflexao_periodica"
```

```python
@dataclass(frozen=True)
class DecisaoAtivacaoCognitiva:
    ativar: bool
    motivo: MotivoAtivacaoCognitiva | None
    razao_bloqueio: str | None = None
```
```python
@dataclass(frozen=True)
class ContextoCognitivo:
    versao_schema: int
    timestamp: str
    motivo_ativacao: MotivoAtivacaoCognitiva
    entidade_principal: str
    estado_tecnico: str
    estado_percepcao: str
    incidente_principal: dict[str, object] | None
    estado_afetivo: dict[str, float | str | None]
    emocao_principal: str
    nuances: tuple[str, ...]
    foco_atencao: str | None
    expectativa: dict[str, object] | None
    mudancas_recentes: tuple[dict[str, object], ...]
    dependencias_afetadas: tuple[str, ...]
    truncamentos: tuple[str, ...]
```

`ContextoCognitivo.to_dict()` produz JSON determinístico e `payload_bytes()` mede o UTF-8 canônico (`ensure_ascii=False`, `sort_keys=True`, separadores compactos).

---

### Task 1: Contrato cognitivo e configuração bounded

**Files:**
- Create: `infrastructure/pentium/atlas/modelo_contexto_cognitivo.py`
- Create: `infrastructure/pentium/atlas/configuracao_cognitiva.py`
- Create: `infrastructure/pentium/atlas/config_cognitiva.json`
- Test: `infrastructure/pentium/atlas/tests/test_modelo_contexto_cognitivo.py`
- Test: `infrastructure/pentium/atlas/tests/test_configuracao_cognitiva.py`

**Interfaces:**
- Consumes: apenas stdlib.
- Produces: `MotivoAtivacaoCognitiva`, `DecisaoAtivacaoCognitiva`, `ContextoCognitivo`, `PoliticaContextoCognitivo`, `PoliticaAtivacaoCognitiva`, `ConfiguracaoCognitiva`, `carregar_configuracao_cognitiva(path)`.

- [ ] **Step 1: Write failing contract tests**

```python
class ModeloContextoCognitivoTests(unittest.TestCase):
    def test_contexto_normaliza_timestamp_e_serializa_deterministicamente(self):
        ctx = ContextoCognitivo(
            versao_schema=1,
            timestamp="2026-09-05T15:00:00-03:00",
            motivo_ativacao=MotivoAtivacaoCognitiva.INTERACAO_HUMANA,
            entidade_principal="core",
            estado_tecnico="healthy",
            estado_percepcao="observado",
            incidente_principal=None,
            estado_afetivo={"valencia": 0.1, "foco_atencao": "core"},
            emocao_principal="calmo",
            nuances=("confiante",),
            foco_atencao="core",
            expectativa=None,
            mudancas_recentes=(),
            dependencias_afetadas=(),
            truncamentos=(),
        )
        self.assertEqual("2026-09-05T18:00:00+00:00", ctx.timestamp)
        self.assertEqual(ctx.to_dict(), ctx.to_dict())
        self.assertGreater(ctx.payload_bytes(), 0)
```
```python
class ConfiguracaoCognitivaTests(unittest.TestCase):
    def test_configuracao_carrega_bounds_aprovados(self):
        cfg = carregar_configuracao_cognitiva(ATLAS / "config_cognitiva.json")
        self.assertEqual(1, cfg.schema_version)
        self.assertEqual(256, cfg.contexto.max_string_chars)
        self.assertEqual(8, cfg.contexto.max_mudancas_recentes)
        self.assertEqual(8192, cfg.contexto.max_payload_bytes)
        self.assertEqual(4, cfg.ativacao.max_ativacoes_autonomas_janela)

    def test_configuracao_rejeita_limites_invalidos(self):
        with self.assertRaises(ValueError):
            PoliticaContextoCognitivo(0, 8, 8, 2, 8192)
```

- [ ] **Step 2: Run tests and confirm RED**

Run:
```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_modelo_contexto_cognitivo -v
python3 -m unittest infrastructure.pentium.atlas.tests.test_configuracao_cognitiva -v
```
Expected: import/module failures because C1 does not exist yet.

- [ ] **Step 3: Implement the minimal immutable models and config loader**

Implementation requirements:
- normalize aware timestamps to UTC;
- reject empty required strings;
- deduplicate `nuances`, `dependencias_afetadas` and `truncamentos` preserving deterministic order;
- reject negative/zero capacities;
- require `0.0 <= novidade_minima <= 1.0` and `0.0 <= delta_afetivo_minimo <= 1.0`;
- require positive cooldown/window and positive autonomous budget;
- canonical JSON serialization must use UTF-8, sorted keys and compact separators.

- [ ] **Step 4: Run the two C1 contract test modules**

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add infrastructure/pentium/atlas/modelo_contexto_cognitivo.py \
        infrastructure/pentium/atlas/configuracao_cognitiva.py \
        infrastructure/pentium/atlas/config_cognitiva.json \
        infrastructure/pentium/atlas/tests/test_modelo_contexto_cognitivo.py \
        infrastructure/pentium/atlas/tests/test_configuracao_cognitiva.py
git commit -m "feat(atlas): definir contrato cognitivo bounded C1"
```

---
### Task 2: Builder de Contexto Cognitivo

**Files:**
- Create: `infrastructure/pentium/atlas/contexto_cognitivo.py`
- Test: `infrastructure/pentium/atlas/tests/test_contexto_cognitivo.py`

**Interfaces:**
- Consumes: `GlobalAssessment`, `EstadoPercepcao`, `IncidenteTecnico | None`, `EstadoAfetivo`, `EmocaoDerivada`, `FocoAtencao`, `Expectativa | None`, `Stimulus` reduzidos, `PoliticaContextoCognitivo`.
- Produces: `ContextoCognitivoBuilder.construir(...) -> ContextoCognitivo`.

- [ ] **Step 1: Write failing builder tests**

```python
class ContextoCognitivoBuilderTests(unittest.TestCase):
    def test_builder_compacta_contratos_autoritativos_sem_mutar_origem(self):
        ctx = self.builder().construir(
            motivo=MotivoAtivacaoCognitiva.CRITICIDADE_TECNICA,
            assessment=self.assessment_critical(),
            percepcao=self.percepcao_core(),
            incidente=self.incidente_core(),
            estado_afetivo=self.estado_afetivo(),
            emocao=EmocaoDerivada("alarmado", ("vigilante",)),
            foco=self.foco_core(),
            expectativa=None,
            mudancas_recentes=self.stimuli(3),
            dependencias_afetadas=("l2jtoren", "database"),
            agora="2026-09-05T18:10:00+00:00",
        )
        self.assertEqual("critical", ctx.estado_tecnico)
        self.assertEqual("core", ctx.entidade_principal)
        self.assertEqual("alarmado", ctx.emocao_principal)
        self.assertLessEqual(ctx.payload_bytes(), 8192)
```

```python
    def test_builder_trunca_listas_strings_e_registra_truncamentos(self):
        ctx = self.builder(max_string_chars=12, max_mudancas=2).construir(...)
        self.assertEqual(2, len(ctx.mudancas_recentes))
        self.assertIn("mudancas_recentes", ctx.truncamentos)
        self.assertTrue(any(item.startswith("string:") for item in ctx.truncamentos))
```

- [ ] **Step 2: Run builder tests and confirm RED**

Run: `python3 -m unittest infrastructure.pentium.atlas.tests.test_contexto_cognitivo -v`
Expected: module/class missing.

- [ ] **Step 3: Implement `ContextoCognitivoBuilder` as a pure reducer**

Rules:
- no I/O, subprocess, network, filesystem reads or global mutable state;
- derive `entidade_principal` from incident first, then perception entity, then focus entity;
- reduce `GlobalAssessment` to state/intensity/reasons only;
- reduce perception to state/confidence/source summary only;
- reduce incident to id/type/severity/cause/confidence/recovery only;
- reduce affect to six dimensions + `foco_atencao` only;
- serialize at most configured recent changes and affected dependencies;
- if final payload exceeds `max_payload_bytes`, remove least-recent noncritical recent changes first, then optional dependencies; required core fields may never be dropped;
- every reduction caused by a bound appends one stable truncation marker.

- [ ] **Step 4: Run builder tests and full A1–A4 regression subset**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_contexto_cognitivo -v
python3 -m unittest infrastructure.pentium.atlas.tests.test_contexto_foco_emocao -v
python3 -m unittest infrastructure.pentium.atlas.tests.test_emocao_derivada -v
```
Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add infrastructure/pentium/atlas/contexto_cognitivo.py \
        infrastructure/pentium/atlas/tests/test_contexto_cognitivo.py
git commit -m "feat(atlas): compor contexto cognitivo bounded"
```

---
### Task 3: ActivationPolicy determinística

**Files:**
- Create: `infrastructure/pentium/atlas/politica_ativacao_cognitiva.py`
- Test: `infrastructure/pentium/atlas/tests/test_politica_ativacao_cognitiva.py`

**Interfaces:**
- Consumes: `PoliticaAtivacaoCognitiva`, estado anterior/atual, novidade, delta afetivo, flags de recuperação/expectativa/interação/reflexão e `agora` injetado.
- Produces: `ActivationPolicy.avaliar(...) -> DecisaoAtivacaoCognitiva` e `ActivationPolicy.registrar_ativacao(fingerprint, agora, autonomo)`.

- [ ] **Step 1: Write failing policy tests**

```python
class ActivationPolicyTests(unittest.TestCase):
    def test_interacao_humana_ativa_mesmo_durante_cooldown_autonomo(self):
        politica = self.politica()
        politica.registrar_ativacao("evento-1", "2026-09-05T18:00:00+00:00", autonomo=True)
        decisao = politica.avaliar(
            fingerprint="humano-1", agora="2026-09-05T18:00:10+00:00",
            interacao_humana=True,
        )
        self.assertTrue(decisao.ativar)
        self.assertEqual(MotivoAtivacaoCognitiva.INTERACAO_HUMANA, decisao.motivo)
```

```python
    def test_evento_autonomo_equivalente_respeita_cooldown_e_budget(self):
        politica = self.politica(cooldown_s=120, max_budget=1)
        primeira = politica.avaliar(fingerprint="core:critical", agora="2026-09-05T18:00:00+00:00", criticidade=True)
        self.assertTrue(primeira.ativar)
        politica.registrar_ativacao("core:critical", "2026-09-05T18:00:00+00:00", autonomo=True)
        repetida = politica.avaliar(fingerprint="core:critical", agora="2026-09-05T18:00:30+00:00", criticidade=True)
        self.assertFalse(repetida.ativar)
        self.assertIn(repetida.razao_bloqueio, ("cooldown", "orcamento"))
```

- [ ] **Step 2: Run policy tests and confirm RED**

Run: `python3 -m unittest infrastructure.pentium.atlas.tests.test_politica_ativacao_cognitiva -v`
Expected: module/class missing.

- [ ] **Step 3: Implement deterministic precedence and bounded history**

Precedence: `INTERACAO_HUMANA` > `CRITICIDADE_TECNICA` > `EXPECTATIVA_QUEBRADA` > `RECUPERACAO_IMPORTANTE` > `MUDANCA_ESTADO` > `MUDANCA_AFETIVA` > `NOVIDADE_RELEVANTE` > `REFLEXAO_PERIODICA`.

Autonomous events are subject to fingerprint cooldown and sliding-window budget. Internal history uses bounded deques sized from the maximum events needed by the configured window/budget; no unbounded dict/list is allowed.

- [ ] **Step 4: Run policy tests**

Expected: PASS, including threshold boundaries and timezone validation.

- [ ] **Step 5: Commit Task 3**

```bash
git add infrastructure/pentium/atlas/politica_ativacao_cognitiva.py \
        infrastructure/pentium/atlas/tests/test_politica_ativacao_cognitiva.py
git commit -m "feat(atlas): adicionar policy de ativacao cognitiva"
```

---

### Task 4: Empacotamento e Foundation CI de C1

**Files:**
- Create: `infrastructure/pentium/atlas/tests/test_c1_contexto_cognitivo_empacotamento.py`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`

**Interfaces:**
- Consumes: módulos/configuração das Tasks 1–3.
- Produces: `ATLAS_COGNITIVO_C1_INSTALL_PASS` e `DEVEX_HOMELAB_ATLAS_COGNITIVO_C1_PASS`.

- [ ] **Step 1: Write failing packaging tests**

```python
class C1EmpacotamentoTests(unittest.TestCase):
    def test_instalador_inclui_c1_sem_iniciar_servico_ou_llm(self):
        texto = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for nome in ("modelo_contexto_cognitivo.py", "configuracao_cognitiva.py", "contexto_cognitivo.py", "politica_ativacao_cognitiva.py", "config_cognitiva.json", "ATLAS_COGNITIVO_C1_INSTALL_PASS"):
            self.assertIn(nome, texto)
        for proibido in ("llama.cpp", "systemctl enable", "systemctl start"):
            self.assertNotIn(proibido, texto)
```

```python
    def test_ci_compila_valida_e_marca_c1(self):
        texto = (ROOT / ".github" / "workflows" / "foundation-ci.yml").read_text(encoding="utf-8")
        self.assertIn("DEVEX_HOMELAB_ATLAS_COGNITIVO_C1_PASS", texto)
        self.assertIn("config_cognitiva.json", texto)
```

- [ ] **Step 2: Run packaging test and confirm RED**
Run: `python3 -m unittest infrastructure.pentium.atlas.tests.test_c1_contexto_cognitivo_empacotamento -v`
Expected: FAIL because installer/CI do not contain C1 yet.

- [ ] **Step 3: Update installer and CI minimally**
Add four Python modules and one config to install/compile/json validation lists. Add C1 marker after full Atlas unittest discovery. Do not add runtime service, model download or inference invocation.

- [ ] **Step 4: Run packaging test, bash syntax and JSON validation**
```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_c1_contexto_cognitivo_empacotamento -v
bash -n infrastructure/pentium/atlas/install-user.sh
python3 -m json.tool infrastructure/pentium/atlas/config_cognitiva.json >/dev/null
```
Expected: PASS.

- [ ] **Step 5: Commit Task 4**
```bash
git add infrastructure/pentium/atlas/install-user.sh .github/workflows/foundation-ci.yml \
        infrastructure/pentium/atlas/tests/test_c1_contexto_cognitivo_empacotamento.py
git commit -m "ci(atlas): integrar gate do contexto cognitivo C1"
```

---
### Task 5: Verificação integrada, documentação de evidência e checkpoint

**Files:**
- Modify only if needed after test evidence: `docs/superpowers/plans/2026-09-05-atlas-c1-contexto-cognitivo.md`
- No production code changes are allowed in this task unless a failing gate reveals a real defect; such a defect must return to the responsible task with a new RED/GREEN cycle.

**Interfaces:**
- Consumes: all C1 modules and full Atlas suite.
- Produces: verified HEAD ready for PR/checkpoint, not deployment.

- [ ] **Step 1: Run C1-focused suite**

```bash
python3 -m unittest \
  infrastructure.pentium.atlas.tests.test_modelo_contexto_cognitivo \
  infrastructure.pentium.atlas.tests.test_configuracao_cognitiva \
  infrastructure.pentium.atlas.tests.test_contexto_cognitivo \
  infrastructure.pentium.atlas.tests.test_politica_ativacao_cognitiva \
  infrastructure.pentium.atlas.tests.test_c1_contexto_cognitivo_empacotamento -v
```
Expected: all PASS.

- [ ] **Step 2: Run full Atlas regression**

```bash
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
```
Expected: all existing A1–A4/D1/D2 and C1 tests PASS.

- [ ] **Step 3: Run static/package gates**

```bash
python3 -m py_compile \
  infrastructure/pentium/atlas/modelo_contexto_cognitivo.py \
  infrastructure/pentium/atlas/configuracao_cognitiva.py \
  infrastructure/pentium/atlas/contexto_cognitivo.py \
  infrastructure/pentium/atlas/politica_ativacao_cognitiva.py
python3 -m json.tool infrastructure/pentium/atlas/config_cognitiva.json >/dev/null
bash -n infrastructure/pentium/atlas/install-user.sh
git diff --check origin/main...HEAD
```
Expected: all commands exit 0.

- [ ] **Step 4: Verify C1 has zero inference/runtime authority**

```bash
git grep -n -E 'llama\.cpp|Qwen|subprocess|os\.system|Popen|run_shell|ssh\(' -- infrastructure/pentium/atlas/modelo_contexto_cognitivo.py infrastructure/pentium/atlas/configuracao_cognitiva.py infrastructure/pentium/atlas/contexto_cognitivo.py infrastructure/pentium/atlas/politica_ativacao_cognitiva.py && exit 1 || exit 0
```
Expected: exit 0 with no prohibited integration in C1 production modules.

- [ ] **Step 5: Push branch and open/update PR for Issue #20**

PR title: `feat(atlas): implementar C1 Contexto Cognitivo bounded`

PR body must state: spec path, exact HEAD, C1-only scope, tests executed, no real LLM/inference, no CONTROL/DESTRUCTIVE, and next slice C2 only after C1 GREEN.

- [ ] **Step 6: Verify Foundation CI on the exact PR HEAD**

Required marker: `DEVEX_HOMELAB_ATLAS_COGNITIVO_C1_PASS` plus `DEVEX_HOMELAB_FOUNDATION_CI_PASS`. Any new commit invalidates the evidence and requires a fresh run.

- [ ] **Step 7: Draft `/checkpoint` in pt-BR**

Include: implementation completed, exact SHA, C1-focused and full-suite evidence, Foundation CI result on that SHA, confirmed absence of LLM/backend/operational authority, blockers if any, and next safe step `C2 — LLM Gateway` only after C1 is GREEN.

## Definition of Done — C1

- `ContextoCognitivo` is immutable, serializable and deterministic.
- Required fields come only from existing authoritative contracts.
- Strings, recent changes, nuances, dependencies and final UTF-8 payload are bounded.
- Every truncation is explicitly recorded.
- ActivationPolicy covers all eight approved activation reasons.
- Autonomous activations obey cooldown, deduplication and sliding-window budget.
- Human interaction is not suppressed by autonomous cooldown/budget.
- C1 performs zero LLM calls and owns zero shell/SSH/network capability.
- Installer packages C1 without starting a service.
- Full Atlas suite remains GREEN.
- Foundation CI is GREEN on the exact final HEAD with the C1 marker.
- PR checkpoint records evidence and the next step; no physical deployment is claimed by C1.
