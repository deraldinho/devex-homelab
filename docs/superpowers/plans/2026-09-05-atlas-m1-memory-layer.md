# Atlas M1 Memory Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar memória L0–L3 persistente, bounded e com gerenciamento automático de pressão para o Atlas.

**Architecture:** SQLite local guarda registros versionados. MemoryManager aplica retenção/compactação deterministicamente; MemoryRetriever entrega apenas seleção bounded ao ContextoCognitivoBuilder. A LLM nunca grava nem apaga memória diretamente.

**Tech Stack:** Python stdlib, sqlite3, unittest, JSON, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-05-atlas-memory-layer-context-manager-design.md`

## Global Constraints

- Base exata: C5 `dbff174b8f147511e813347e7f71aa9f979c9a8c`.
- Pressão: 70%, 85%, 95%, 100%.
- Memórias protegidas/pinned nunca são removidas automaticamente.
- Sem vector DB no v1.
- Sem escrita/deleção direta pela LLM.
- ContextoCognitivo global permanece limitado a 8192 bytes.

---

### Task 1: Contratos de memória e SQLite store

**Files:** criar `memory_model.py`, `memory_store.py`; testar `test_memory_model.py`, `test_memory_store.py`.

**Interfaces:** `MemoryRecord`, `MemoryLayer`, `MemoryStore.save/get/list/delete/count/size_bytes`.

- [ ] Escrever testes RED para validação L0–L3, bounds, schema e round-trip SQLite.
- [ ] Confirmar RED por módulos ausentes.
- [ ] Implementar contratos imutáveis e schema SQLite v1.
- [ ] Confirmar GREEN e restart/round-trip.
- [ ] Commitar a tarefa.
### Task 2: MemoryManager e pressão automática

**Files:** criar `memory_manager.py`; testar `test_memory_manager.py`.

**Interfaces:** `MemoryPolicy`, `MemoryPressure`, `MemoryManager.maintain()`, `MemoryManager.remember()`.

- [ ] Escrever testes RED para 70/85/95/100%, expiração, dedupe, proteção e fail-safe.
- [ ] Confirmar RED.
- [ ] Implementar score determinístico, limpeza e eviction controlada.
- [ ] Garantir transação para consolidação antes de apagar originais.
- [ ] Confirmar GREEN e commit.

### Task 3: Retrieval bounded e contexto cognitivo

**Files:** criar `memory_retriever.py`; modificar `modelo_contexto_cognitivo.py`, `contexto_cognitivo.py`, `config_cognitiva.json`; testar retrieval e builder.

**Interfaces:** `MemoryRetriever.retrieve(...) -> tuple[dict,...]`; `ContextoCognitivo.memorias_relevantes`.

- [ ] Escrever testes RED para ranking, quantidade, bytes e remoção sob payload pressure.
- [ ] Confirmar RED.
- [ ] Implementar retrieval estruturado e integração no builder.
- [ ] Confirmar que a LLM recebe somente a visão reduzida.
- [ ] Confirmar GREEN e commit.

### Task 4: Empacotamento, CI e regressão

**Files:** modificar `install-user.sh`, `.github/workflows/foundation-ci.yml`; criar teste de empacotamento M1.

- [ ] Escrever teste RED do marker `DEVEX_HOMELAB_ATLAS_MEMORY_M1_PASS`.
- [ ] Integrar módulos/config ao installer e py_compile do CI.
- [ ] Rodar testes M1, full Atlas, py_compile, JSON, bash -n e git diff --check.
- [ ] Verificar ausência de shell/rede/segredos na implementação M1.
- [ ] Commitar, publicar PR empilhada em C5 e aguardar CI do HEAD exato.