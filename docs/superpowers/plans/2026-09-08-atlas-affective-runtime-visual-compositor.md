# Atlas Affective Runtime + Visual Compositor Implementation Plan

 > **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

 **Goal:** Tornar vivo o estado afetivo/visual do Atlas no Pentium, com um único owner determinístico que publica `EstadoVisualAtlas` para o dashboard sem permitir que voz, health, dashboard ou LLM inventem emoção.

 **Architecture:** `AffectiveRuntime` coordena o estado afetivo existente (A1), foco/emoção existente (A4), estado efêmero de interação e projeção visual. `CompositorVisualAfetivo` é uma função determinística e side-effect free; `VisualStatePublisher` é o único writer de `~/pentium-agent/atlas/runtime/visual-state.json`.

**Tech Stack:** Python 3 stdlib, `dataclasses`, JSON, filesystem atômico, unittest, systemd packaging existente.

 **Spec:** `docs/superpowers/specs/2026-09-08-atlas-affective-runtime-visual-compositor-design.md`

## Global Constraints
- Base funcional: `f20a2d46202733ece27d59a9313026ef73ee7a54`.
- Nenhuma LLM escolhe emoção, foco, gesto ou expressão.
- Dashboard permanece read-only.
- Voz só modula estado efêmero de interação.
- `VisualStatePublisher` é o único writer do snapshot visual.
- Nenhuma telemetria bruta, áudio bruto, transcrição completa ou biometria entra no snapshot.
- Nenhum busy loop; filas e intervalos devem permanecer bounded.
- Mudanças do Atlas ficam em `deraldinho/devex-homelab`; não tocar em L2jToren.

---

### Task 1: Contrato `EstadoVisualAtlas`

**Files:**
- Create: `infrastructure/pentium/atlas/modelo_visual_atlas.py`
- Test: `infrastructure/pentium/atlas/tests/test_modelo_visual_atlas.py`

**Interfaces:**
- Produces: `EstadoVisualAtlas`, `EstadoInteracaoVisual`, enums fechados de modo/expressão.
- Consumes: somente stdlib.

- [ ] **Step 1: Write the failing tests**
Cobrir construção válida, clamp/validação de intensidade e velocidade, limites de `transicao_ms`, enums inválidos, foco neutro e timestamps UTC para interação.

- [ ] **Step 2: Run RED**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_modelo_visual_atlas -v`
Expected: FAIL  por módulo/contratos ausentes.

- [ ] **Step 3: Implement minimal immutable contracts**
Implementar dataclasses frozen, enums string e validações determinísticas. `EstadoVisualAtlas.para_dict()` deve produzir exatamente os campos já consumidos pelo dashboard, incluindo `versao_avatar=1`.

- [ ] **Step 4: Run GREEN**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_modelo_visual_atlas -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git commit -m "feat(atlas): adicionar contrato de estado visual"`

---

### Task 2: `CompositorVisualAfetivo`

**Files:**
- Create: `infrastructure/pentium/atlas/compositor_visual_afetivo.py`
- Test: `infrastructure/pentium/atlas/tests/test_compositor_visual_afetivo.py`

**Interfaces:**
- Consumes: `ResultadoFocoEmocao`, `EstadoInteracaoVisual`.
- Produces: `EstadoVisualAtlas`.

- [ ] **Step 1: Write the failing mapping tests**
Cobrir `calmo/confiante/satisfeito ✒SERENO`, `interessado✚ENGAJADO`, `curioso→CURIOSO`, `atento/vigilante→ATENTO`, `preocupado✚PREOCUPADO`, `estressado/alarmado/frustrado→SOB_PRESSAO`, `aliviado✚RECUPERANDO`.

- [ ] **Step 2: Write failing mode/focus tests**
Cobrir prioridade `falando > pensando > ouvindo > reagindo > observando > ocioso`, foco por `FocoAtencao.principal.entidade_id`, gesto derivado e ausência de foco como `neutro`.

- [ ] **Step 3: Run RED**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_compositor_visual_afetivo -v`
Expected: FAIL  por compositor ausente.

- [ ] **Step 4: Implement deterministic compositor**
Usar somente inputs já resolvidos. Intensidade deve ser bounded `0..1` e calculada a partir das dimensões relevantes sem threshold técnico universal. Transição normal `400ms`; crítica `60ms`.

- [ ] **Step 5: Run GREEN**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_compositor_visual_afetivo -v`
Expected: PASS.

- [ ] **Step 6: Commit**
`git commit -m "feat(atlas): implementar compositor visual afetivo"`

---

### Task 3: `VisualStatePublisher`

**Files:**
- Create: infrastructure/pentium/atlas/visual_state_publisher.py`
- Test: `infrastructure/pentium/atlas/tests/test_visual_state_publisher.py`

**Interfaces:**
- Consumes: `EstadoVisualAtlas`.
- Produces: JSON atômico no path configurado.

- [ ] **Step 1: Write failing atomic-persistence tests**
Cobrir criação do diretório, JSON versionado, newline final, round-trip UTF-8, `os.replace`, remoção do `.tmp` após erro e nenhuma fila/histórico.

- [ ] **Step 2: Run RED**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_visual_state_publisher -v`
Expected: FAIL por publisher ausente.

- [ ] **Step 3: Implement publisher**
Escrever no mesmo diretório, `flush`, `os.fsync`, `os.replace`, fsync de diretório em POSIX e cleanup em `finally`.

- [ ] **Step 4: Run GREEN**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_visual_state_publisher -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git commit -m "feat(atlas): publicar estado visual atomicamente"`

---

### Task 4: `AffectiveRuntime` foundation

**Files:**
- Create: `infrastructure/pentium/atlas/affective_runtime.py`
- Test: infrastructure/pentium/atlas/tests/test_affective_runtime.py`

**Interfaces:**
- Consumes: estado A1 restaurado, snapshot A4 opcional, source injetável de atualizações, compositor, publisher.
- Produces: estado visual atual e publicação materialmente alterada.

- [ ] **Step 1: Write failing restore/isolation tests**
Cobrir ausência/corrupção A4 sem inventar emoção; A1 restaurado via mecanismo existente; publisher falhando sem derrubar estado afetivo; compositor falhando sem mutar A1/A4.

- [ ] **Step 2: Write failing update/coalescing tests**
Cobrir source injetével, atualização de interação, nao publicar estado idêntico repetidamente e publicação quando o visual muda.

- [ ] **Step 3: Run RED**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_affective_runtime -v`
Expected: FAIL por runtime ausente.

- [ ] **Step 4: Implement minimal owner**
Runtime deve manter `ultimo_visual`, receber `ResultadoFocoEmocao` já resolvido, aplicar somente projeção visual, atualizar flags efêmeras e delegar persistência ao publisher. Nenhuma leitura de health deve criar emoção.

- [ ] **Step 5: Run GREEN**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_affective_runtime -v`
Expected: PASS.

- [ ] **Step 6: Commit**
`git commit -m "feat(atlas): adicionar owner do runtime afetivo visual"`

---

### Task 5: Adaptador efêmero de voz

**Files:**
- Modify: `infrastructure/pentium/atlas/voice_runtime.py`
- Create or Modify: `infrastructure/pentium/atlas/tests/test_voice_runtime.py`

**Interfaces:**
- Consumes: callback opcional `visual_state_sink(EstadoInteracaoVisual)`.
- Produces: transições efêmeras de listening/processing/speaking/degraded sem autoridade afetiva.

- [ ] **Step 1: Write failing transition tests**
Verificar que captura/listening, STT+ interação/processing e TTS/speaking notificam o sink; ausência de sink preserva comportamento legado.

- [ ] **Step 2: Run RED**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_voice_runtime -v`
Expected: FAIL nos novos contratos.

- [ ] **Step 3: Implement optional sink**
Adicionar callback opcional; emitir flags com `try/finally` para retornar ao estado de escuta. Exceção no sink visual não pode derrubar voz.

- [ ] **Step 4: Run GREEN**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_voice_runtime -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git commit -m "feat(atlas): projetar estado efemero da voz no avatar"`

---

### Task 6: Configuração, empacotamento e gate

**Files:**
- Create: `infrastructure/pentium/atlas/config_affective_runtime.json`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`
- Test: `infrastructure/pentium/atlas/tests/test_affective_runtime_packaging.py`

**Interfaces:**
- Config: schema v1, `visual_state_path`, limites/tick/heartbeat bounded.
- Packaging: inclui todos os novos módulos e configuração.

- [ ] **Step 1: Write failing packaging tests**
Verificar módulos/config presentes no installer, config schema 1, paths e limites, e marker de CI `DEVEX_HOMELAB_ATLAS_AFFECTIVE_RUNTIME_PASS`.

- [ ] **Step 2: Run RED**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_affective_runtime_packaging -v`
Expected: FAIL até configuração/empacotamento/gate existirem.

- [ ] **Step 3: Implement config/install/CI**
Adicionar arquivos à cópia/validação do installer e gate Python focado nos novos testes.

- [ ] **Step 4: Run GREEN**
Run: `python -m unittest infrastructure.pentium.atlas.tests.test_affective_runtime_packaging -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git commit -m "ci(atlas): certificar affective runtime visual"`

---

### Task 7: Integração dashboard + certificação local

**Files:**
- Test: existing dashboard tests plus Atlas affected suites.

**Interfaces:**
- Produces: evidência de que o JSON publicado é aceito sem reclassificação pelo dashboard.

- [ ] **Step 1: Add an integration test if missing**
Gerar `EstadoVisualAtlas`, publicar em temp dir, apontar `dashboard_collectors` para o arquivo e verificar pass-through exato.

- [ ] **Step 2: Run targeted suites**
Run all new Atlas tests, A1/A4 suites and dashboard suite.

- [ ] **Step 3: Run syntax/config checks**
Run `python -m py_compile` on touched Python; parse JSON configs; run `bash -n infrastructure/pentium/atlas/install-user.sh`; run `git diff --check`.

- [ ] **Step 4: Run full Atlas test suite**
Run: `python -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py'`
Expected: PASS.

- [ ] **Step 5: Final commit if integration-only changes exist**
`git commit -m "test(atlas): certificar runtime afetivo visual"`

- [ ] **Step 6: Record exact HEAD evidence**
Capture exact SHA, test counts, branch status and diff cleanliness.
