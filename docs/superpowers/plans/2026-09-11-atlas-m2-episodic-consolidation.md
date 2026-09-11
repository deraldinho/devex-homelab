# Atlas M2 Episodic Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar consolidação episódica bounded, persistente e exactly-once para o Atlas, com provenance, reliability snapshot e generation fencing, sem alterar o comportamento afetivo existente.

**Architecture:** Eventos já validados passam por adapters explícitos e viram `EpisodicEvidence`. Um `EpisodicBuffer` persiste segmentos OPEN/CLOSED; um `EpisodicConsolidator` produz exatamente um `MemoryRecord` determinístico por segmento na M2 e o `MemoryStore` grava memória + provenance + `CONSOLIDATED` atomicamente. `MemoryRetriever`, `ReactionLoopCognitivo` e `ContextoAfetivo` permanecem compatíveis.

**Tech Stack:** Python 3, `dataclasses`, `enum`, SQLite/WAL, `unittest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-11-atlas-episodic-consolidation-design.md`

## Global Constraints

- A LLM não decide persistência, fechamento, promoção nem exclusão.
- Não persistir `Stimulus.payload` bruto, segredos ou credenciais.
- `generation_id` muda a cada execução lógica do runtime.
- Segmentos OPEN recuperados após restart fecham como `restart_recovery`; nunca recebem eventos da nova geração.
- O schema interno SQLite evolui para v2; `config_memory.json` permanece schema 1 e aceita defaults M2.
- Exactly-once é obrigatório por `segment_id`; retry não duplica memória, provenance ou `frequency`.
- `MemoryRecord`, `MemoryRetriever`, `ReactionLoopCognitivo` e `ContextoAfetivo` preservam seus contratos atuais.
- TDD obrigatório; cada task termina com testes GREEN e commit próprio.

---

## File Map

**Create:**
- `infrastructure/pentium/atlas/episodic_model.py` — enums e dataclasses imutáveis de segmento/evidência/provenance.
- `infrastructure/pentium/atlas/episodic_buffer.py` — segmentação, bounds, fechamento e recovery de restart.
- `infrastructure/pentium/atlas/episodic_consolidator.py` — transformação determinística CLOSED -> `MemoryRecord`.
- `infrastructure/pentium/atlas/episodic_adapters.py` — adapters allowlisted para percepção/incidente.
- `infrastructure/pentium/atlas/episodic_ingestion.py` — coordenador que liga resultado validado -> buffer -> consolidação/recovery.
- `infrastructure/pentium/atlas/episodic_metrics.py` — contadores bounded em memória, sem conteúdo sensível.
- `infrastructure/pentium/atlas/tests/test_episodic_model.py`
- `infrastructure/pentium/atlas/tests/test_episodic_buffer.py`
- `infrastructure/pentium/atlas/tests/test_episodic_consolidator.py`
- `infrastructure/pentium/atlas/tests/test_episodic_adapters.py`
- `infrastructure/pentium/atlas/tests/test_episodic_ingestion.py`
- `infrastructure/pentium/atlas/tests/test_m2_memory_packaging.py`

**Modify:**
- `infrastructure/pentium/atlas/config_memory.py` e `config_memory.json` — defaults/validação M2 sem elevar schema de configuração.
- `infrastructure/pentium/atlas/memory_store.py` — migração SQLite v1->v2, CRUD episódico, provenance e commit exactly-once.
- `infrastructure/pentium/atlas/memory_manager.py` — entrada canônica `remember_consolidated(...)`.
- `infrastructure/pentium/atlas/pipeline_percepcao_correlacao.py` — sink opcional pós-validação, mantendo comportamento default.
- `infrastructure/pentium/atlas/install-user.sh` e `.github/workflows/foundation-ci.yml` — empacotamento/gate M2.

---

### Task 1: Modelo episódico e configuração bounded

**Files:**
- Create: `infrastructure/pentium/atlas/episodic_model.py`
- Modify: `infrastructure/pentium/atlas/config_memory.py`
- Modify: `infrastructure/pentium/atlas/config_memory.json`
- Test: `infrastructure/pentium/atlas/tests/test_episodic_model.py`
- Test: `infrastructure/pentium/atlas/tests/test_config_memory.py`**Interfaces:**
- Produces: `EpisodeCategory`, `SegmentStatus`, `ClosureReason`, `EpisodicEvidence`, `EpisodicSegment`, `MemoryProvenance`.
- Produces config fields: `episodic_max_events`, `episodic_max_bytes`, `episodic_max_open_segments`, `episodic_max_pending_bytes`, `episodic_idle_timeout_s`.

- [ ] **Step 1: Write failing model/config tests**

```python
class EpisodicModelTests(unittest.TestCase):
    def test_evidence_normaliza_timestamp_e_valida_generation(self):
        ev = EpisodicEvidence(
            "e1", "2026-09-11T12:00:00-03:00", "core.agent", "perception",
            "core inacessivel", 0.9, True, "gen-1", "core:down", 0.8, 0.9,
        )
        self.assertEqual("2026-09-11T15:00:00+00:00", ev.occurred_at)
        self.assertEqual("gen-1", ev.generation_id)

    def test_config_schema_1_aplica_defaults_episodicos(self):
        cfg = load_memory_config(Path("infrastructure/pentium/atlas/config_memory.json"))
        self.assertGreater(cfg.episodic_max_events, 0)
        self.assertGreater(cfg.episodic_max_pending_bytes, cfg.episodic_max_bytes)
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_episodic_model infrastructure.pentium.atlas.tests.test_config_memory -v`
Expected: FAIL because episodic types/fields do not exist.

- [ ] **Step 3: Implement immutable domain model**

```python
class EpisodeCategory(str, Enum):
    INCIDENT = "incident"
    DEPLOYMENT = "deployment"
    DEVELOPMENT_SESSION = "development_session"
    HUMAN_INTERACTION = "human_interaction"
    GENERIC = "generic"

class SegmentStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    CONSOLIDATED = "consolidated"
```
```python
@dataclass(frozen=True)
class EpisodicEvidence:
    event_id: str
    occurred_at: str
    source: str
    source_kind: str
    content_reduced: str
    reliability: float
    verified: bool
    generation_id: str
    dedupe_key: str | None
    importance: float
    criticality: float
```

Implement `EpisodicSegment` with `segment_key` as deterministic internal routing key plus the spec fields, and `MemoryProvenance` with `segment_id`, `memory_id`, `generation_id`, `sources`, `interval_start`, `interval_end`, `evidence_count`.

- [ ] **Step 4: Extend config loader with safe schema-1 defaults**

Use defaults: `max_events=32`, `max_bytes=16384`, `max_open_segments=64`, `max_pending_bytes=524288`, `idle_timeout_s=300.0`. Add optional `episodic` object to repository JSON with those explicit values; reject zero/negative values.

- [ ] **Step 5: Run tests and confirm GREEN**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_episodic_model infrastructure.pentium.atlas.tests.test_config_memory -v`
Expected: PASS, including existing M1 config assertions.

- [ ] **Step 6: Commit**

```bash
git add infrastructure/pentium/atlas/episodic_model.py infrastructure/pentium/atlas/config_memory.py infrastructure/pentium/atlas/config_memory.json infrastructure/pentium/atlas/tests/test_episodic_model.py infrastructure/pentium/atlas/tests/test_config_memory.py
git commit -m "feat(atlas): add bounded episodic memory model"
```

---

### Task 2: SQLite v2 migration and episodic persistence

**Files:**
- Modify: `infrastructure/pentium/atlas/memory_store.py`
- Test: `infrastructure/pentium/atlas/tests/test_memory_store.py`

**Interfaces:**
- Consumes: Task 1 episodic dataclasses.
- Produces: `save_segment`, `get_segment`, `list_open_segments`, `append_evidence`, `list_evidence`, `close_segment`, `get_provenance`, `persist_consolidated`.

- [ ] **Step 1: Write failing migration and round-trip tests**

```python
class MemoryStoreV2Tests(unittest.TestCase):
    def test_migra_v1_para_v2_sem_perder_memorias(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.db"
            store = MemoryStore(path)
            legacy = MemoryRecord(
                "legacy", MemoryLayer.EPISODIC, "2026-09-11T12:00:00+00:00",
                "core", "evento legado", 0.5, 0.8, 1, "observation",
            )
            store.save(legacy)
            store.close()
            migrated = MemoryStore(path)
            self.assertIsNotNone(migrated.get("legacy"))
            self.assertEqual("2", migrated.schema_version())

    def test_segmento_e_evidencia_sobrevivem_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.db"
            store = MemoryStore(path)
            segment = make_segment("seg-1", "gen-1")
            evidence = make_evidence("e1", "gen-1")
            store.save_segment(segment)
            store.append_evidence(segment.segment_id, evidence)
            store.close()
            reopened = MemoryStore(path)
            self.assertEqual(segment.segment_id, reopened.get_segment(segment.segment_id).segment_id)
            self.assertEqual((evidence,), reopened.list_evidence(segment.segment_id))
```

Add local test helpers `make_segment()` and `make_evidence()` in `test_memory_store.py` using Task 1 constructors with fixed UTC timestamps and bounded values.

- [ ] **Step 2: Run focused test and confirm RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_memory_store.MemoryStoreV2Tests -v`
Expected: FAIL because schema v2 methods/tables do not exist.

- [ ] **Step 3: Implement transactional v1->v2 migration**

Keep `memories` unchanged. In one SQLite transaction create `episodic_segments`, `episodic_evidence`, and `memory_provenance`; then update `meta.schema_version` from `1` to `2`. Accept fresh DB and v1 DB; reject any other version without destructive fallback.

Required uniqueness/foreign keys: `episodic_segments.segment_id PRIMARY KEY`, `episodic_evidence.event_id PRIMARY KEY`, `memory_provenance.segment_id PRIMARY KEY`, and `memory_provenance.memory_id REFERENCES memories(memory_id)`.

- [ ] **Step 4: Implement bounded CRUD helpers**

`append_evidence(segment_id, evidence)` must verify the segment is OPEN, the `generation_id` matches, and the event is not already present. `close_segment(segment_id, reason, updated_at)` must be idempotent for an already CLOSED segment and must never reopen a segment.

- [ ] **Step 5: Run all store tests**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_memory_store -v`
Expected: PASS for M1 transaction tests plus new v2 migration/round-trip tests.

- [ ] **Step 6: Commit**

```bash
git add infrastructure/pentium/atlas/memory_store.py infrastructure/pentium/atlas/tests/test_memory_store.py
git commit -m "feat(atlas): persist episodic segments in memory store v2"
```

---

### Task 3: EpisodicBuffer, fechamento e restart recovery

**Files:**
- Create: `infrastructure/pentium/atlas/episodic_buffer.py`
- Create: `infrastructure/pentium/atlas/episodic_metrics.py`
- Test: `infrastructure/pentium/atlas/tests/test_episodic_buffer.py`

**Interfaces:**
- Consumes: `EpisodicEvidence`, `EpisodicSegment`, `MemoryStore`, M2 config bounds.
- Produces: `EpisodicBuffer.ingest(...)`, `close_idle(...)`, `recover_previous_generation(...)`, `EpisodicIngestResult`.

- [ ] **Step 1: Write failing generation-fence and bounds tests**

```python
class EpisodicBufferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "memory.db")
        self.cfg = make_memory_config(episodic_max_bytes=64, episodic_max_pending_bytes=96)
        self.buffer = EpisodicBuffer(self.store, self.cfg, id_factory=iter(("seg-1", "seg-2")).__next__)

    def test_generation_mismatch_closes_old_and_opens_new(self):
        first = self.buffer.ingest(make_evidence("e1", "gen-1"), EpisodeCategory.INCIDENT, "incident:core")
        second = self.buffer.ingest(make_evidence("e2", "gen-2"), EpisodeCategory.INCIDENT, "incident:core")
        self.assertEqual(ClosureReason.GENERATION_FENCE, self.store.get_segment(first.segment_id).closure_reason)
        self.assertNotEqual(first.segment_id, second.segment_id)

    def test_pending_bytes_never_exceed_global_bound(self):
        oversized = make_evidence("e-big", "gen-1", content="x" * 80)
        self.buffer.ingest(oversized, EpisodeCategory.GENERIC, "g:1")
        with self.assertRaises(OverflowError):
            self.buffer.ingest(make_evidence("e2", "gen-1", content="y" * 40), EpisodeCategory.GENERIC, "g:2")
        self.assertLessEqual(self.buffer.pending_bytes(), self.cfg.episodic_max_pending_bytes)
```

Add local `make_memory_config()` and `make_evidence()` helpers using the Task 1 constructors; keep their values fixed and deterministic.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_episodic_buffer -v`
Expected: FAIL because `EpisodicBuffer` does not exist.

- [ ] **Step 3: Implement deterministic routing and closure**

`segment_key` is derived from `(category.value, entity_id or "-", semantic_key)`. Reuse only an OPEN segment from the same `generation_id` and key. Close on terminal flag, incompatible key, idle timeout, per-segment event/byte limits, or generation mismatch.

- [ ] **Step 4: Implement restart recovery**

```python
def recover_previous_generation(self, current_generation_id: str, now: str) -> tuple[str, ...]:
    recovered = []
    for segment in self._store.list_open_segments():
        if segment.generation_id == current_generation_id:
            continue
        self._store.close_segment(segment.segment_id, ClosureReason.RESTART_RECOVERY, now)
        recovered.append(segment.segment_id)
        self._metrics.increment("generation_fence_total")
    return tuple(recovered)
```

Recovery only closes; consolidation remains Task 4 so failures are retryable.

- [ ] **Step 5: Add content-free metrics**

Implement counters/gauges for `episodes_open`, `episodes_closed_total`, `episode_events_total`, `episode_bytes`, `generation_fence_total`, `stale_event_rejected_total`; metric labels may contain category/source kind, never evidence content.

- [ ] **Step 6: Run focused and store tests**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_episodic_buffer infrastructure.pentium.atlas.tests.test_memory_store -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add infrastructure/pentium/atlas/episodic_buffer.py infrastructure/pentium/atlas/episodic_metrics.py infrastructure/pentium/atlas/tests/test_episodic_buffer.py
git commit -m "feat(atlas): add fenced episodic buffer"
```
---

### Task 4: Deterministic consolidator and exactly-once commit

**Files:**
- Create: `infrastructure/pentium/atlas/episodic_consolidator.py`
- Modify: `infrastructure/pentium/atlas/memory_manager.py`
- Modify: `infrastructure/pentium/atlas/memory_store.py`
- Test: `infrastructure/pentium/atlas/tests/test_episodic_consolidator.py`
- Test: `infrastructure/pentium/atlas/tests/test_memory_manager.py`

**Interfaces:**
- Consumes: CLOSED `EpisodicSegment` + ordered evidence tuple.
- Produces: `EpisodicConsolidator.consolidate(segment_id, now) -> bool`.
- Produces: `MemoryManager.remember_consolidated(segment, record, provenance, now) -> bool`.

- [ ] **Step 1: Write failing exactly-once tests**

```python
class EpisodicConsolidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "memory.db"
        self.store = MemoryStore(self.path)
        seed_closed_segment(self.store, "seg-1", "gen-1", make_evidence("e1", "gen-1"))
        self.manager = MemoryManager(self.store, MemoryPolicy(100, 100000))
        self.consolidator = EpisodicConsolidator(self.store, self.manager)

    def test_retry_same_segment_is_exactly_once(self):
        self.assertTrue(self.consolidator.consolidate("seg-1", NOW))
        before = self.store.count()
        self.assertFalse(self.consolidator.consolidate("seg-1", NOW))
        self.assertEqual(before, self.store.count())
        self.assertEqual(1, self.store.get_provenance("seg-1").evidence_count)

    def test_mixed_generation_segment_fails_closed(self):
        with sqlite3.connect(self.path) as raw:
            raw.execute("UPDATE episodic_evidence SET generation_id='gen-2' WHERE event_id='e1'")
        with self.assertRaises(ValueError):
            self.consolidator.consolidate("seg-1", NOW)
```

Add deterministic local helpers `make_evidence()` and `seed_closed_segment()`; the latter saves an OPEN segment, appends evidence through the public store API, then closes it.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_episodic_consolidator -v`
Expected: FAIL because consolidator and exactly-once API do not exist.

- [ ] **Step 3: Implement deterministic single-record consolidation for M2**

Order evidence by `(occurred_at, event_id)`. Reject empty evidence or mixed generation. Build one bounded content string from allowlisted reduced evidence, capped at `MemoryRecord`'s 1024 chars. Compute `importance=max`, `criticality=max`, and confidence as reliability-weighted mean where unverified evidence contributes weight `0.0`.

Use deterministic IDs: `memory_id="episode:" + segment_id` and `dedupe_key` from the segment semantic key. Set layer `EPISODIC`, origin `episodic:<category>`.

- [ ] **Step 4: Implement atomic store commit**

```python
def persist_consolidated(self, segment_id, record, provenance) -> bool:
    with self._db:
        row = self._db.execute(
            "SELECT status FROM episodic_segments WHERE segment_id=?", (segment_id,)
        ).fetchone()
        if row is None or row[0] not in ("closed", "consolidated"):
            raise MemoryStoreError("segmento nao esta CLOSED")
        if row[0] == "consolidated":
            return False
        existing = None
        if record.dedupe_key:
            existing = self._db.execute(
                "SELECT memory_id,frequency,importance,confidence,criticality,pinned,protected "
                "FROM memories WHERE dedupe_key=? ORDER BY created_at,memory_id LIMIT 1",
                (record.dedupe_key,),
            ).fetchone()
        memory_id = self._merge_or_insert_memory(record, existing)
        bound = replace(provenance, memory_id=memory_id)
        self._insert_provenance(bound)
        self._db.execute(
            "UPDATE episodic_segments SET status='consolidated' WHERE segment_id=?",
            (segment_id,),
        )
    return True
```

Implement `_merge_or_insert_memory()` and `_insert_provenance()` as private helpers that execute SQL only and never commit independently; the enclosing `with self._db:` owns the transaction.

If `dedupe_key` matches an existing memory, merge frequency/scores inside the same transaction; provenance still records this segment -> existing `memory_id`. A retry sees `CONSOLIDATED` and returns `False` before any merge.

- [ ] **Step 5: Expose canonical manager API**

`MemoryManager.remember_consolidated(...)` validates FULL-pressure policy and delegates the atomic write. Existing `remember()` stays unchanged for legacy callers.

- [ ] **Step 6: Run RED/GREEN regression set**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_episodic_consolidator infrastructure.pentium.atlas.tests.test_memory_manager infrastructure.pentium.atlas.tests.test_memory_store -v`
Expected: PASS, including M1 dedupe/promotion tests.

- [ ] **Step 7: Commit**

```bash
git add infrastructure/pentium/atlas/episodic_consolidator.py infrastructure/pentium/atlas/memory_manager.py infrastructure/pentium/atlas/memory_store.py infrastructure/pentium/atlas/tests/test_episodic_consolidator.py infrastructure/pentium/atlas/tests/test_memory_manager.py infrastructure/pentium/atlas/tests/test_memory_store.py
git commit -m "feat(atlas): consolidate episodes exactly once"
```

---

### Task 5: Safe adapters from validated perception/incidents

**Files:**
- Create: `infrastructure/pentium/atlas/episodic_adapters.py`
- Modify: `infrastructure/pentium/atlas/pipeline_percepcao_correlacao.py`
- Test: `infrastructure/pentium/atlas/tests/test_episodic_adapters.py`
- Test: `infrastructure/pentium/atlas/tests/test_pipeline_percepcao_correlacao.py`

**Interfaces:**
- Produces: `evidence_from_perception(perception, generation_id) -> EpisodicEvidence`.
- Produces: `evidence_from_incident(incident, generation_id) -> tuple[EpisodicEvidence, EpisodeCategory, str, bool]`.
- Pipeline adds optional `episodic_sink: Callable[[ResultadoPipelinePercepcaoCorrelacao], None] | None = None`.

- [ ] **Step 1: Write failing allowlist tests**

```python
class EpisodicAdapterTests(unittest.TestCase):
    def setUp(self):
        self.incident = IncidenteTecnico(
            "inc-1", "core", "indisponibilidade_correlacionada", "critical",
            "2026-09-11T12:00:00+00:00", "core", 0.9, ("core",), 1,
        )

    def test_incident_adapter_never_embeds_raw_payload(self):
        ev, category, key, terminal = evidence_from_incident(self.incident, "gen-1")
        self.assertEqual(EpisodeCategory.INCIDENT, category)
        self.assertEqual("incident:inc-1", key)
        self.assertNotIn("payload", ev.content_reduced.lower())
        self.assertIn("core", ev.content_reduced)

    def test_recovered_incident_is_terminal(self):
        recovered = replace(self.incident, estado_recuperacao=EstadoRecuperacaoIncidente.RECUPERADO)
        self.assertTrue(evidence_from_incident(recovered, "gen-1")[3])
```

- [ ] **Step 2: Run adapter tests and confirm RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_episodic_adapters -v`
Expected: FAIL because adapters do not exist.

- [ ] **Step 3: Implement reduced, deterministic adapters**

Perception content may include only entity id, observation state, confidence, conflict flag and source-name sets. Incident content may include only incident id, entity, type, severity, recovery state, bounded affected-entity count and probable-cause identifier. Do not pass arbitrary dictionaries.

Reliability rules for M2: perception uses `perception.confianca`; incident uses `incident.confianca_causal`; `verified=True` only when the source object is already a validated pipeline result.

- [ ] **Step 4: Add optional post-validation sink to pipeline**

After `ResultadoPipelinePercepcaoCorrelacao(True, percepcao, incidentes)` is built, invoke the sink inside a narrow `try/except Exception` that records/returns perception normally even if episodic ingestion fails. Do not invoke the sink for duplicate stimuli (`aceito=False`).

- [ ] **Step 5: Add compatibility tests**

```python
def test_pipeline_without_sink_preserves_existing_result(self):
    pipeline = build_pipeline()
    result = pipeline.processar(stimulus)
    self.assertTrue(result.aceito)

def test_duplicate_stimulus_does_not_emit_episode_twice(self):
    seen = []
    pipeline = build_pipeline(episodic_sink=seen.append)
    pipeline.processar(stimulus)
    pipeline.processar(stimulus)
    self.assertEqual(1, len(seen))
```

- [ ] **Step 6: Run perception + adapter regression tests**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_episodic_adapters infrastructure.pentium.atlas.tests.test_pipeline_percepcao_correlacao -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add infrastructure/pentium/atlas/episodic_adapters.py infrastructure/pentium/atlas/pipeline_percepcao_correlacao.py infrastructure/pentium/atlas/tests/test_episodic_adapters.py infrastructure/pentium/atlas/tests/test_pipeline_percepcao_correlacao.py
git commit -m "feat(atlas): ingest validated perception into episodic memory"
```

---

### Task 6: Coordenador de ingestão e recovery end-to-end

**Files:**
- Create: `infrastructure/pentium/atlas/episodic_ingestion.py`
- Modify: `infrastructure/pentium/atlas/memory_store.py`
- Test: `infrastructure/pentium/atlas/tests/test_episodic_ingestion.py`

**Interfaces:**
- Consumes: validated `ResultadoPipelinePercepcaoCorrelacao`, adapters, buffer, consolidator.
- Produces: `EpisodicMemorySink.__call__(result)`, `recover(now)`, `flush_idle(now)`.

- [ ] **Step 1: Write failing end-to-end tests**

```python
def test_incident_open_then_recovery_creates_one_memory(self):
    sink(open_result)
    sink(recovered_result)
    self.assertEqual(1, store.count())
    self.assertEqual("consolidated", store.get_segment("seg-1").status.value)

def test_restart_recovery_consolidates_old_generation_once(self):
    old_sink(open_result)
    new_sink.recover(NOW)
    new_sink.recover(NOW)
    self.assertEqual(1, store.count())
```

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_episodic_ingestion -v`
Expected: FAIL because coordinator and closed-segment query do not exist.

- [ ] **Step 3: Implement coordinator behavior**

`EpisodicMemorySink` owns one `generation_id`. For each accepted incident result, adapt -> `buffer.ingest(...)`; if ingest closes a segment, immediately call consolidator for that segment. `flush_idle(now)` closes idle segments then consolidates them. `recover(now)` calls `recover_previous_generation(...)` then consolidates every recovered CLOSED segment.

Do not generate memory from duplicate pipeline results. If consolidation fails, leave the segment CLOSED and increment `consolidation_rejected_total`; a later `recover`/`flush_idle` retries it.

- [ ] **Step 4: Add `list_closed_segments()` to store**

Return only CLOSED, never CONSOLIDATED, ordered by `(updated_at, segment_id)` with an explicit limit. This is the retry queue; it must stay bounded by the same pending-byte policy.

- [ ] **Step 5: Verify restart + retry semantics**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_episodic_ingestion infrastructure.pentium.atlas.tests.test_episodic_buffer infrastructure.pentium.atlas.tests.test_episodic_consolidator -v`
Expected: PASS and exactly one memory after duplicate recovery calls.

- [ ] **Step 6: Commit**

```bash
git add infrastructure/pentium/atlas/episodic_ingestion.py infrastructure/pentium/atlas/memory_store.py infrastructure/pentium/atlas/tests/test_episodic_ingestion.py
git commit -m "feat(atlas): wire episodic ingestion and restart recovery"
```

---

### Task 7: Packaging, CI and non-regression certification

**Files:**
- Create: `infrastructure/pentium/atlas/tests/test_m2_memory_packaging.py`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`
- Test: existing M1, cognitive and affective suites.

**Interfaces:**
- Produces installer marker `ATLAS_MEMORY_M2_INSTALL_PASS` and CI marker `DEVEX_HOMELAB_ATLAS_MEMORY_M2_PASS`.

- [ ] **Step 1: Write failing packaging tests**

```python
def test_installer_includes_m2_modules_and_marker(self):
    text = Path("infrastructure/pentium/atlas/install-user.sh").read_text(encoding="utf-8")
    for name in ("episodic_model.py", "episodic_buffer.py", "episodic_consolidator.py",
                 "episodic_adapters.py", "episodic_ingestion.py", "episodic_metrics.py"):
        self.assertIn(name, text)
    self.assertIn("ATLAS_MEMORY_M2_INSTALL_PASS", text)
```

- [ ] **Step 2: Run packaging test and confirm RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_m2_memory_packaging -v`
Expected: FAIL until installer/workflow include M2 modules and marker.

- [ ] **Step 3: Update installer and CI gate**

Package all six M2 modules and keep M1 files/markers intact. CI must compile the new modules, execute M2 unit tests, and emit `DEVEX_HOMELAB_ATLAS_MEMORY_M2_PASS` only after those tests pass. Do not start services automatically.

- [ ] **Step 4: Run full Atlas Python suite**

Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -p "test_*.py" -v`
Expected: 0 failures/errors. Pay special attention to `test_reaction_loop_cognitivo`, `test_contexto_afetivo`, `test_memory_*`, perception/correlation and packaging tests.

- [ ] **Step 5: Verify repository diff hygiene**

Run: `git diff --check`
Expected: no output and exit 0.

- [ ] **Step 6: Commit**

```bash
git add infrastructure/pentium/atlas/install-user.sh .github/workflows/foundation-ci.yml infrastructure/pentium/atlas/tests/test_m2_memory_packaging.py
git commit -m "ci(atlas): certify episodic memory M2"
```

---

## Final Acceptance Gate

Run from repository root:

```bash
python -m unittest discover -s infrastructure/pentium/atlas/tests -p "test_*.py" -v
git diff --check
git status --short --branch
```

Accept M2 only with the full suite GREEN, no whitespace errors, no unexpected modified files, persisted DB schema v2 migration covered, exactly-once retry covered, restart fencing covered, and affective/cognitive regressions GREEN.