# Atlas Observation Affective Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Conectar `ObservationRuntime` ao estado afetivo/visual por um pipeline bounded e determinístico que reutiliza A1/A2/A3/A4 sem duplicar ownership.

**Architecture:** `ObservationRuntime` emite apenas estímulos aceitos para um sink opcional fail-safe. `PipelineAfetivoObservacional` coordena A3, A2, `AdaptadorImpactoAfetivo`, A1 e A4, entregando somente `ResultadoFocoEmocao` ao `AffectiveRuntime` visual.

**Tech Stack:** Python stdlib, `dataclasses`, `unittest`, JSON versionado, Foundation CI existente.

**Spec:** `docs/superpowers/specs/2026-09-08-atlas-observation-affective-pipeline-design.md`

## Global Constraints
- Base funcional: `67d62d5a6fb8c8f9547b2238238fdb6ec4ab37b4`.
- Não consumir `StimulusBus.poll()` para afeto.
- Apenas `Stimulus` aceito pelo bus pode alcançar o sink afetivo.
- A1 é o único owner mutável de `EstadoAfetivo`.
- A3 continua owner de percepção/incidentes; A2 de vínculos/histórico; A4 de foco/emoção.
- Nenhum LLM escolhe impulso, gravidade, foco ou emoção.
- Filas, caches, IDs e diagnósticos devem permanecer bounded.
- Nenhuma mudança em L2jToren.

---
### Task 1: Sink de estímulo aceito no Observation Runtime

**Files:**
- Modify: `infrastructure/pentium/atlas/observation_runtime.py`
- Test: `infrastructure/pentium/atlas/tests/test_observation_runtime.py`

**Interfaces:**
- Produces: `accepted_stimulus_sink: Callable[[Stimulus], None] | None` no construtor.
- Behavior: invoca sink somente após `bus.publish(...).accepted is True`; falha do sink vira erro `accepted_sink:<Tipo>` e não interrompe journal/runtime.

- [ ] Escrever testes para aceito, recusado por pressão e sink falho.
- [ ] Rodar os testes e observar RED por argumento inexistente/comportamento ausente.
- [ ] Implementar callback mínimo dentro de `_publish` sem mudar semântica do bus.
- [ ] Rodar `test_observation_runtime.py` e observar GREEN.
- [ ] Commit: `feat(atlas): expor estimulo observacional aceito`.

### Task 2: Adaptador de impacto afetivo observacional

**Files:**
- Create: `infrastructure/pentium/atlas/adaptador_impacto_afetivo.py`
- Test: `infrastructure/pentium/atlas/tests/test_adaptador_impacto_afetivo.py`

**Interfaces:**
- Produces: `ConfigImpactoAfetivo`, `ImpactoAfetivoObservacional`, `AdaptadorImpactoAfetivo.derivar(...)`.
- Consumes: `Stimulus`, `ResultadoPipelinePercepcaoCorrelacao`, `VinculoAfetivo | None`, `reincidencia: float`.

- [ ] Testar percepção insegura, incidente conhecido, recuperação, vínculo ausente e gravidade desconhecida conservadora.
- [ ] Rodar testes e observar RED por módulo ausente.
- [ ] Implementar dataclasses/configuração bounded e regras determinísticas da spec.
- [ ] Rodar testes do adaptador e observar GREEN.
- [ ] Commit: `feat(atlas): derivar impacto afetivo da observacao`.
### Task 3: Pipeline afetivo observacional

**Files:**
- Create: `infrastructure/pentium/atlas/pipeline_afetivo_observacional.py`
- Test: `infrastructure/pentium/atlas/tests/test_pipeline_afetivo_observacional.py`

**Interfaces:**
- Produces: `ResultadoPipelineAfetivoObservacional` e `PipelineAfetivoObservacional.processar(stimulus)`.
- Coordena: A3 → A2/reincidência → adaptador → histórico A2 → A1 → assuntos bounded → A4 → `AffectiveRuntime.atualizar_resultado`.

- [ ] Testar processamento único, duplicata sem segundo impulso, abertura/recuperação uma vez e erro bounded de entidade A2 desconhecida.
- [ ] Rodar testes e observar RED por módulo ausente.
- [ ] Implementar caches bounded com `deque`/sets e transições por `incidente_id`.
- [ ] Rodar testes do pipeline e observar GREEN.
- [ ] Commit: `feat(atlas): coordenar pipeline observacional afetivo`.

### Task 4: Configuração, empacotamento e CI

**Files:**
- Create: `infrastructure/pentium/atlas/config_observation_affective.json`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`
- Test: `infrastructure/pentium/atlas/tests/test_observation_affective_packaging.py`

- [ ] Escrever teste de packaging/markers/config e observar RED.
- [ ] Adicionar config schema v1 com capacidades, mapa de gravidade e ganhos bounded.
- [ ] Incluir novos módulos/config no install, `py_compile`, `json.tool` e gate Foundation CI.
- [ ] Rodar teste de packaging e observar GREEN.
- [ ] Commit: `ci(atlas): certificar pipeline observacional afetivo`.

### Task 5: Integração end-to-end e certificação

**Files:**
- Test: `infrastructure/pentium/atlas/tests/test_observation_affective_integration.py`

- [ ] Criar teste `ObservationRuntime → sink → A3/A2/A1/A4 → AffectiveRuntime → visual-state.json` e observar RED antes do wiring final necessário.
- [ ] Completar apenas o wiring exigido pelo teste, sem daemon novo nesta slice.
- [ ] Rodar testes focados, Atlas completo e dashboard completo.
- [ ] Rodar `py_compile`, `json.tool`, `bash -n`, `git diff --check` e guard UTF-8.
- [ ] Commit: `test(atlas): certificar pipeline observacional afetivo`.
