# Atlas Personal Workspace + Self Work Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a bounded personal workspace for Atlas with autonomous self-work, strong filesystem isolation, provenance, recoverable trash, local retrieval, adaptive token economy, and dashboard observability.

**Architecture:** Atlas never receives a generic filesystem or shell. Cognitive intents route through explicit workspace capabilities into a deterministic WorkspaceBroker rooted at `~/pentium-agent/atlas-workspace`; local indexing/cache/token-governor paths are preferred before Hermes. Self Work is bounded, preemptible by human interaction, and cannot expand infrastructure privileges.

**Tech Stack:** Python 3, pathlib, sqlite3/FTS5, unittest, JSON/JSONL, existing Atlas capability/action/cognitive runtime and Dashboard patterns.

**Spec:** `docs/superpowers/specs/2026-09-12-atlas-personal-workspace-self-work-design.md`

## Global Constraints

- Workspace root is isolated from repositories, secrets, host filesystem, and network effects.
- No shell, executable creation, symlink/hardlink escape, absolute path, or `..` traversal capability exists.
- Default quota: 134217728 bytes; max file: 1048576 bytes; max files: 2048.
- Allowed initial content types: `.md`, `.txt`, `.json`, `.jsonl`, `.csv`.
- `workspace_trash` is AUTO and recoverable; permanent purge requires human confirmation.
- Memory, Continuous Intent, Workspace, and Self Work remain distinct concepts.
- Priority: Human > Incident > Observation > Self Work > Reflection.
- Token economy rule: Local first. Cache second. Retrieval third. LLM last.
- Human interaction must preempt Self Work without losing recoverable state.
- Existing Atlas infrastructure autonomy scope must not expand.
- Each task uses RED -> GREEN -> refactor, focused tests, and a logical commit.

---

### Task 1: Workspace policy and secure path boundary

**Files:**
- Create: `infrastructure/pentium/atlas/workspace_policy.py`
- Test: `infrastructure/pentium/atlas/tests/test_workspace_policy.py`

**Interfaces:**
- Produces: `WorkspacePolicy`, `WorkspacePolicyError`, `resolve_workspace_path(root: Path, area: str, relative_path: str, policy: WorkspacePolicy) -> Path`.
- Enforces allowed areas, extensions, root containment, no absolute paths, no traversal, no symlink escape, file-size/file-count/quota constants.

- [ ] **Step 1: Write failing tests** for valid paths and rejection of absolute paths, `..`, unknown areas, disallowed extensions, and symlink escape.
- [ ] **Step 2: Run** `python -m unittest -v infrastructure.pentium.atlas.tests.test_workspace_policy` and verify RED because the module/API does not exist.
- [ ] **Step 3: Implement minimal policy/path resolver** using `Path.resolve(strict=False)`, explicit area allowlist, suffix allowlist, `os.path.commonpath`, and `lstat`/parent checks that reject symlinks inside the workspace chain.
- [ ] **Step 4: Re-run focused tests** and verify GREEN.
- [ ] **Step 5: Commit** `feat(atlas): add secure workspace boundary`.

### Task 2: Deterministic WorkspaceBroker and provenance

**Files:**
- Create: `infrastructure/pentium/atlas/workspace_broker.py`
- Create: `infrastructure/pentium/atlas/workspace_manifest.py`
- Test: `infrastructure/pentium/atlas/tests/test_workspace_broker.py`

**Interfaces:**
- Consumes: `WorkspacePolicy`, `resolve_workspace_path`.
- Produces: `WorkspaceBroker.status/list/read/write/append/mkdir/move/archive/trash/restore`, `WorkspaceRecord`, append-only audit JSONL and metadata under `.system/`.

- [ ] **Step 1: Write failing tests** proving atomic writes, 0600 files, bounded append, quota/file-count enforcement, provenance fields, recoverable trash, restore, and no permanent delete API.
- [ ] **Step 2: Run focused tests** and verify RED.
- [ ] **Step 3: Implement minimal broker** with temp-file + fsync + replace, 0700 directories, 0600 files, content hashing, manifest/audit writes, and `.trash` relocation metadata.
- [ ] **Step 4: Re-run focused tests** and verify GREEN.
- [ ] **Step 5: Commit** `feat(atlas): add bounded personal workspace broker`.

### Task 3: Local workspace index and progressive retrieval

**Files:**
- Create: `infrastructure/pentium/atlas/workspace_index.py`
- Create: `infrastructure/pentium/atlas/workspace_retriever.py`
- Test: `infrastructure/pentium/atlas/tests/test_workspace_retriever.py`

**Interfaces:**
- Produces: `WorkspaceIndex.upsert/remove/search`, `WorkspaceRetriever.retrieve(query, max_items, max_bytes)`.
- Retrieval order: metadata -> digest -> snippets -> full file only when explicitly requested and within limits.

- [ ] **Step 1: Write failing tests** for FTS lookup, ranking, byte ceilings, stable hashes, and no full-file read for a metadata-sufficient query.
- [ ] **Step 2: Run focused tests** and verify RED.
- [ ] **Step 3: Implement SQLite index** with FTS5 when available and deterministic fallback token matching if FTS5 is unavailable.
- [ ] **Step 4: Implement progressive retrieval** returning reduced records under item/byte ceilings.
- [ ] **Step 5: Re-run tests and commit** `feat(atlas): add local workspace retrieval`.

### Task 4: Persistent workspace context cache

**Files:**
- Create: `infrastructure/pentium/atlas/workspace_context_cache.py`
- Test: `infrastructure/pentium/atlas/tests/test_workspace_context_cache.py`

**Interfaces:**
- Produces: content-addressed cache keyed by content/query/intent/policy-version fingerprints with TTL and bounded entries persisted in SQLite.

- [ ] **Step 1: Write failing tests** for hit/miss, invalidation on hash/policy change, TTL expiry, and persistence across process restart.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement minimal cache** with deterministic SHA-256 keys and bounded LRU metadata.
- [ ] **Step 4: Verify GREEN and commit** `feat(atlas): add persistent workspace context cache`.

### Task 5: Token Budget Governor and zero-token routing

**Files:**
- Create: `infrastructure/pentium/atlas/token_budget_governor.py`
- Create: `infrastructure/pentium/atlas/cognitive_router.py`
- Test: `infrastructure/pentium/atlas/tests/test_token_budget_governor.py`
- Test: `infrastructure/pentium/atlas/tests/test_cognitive_router.py`

**Interfaces:**
- Produces: `TokenBudgetGovernor` modes `NORMAL|CONSERVATIVE|RESTRICTED|HUMAN_ONLY`; `CognitiveRoute` values `DETERMINISTIC|CACHE|RETRIEVAL|LLM|NO_INFERENCE_REQUIRED`.
- Human/incident traffic always outranks Self Work/reflection.

- [ ] **Step 1: Write failing tests** for adaptive pressure modes, priority preservation, Self Work suppression under pressure, unchanged human route, fingerprint no-op, and deterministic workspace status/list routes.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement governor** using explicit per-window counters and estimated/actual token accounting; no network dependency.
- [ ] **Step 4: Implement router** with the rule Local -> Cache -> Retrieval -> LLM and `NO_INFERENCE_REQUIRED` for unchanged non-deadline state.
- [ ] **Step 5: Verify GREEN and commit** `feat(atlas): add adaptive cognitive token economy`.

### Task 6: Context Pack Builder and delta context

**Files:**
- Create: `infrastructure/pentium/atlas/context_pack.py`
- Test: `infrastructure/pentium/atlas/tests/test_context_pack.py`

**Interfaces:**
- Produces: `ContextPackBuilder.build(...)` with normal 3000, complex 6000, emergency 8000 token ceilings; deterministic truncation and delta-first representation.

- [ ] **Step 1: Write failing tests** for ceiling enforcement, stable priority ordering, delta-only unchanged infrastructure, bounded memory/workspace snippets, and human-context retention.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement builder** with deterministic approximate token estimator and explicit section budgets.
- [ ] **Step 4: Verify GREEN and commit** `feat(atlas): add bounded cognitive context packs`.

### Task 7: Workspace capabilities and action executor

**Files:**
- Modify: `infrastructure/pentium/atlas/capability_registry.py`
- Modify: `infrastructure/pentium/atlas/policy_capabilities.py`
- Modify: `infrastructure/pentium/atlas/action_executors.py`
- Create: `infrastructure/pentium/atlas/workspace_capability_executor.py`
- Test: `infrastructure/pentium/atlas/tests/test_workspace_capabilities.py`

**Interfaces:**
- Adds only explicit capabilities: `workspace_status`, `workspace_list`, `workspace_read`, `workspace_search`, `workspace_create_note`, `workspace_write`, `workspace_append`, `workspace_mkdir`, `workspace_move`, `workspace_archive`, `workspace_trash`, `workspace_restore`, `workspace_purge`.
- No generic `filesystem_*`, `shell`, `execute_file`, or external-path capability.

- [ ] **Step 1: Write failing tests** for registry levels, AUTO-safe bounded operations, human-confirmed purge, invalid parameters, and proof that generic filesystem/shell capabilities are absent.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement registry/policy/executor wiring** delegating only to `WorkspaceBroker` methods.
- [ ] **Step 4: Verify GREEN and commit** `feat(atlas): expose bounded workspace capabilities`.

### Task 8: Self Work state machine and human preemption

**Files:**
- Create: `infrastructure/pentium/atlas/self_work.py`
- Modify: `infrastructure/pentium/atlas/continuous_intent_machine.py`
- Modify: `infrastructure/pentium/atlas/behavior_selector.py`
- Test: `infrastructure/pentium/atlas/tests/test_self_work.py`

**Interfaces:**
- Produces states `CANDIDATE|ACTIVE|WORKING|REVIEWING|COMPLETED|PAUSED|ABANDONED|EXPIRED|BLOCKED`.
- One active Self Work item; max autonomous operations and inference budget are explicit; human interaction preempts to PAUSED and resumes only if still valid.

- [ ] **Step 1: Write failing tests** for one-active constraint, state transitions, human preemption, resume, expiration, operation budget, and terminal cleanup.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement minimal state machine** independent of LLM calls.
- [ ] **Step 4: Integrate selector/continuous intent without changing existing infra-action privileges.**
- [ ] **Step 5: Verify GREEN and commit** `feat(atlas): add bounded self work runtime`.

### Task 9: Cognitive runtime integration

**Files:**
- Modify: `infrastructure/pentium/atlas/cognitive_daemon.py`
- Modify: `infrastructure/pentium/atlas/reaction_loop_cognitivo.py`
- Modify: `infrastructure/pentium/atlas/llm_gateway.py`
- Test: `infrastructure/pentium/atlas/tests/test_cognitive_workspace_integration.py`

**Interfaces:**
- Wires router, governor, ContextPackBuilder, workspace retrieval/cache, Self Work, and workspace executor into the existing single cognitive pipeline.

- [ ] **Step 1: Write failing integration tests** proving deterministic requests consume no LLM call, unchanged observations produce no inference, cache/retrieval paths short-circuit, human interaction preempts Self Work, and LLM receives only bounded Context Packs.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement integration** while preserving existing ReactionLoop/Hermes ownership and exception isolation.
- [ ] **Step 4: Verify focused + existing cognitive suites GREEN.**
- [ ] **Step 5: Commit** `feat(atlas): integrate self work cognitive economy`.

### Task 10: Dashboard observability and packaging

**Files:**
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `infrastructure/pentium/dashboard/*` only at existing workspace/health presentation boundaries.
- Test: `infrastructure/pentium/atlas/tests/test_workspace_packaging.py`
- Test: dashboard tests covering new read-only status fields.

**Interfaces:**
- Publishes workspace usage, active Self Work state, last artifact, token mode, LLM calls, avoided calls, cache-hit rate, deterministic-route count, and token totals; dashboard remains read-only.

- [ ] **Step 1: Write failing packaging/dashboard tests.**
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Package new modules/config and expose bounded health/status snapshot.**
- [ ] **Step 4: Add dashboard rendering without write capability.**
- [ ] **Step 5: Verify GREEN and commit** `feat(atlas): expose workspace and token economy observability`.

### Task 11: Adversarial security certification

**Files:**
- Create: `infrastructure/pentium/atlas/workspace_certification.py`
- Test: `infrastructure/pentium/atlas/tests/test_workspace_certification.py`

**Interfaces:**
- Produces fail-closed certification for traversal, symlink escape, executable extension, quota overflow, unauthorized purge, generic shell/filesystem capability absence, and token-budget priority preservation.

- [ ] **Step 1: Write failing adversarial tests** for all prohibited paths/actions.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement certification runner** that reports explicit pass/fail reasons and exact deployed SHA field.
- [ ] **Step 4: Verify GREEN and commit** `test(atlas): certify workspace isolation and autonomy bounds`.

### Task 12: Full verification and exact-HEAD CI gate

**Files:**
- Modify documentation only if verification reveals required operator guidance.

**Interfaces:**
- No new runtime behavior; proves the branch is merge-ready.

- [ ] **Step 1: Run** `python -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py'` and require 0 failures/errors.
- [ ] **Step 2: Run** `python -m unittest discover -s infrastructure/pentium/dashboard/tests -p 'test_*.py'` and require 0 failures/errors.
- [ ] **Step 3: Run** `bash -n infrastructure/pentium/atlas/install-user.sh` plus any new shell packaging scripts and `git diff --check`.
- [ ] **Step 4: Push branch, create PR, and require all applicable CI checks GREEN on the exact HEAD SHA before merge/deploy.
- [ ] **Step 5: Prepare a concise pt-BR checkpoint with diff/commits, exact-HEAD evidence, blockers, and next action.
