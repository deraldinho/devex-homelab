# Atlas Dashboard Chat + PlanoAcaoAtlas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar o dashboard o canal operacional da Atlas, com chat, plano explícito de ações, lifecycle observável e reflexo visual seguro de cada decisão.

**Architecture:** O dashboard aceita mensagens e grava uma inbox bounded; o `atlas-cognitive.service` é o único owner do ciclo cognitivo, consome a inbox, produz `PlanoAcaoAtlas`, aplica policy e executores especializados e publica estado/histórico/eventos. O dashboard lê os artefatos runtime e usa SSE apenas para atualização incremental, mantendo `/api/status` como reconciliação autoritativa.

**Tech Stack:** Python 3, `http.server`, Unix/runtime files, JSON/JSONL bounded, SSE, PixiJS, unittest, systemd user services.

**Spec:** `docs/superpowers/specs/2026-09-08-atlas-dashboard-chat-action-plan-design.md`

## Global Constraints

- Qwen nunca controla PixiJS diretamente.
- Qwen nunca executa shell arbitrário.
- Toda ação semântica passa por `PlanoAcaoAtlas` e policy.
- `EstadoVisualAtlas` permanece a fronteira canônica do renderer.
- Voice permanece pausado; `SPEAK_TTS` deve terminar `BLOCKED reason=voice_paused`.
- Runtime files são bounded; estado corrente usa escrita atômica.
- Dashboard continua LAN-only em `192.168.88.3:8765`.
- Não expor chain-of-thought, prompt interno, memória bruta, segredos ou parâmetros sensíveis.
- Implementação e validação em TDD; certificação final exige mesmo SHA no x99/Pentium.

---
### Task 1: Modelo `PlanoAcaoAtlas` e lifecycle

**Files:**
- Create: `infrastructure/pentium/atlas/action_plan.py`
- Test: `infrastructure/pentium/atlas/tests/test_action_plan.py`

**Interfaces:**
- Produces: `ActionType`, `ActionStatus`, `AtlasAction`, `PlanoAcaoAtlas`, `transition_action(action, target_status, *, reason=None, at=None)`.
- `ActionType`: `CHAT_REPLY`, `LOOK_AT`, `SET_EXPRESSION`, `SET_GESTURE`, `SET_POSTURE`, `SPEAK_TTS`, `CAPABILITY_REQUEST`, `WAIT`.
- `ActionStatus`: `PLANNED`, `AUTHORIZED`, `EXECUTING`, `COMPLETED`, `BLOCKED`, `FAILED`, `CANCELLED`.

- [ ] **Step 1: Write failing model/lifecycle tests**

```python
plan = PlanoAcaoAtlas.create(stimulus_id="s1", objective="responder", confidence=.8, response_text="oi", actions=[AtlasAction.create(ActionType.CHAT_REPLY)])
self.assertEqual(ActionStatus.PLANNED, plan.actions[0].status)
self.assertEqual(ActionStatus.AUTHORIZED, transition_action(plan.actions[0], ActionStatus.AUTHORIZED).status)
with self.assertRaises(ValueError): transition_action(plan.actions[0], ActionStatus.COMPLETED)
```

- [ ] **Step 2: Run RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_action_plan -v`  
Expected: import/module failure.

- [ ] **Step 3: Implement immutable validated model**

Require UUID-like non-empty IDs, timezone-aware timestamps, confidence `0..1`, bounded text, action-specific parameter allowlists and legal transition graph.

- [ ] **Step 4: Run GREEN and full Atlas tests**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_action_plan -v` then Atlas discovery.

- [ ] **Step 5: Commit**

`git commit -m "feat(atlas): definir plano de acoes e lifecycle"`
### Task 2: Persistência bounded de planos e eventos

**Files:**
- Create: `infrastructure/pentium/atlas/action_plan_store.py`
- Test: `infrastructure/pentium/atlas/tests/test_action_plan_store.py`

**Interfaces:**
- Consumes: `PlanoAcaoAtlas` from Task 1.
- Produces: `ActionPlanStore(current_path, history_path, max_history=64, max_bytes=131072)`, `save_current(plan)`, `append_terminal(plan)`, `load_current()`.

- [ ] **Step 1: Write failing persistence tests**

```python
store.save_current(plan)
self.assertEqual(plan.plan_id, store.load_current().plan_id)
for i in range(80): store.append_terminal(make_plan(i))
self.assertLessEqual(len(history_lines()), 64)
self.assertNotIn("secret", history_path.read_text())
```

- [ ] **Step 2: Run RED**

Run: `python -m unittest infrastructure.pentium.atlas.tests.test_action_plan_store -v`  
Expected: module missing.

- [ ] **Step 3: Implement atomic current state and bounded JSONL history**

Current state uses tmp + fsync + `os.replace`; history is rewritten to the newest bounded records after validating/sanitizing payloads.

- [ ] **Step 4: Run GREEN and Atlas discovery**

- [ ] **Step 5: Commit**

`git commit -m "feat(atlas): persistir planos de acao bounded"`

### Task 3: Planner determinístico da resposta cognitiva

**Files:**
- Create: `infrastructure/pentium/atlas/action_planner.py`
- Modify: `infrastructure/pentium/atlas/reaction_loop_cognitivo.py`
- Test: `infrastructure/pentium/atlas/tests/test_action_planner.py`

**Interfaces:**
- Consumes: `RespostaCognitiva`, `CognitiveObservationSnapshot`/context metadata.
- Produces: `ActionPlanner.plan(stimulus_id, entity_id, response) -> PlanoAcaoAtlas`.
- Planner does not accept arbitrary renderer commands; it maps structured semantics to allowlisted actions.

- [ ] **Step 1: Write failing planner tests**

```python
plan = planner.plan("s1", "x99", response(texto="Estou verificando.", resumo="mudanca", confianca=.8))
self.assertEqual(ActionType.CHAT_REPLY, plan.actions[0].type)
self.assertIn(ActionType.LOOK_AT, [a.type for a in plan.actions])
self.assertNotIn("shell", json.dumps(plan.to_dict()).lower())
```

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Implement minimal mapping**

Rules: textual response -> `CHAT_REPLY`; known entity -> `LOOK_AT`; emotion/motivo maps to allowlisted expression/gesture; requested TTS -> `SPEAK_TTS`; existing structured capability intent -> `CAPABILITY_REQUEST` with only non-sensitive validated parameters.

- [ ] **Step 4: Run GREEN + reaction-loop regression suites**

- [ ] **Step 5: Commit**

`git commit -m "feat(atlas): derivar plano de acoes da cognicao"`
### Task 4: Policy e executores especializados

**Files:**
- Create: `infrastructure/pentium/atlas/action_policy.py`
- Create: `infrastructure/pentium/atlas/action_executors.py`
- Modify: `infrastructure/pentium/atlas/modelo_visual_atlas.py`
- Test: `infrastructure/pentium/atlas/tests/test_action_execution.py`

**Interfaces:**
- Consumes: `PlanoAcaoAtlas`, `PolicyCapabilities`, current `EstadoVisualAtlas`.
- Produces: `ActionPolicy.authorize(plan, *, voice_enabled=False) -> PlanoAcaoAtlas` and `ActionExecutorRegistry.execute(plan) -> PlanoAcaoAtlas`.
- Visual executor writes semantic updates through `EstadoVisualAtlas`; chat executor publishes a chat event; TTS executor is policy-blocked while Voice is paused.

- [ ] **Step 1: Write failing authorization/execution tests**

```python
authorized = policy.authorize(plan, voice_enabled=False)
self.assertEqual(ActionStatus.BLOCKED, action_of(authorized, ActionType.SPEAK_TTS).status)
self.assertEqual("voice_paused", action_of(authorized, ActionType.SPEAK_TTS).reason)
executed = registry.execute(authorized)
self.assertEqual("x99", visual_state.foco_visual)
self.assertEqual(ActionStatus.COMPLETED, action_of(executed, ActionType.LOOK_AT).status)
```

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Implement policy and executors**

Visual parameters are enums/allowlists only; `CAPABILITY_REQUEST` delegates to existing `PolicyCapabilities` and is never shell. Execution failures set only that action to `FAILED` and continue independent actions.

- [ ] **Step 4: Run GREEN + visual/capability regression tests**

- [ ] **Step 5: Commit**

`git commit -m "feat(atlas): autorizar e executar acoes semanticas"`

### Task 5: Runtime owner do plano e lifecycle observável

**Files:**
- Modify: `infrastructure/pentium/atlas/cognitive_daemon.py`
- Modify: `infrastructure/pentium/atlas/cognitive_observability.py`
- Test: `infrastructure/pentium/atlas/tests/test_cognitive_action_runtime.py`

**Interfaces:**
- Consumes: planner, policy, executor registry, `ActionPlanStore`.
- Produces lifecycle events `plan_created`, `action_status`, `visual_action`, `runtime_error` and terminal persisted plan.

- [ ] **Step 1: Write failing end-to-end daemon test**

```python
result = daemon.run_once()
plan = store.load_current()
self.assertEqual(result.texto, plan.response_text)
self.assertEqual(["plan_created", "action_status"], event_types()[:2])
self.assertTrue(any(a.status in TERMINAL for a in plan.actions))
```

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Wire planner -> policy -> executors after cognitive result**

Publish each transition before/after execution; preserve cognitive `DEGRADADA` behavior when no valid plan can be produced.

- [ ] **Step 4: Run GREEN + full Atlas discovery**

- [ ] **Step 5: Commit**

`git commit -m "feat(atlas): integrar lifecycle de acoes ao runtime cognitivo"`
### Task 6: Inbox de chat bounded e idempotente

**Files:**
- Create: `infrastructure/pentium/atlas/chat_inbox.py`
- Modify: `infrastructure/pentium/atlas/human_interaction.py`
- Test: `infrastructure/pentium/atlas/tests/test_chat_inbox.py`

**Interfaces:**
- Produces: `ChatInbox(path, max_items=32, max_message_chars=512)`, `enqueue(message, client_message_id) -> ChatEnvelope`, `claim_next()`, `ack(message_id)`.
- `ChatEnvelope` contains only bounded text, IDs and timestamps.

- [ ] **Step 1: Write failing bounded/idempotency tests**

```python
first = inbox.enqueue("Como esta o x99?", "client-1")
second = inbox.enqueue("Como esta o x99?", "client-1")
self.assertEqual(first.message_id, second.message_id)
self.assertEqual(1, inbox.pending_count())
with self.assertRaises(ValueError): inbox.enqueue("x" * 513, "client-2")
```

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Implement atomic bounded inbox**

Use a single current JSON file with atomic replace to avoid concurrent JSONL writers between dashboard and cognitive service; claimed/acked messages remain bounded and idempotent.

- [ ] **Step 4: Run GREEN + human interaction tests**

- [ ] **Step 5: Commit**

`git commit -m "feat(atlas): adicionar inbox bounded para chat"`

### Task 7: Cognitive daemon consumes dashboard chat

**Files:**
- Modify: `infrastructure/pentium/atlas/cognitive_daemon.py`
- Modify: `infrastructure/pentium/atlas/human_interaction.py`
- Test: `infrastructure/pentium/atlas/tests/test_cognitive_chat_runtime.py`

**Interfaces:**
- Consumes: `ChatInbox.claim_next()` and existing cognitive context/provider.
- Produces: human-interaction cognitive cycles whose `stimulus_id` maps back to `message_id`, then plans/actions from Tasks 3-5.

- [ ] **Step 1: Write failing chat-to-plan test**

```python
inbox.enqueue("Olhe para o x99 e me diga como ele esta", "client-9")
daemon.run_once()
plan = store.load_current()
self.assertEqual("human_interaction", plan.trigger_kind)
self.assertTrue(any(a.type is ActionType.CHAT_REPLY for a in plan.actions))
self.assertTrue(any(a.type is ActionType.LOOK_AT for a in plan.actions))
```

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Consume at most one human message per cognitive iteration**

Human interaction has priority over periodic reflection but does not bypass policy. Ack only after the cycle reaches a durable observable terminal/result state; failures leave an observable retry/error state without unbounded retries.

- [ ] **Step 4: Run GREEN + full Atlas discovery**

- [ ] **Step 5: Commit**

`git commit -m "feat(atlas): conectar chat ao runtime cognitivo"`
### Task 8: Event store bounded e SSE replayável

**Files:**
- Create: `infrastructure/pentium/dashboard/dashboard_event_store.py`
- Modify: `infrastructure/pentium/dashboard/atlas_dashboard.py`
- Test: `infrastructure/pentium/dashboard/tests/test_dashboard_sse.py`

**Interfaces:**
- Produces: `DashboardEventStore(path, max_events=128, max_bytes=262144)`, `append(type, payload)`, `after(last_event_id)`.
- HTTP: `GET /api/stream` with `text/event-stream`, monotonically increasing event IDs and `Last-Event-ID` replay.

- [ ] **Step 1: Write failing event-store and SSE tests**

```python
store.append("plan_created", {"plan_id":"p1"})
store.append("action_status", {"action_id":"a1","status":"EXECUTING"})
self.assertEqual([2], [e.id for e in store.after(1)])
status, headers, body = self.request("GET", "/api/stream", headers={"Last-Event-ID":"1"})
self.assertEqual(200, status)
self.assertIn("text/event-stream", headers["Content-Type"])
self.assertIn(b"id: 2", body)
```

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Implement bounded append/replay and SSE heartbeat**

No unbounded in-memory subscriber queue. Slow/disconnected clients reconnect using last ID; `/api/status` remains recovery truth.

- [ ] **Step 4: Run GREEN + dashboard server tests**

- [ ] **Step 5: Commit**

`git commit -m "feat(dashboard): adicionar stream SSE bounded"`

### Task 9: `POST /api/chat` bounded e idempotente

**Files:**
- Modify: `infrastructure/pentium/dashboard/atlas_dashboard.py`
- Create: `infrastructure/pentium/dashboard/dashboard_chat.py`
- Test: `infrastructure/pentium/dashboard/tests/test_dashboard_chat_api.py`

**Interfaces:**
- Consumes: shared runtime `ChatInbox` format from Task 6.
- HTTP request: JSON `{message: str, client_message_id: str}`.
- HTTP response: `202 {message_id, stimulus_id, plan_pending: true}`; duplicate client ID returns same IDs.

- [ ] **Step 1: Write failing HTTP tests**

```python
status, _, body = self.request_json("POST", "/api/chat", {"message":"Oi Atlas", "client_message_id":"c1"})
self.assertEqual(202, status)
first = json.loads(body)
second = json.loads(self.request_json("POST", "/api/chat", {"message":"Oi Atlas", "client_message_id":"c1"})[2])
self.assertEqual(first["message_id"], second["message_id"])
self.assertEqual(413, self.request_json("POST", "/api/chat", {"message":"x"*513,"client_message_id":"c2"})[0])
```

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Implement route-specific POST only**

All other POST routes remain `405`; enforce content type, body byte bound, exact fields, text bound and idempotency. Do not invoke Qwen from request thread.

- [ ] **Step 4: Run GREEN + full Dashboard discovery**

- [ ] **Step 5: Commit**

`git commit -m "feat(dashboard): adicionar endpoint de chat Atlas"`
### Task 10: UI Chat + Plano/Decisão + Timeline operacional

**Files:**
- Modify: `infrastructure/pentium/dashboard/dashboard.html`
- Modify: `infrastructure/pentium/dashboard/dashboard_collectors.py`
- Test: `infrastructure/pentium/dashboard/tests/test_dashboard_chat_ui.py`
- Test: `infrastructure/pentium/dashboard/tests/test_dashboard_inline_js.py`

**Interfaces:**
- Consumes: `/api/status`, `/api/chat`, `/api/stream`.
- UI IDs: `atlasChatHistory`, `atlasChatInput`, `atlasChatSend`, `actionPlanObjective`, `actionPlanConfidence`, `actionPlanActions`, `operationalTimeline`.

- [ ] **Step 1: Write failing UI contract tests**

```python
html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
for token in ("atlasChatHistory","atlasChatInput","atlasChatSend","actionPlanActions","operationalTimeline","EventSource('/api/stream')"):
    self.assertIn(token, html)
self.assertNotIn("chain-of-thought", html.lower())
```

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Implement chat interaction and live rendering**

POST uses generated `client_message_id`; message enters UI as pending; SSE updates delivery/plan/action state; polling every 2s remains reconciliation fallback. Render action status separately from planned content.

- [ ] **Step 4: Run GREEN, inline `node --check`, full Dashboard discovery**

- [ ] **Step 5: Commit**

`git commit -m "feat(dashboard): integrar chat e plano de acoes"`

### Task 11: Motion Engine reflects semantic actions

**Files:**
- Modify: `infrastructure/pentium/dashboard/atlas-avatar-engine.js`
- Modify: `infrastructure/pentium/dashboard/atlas-avatar-motion.js`
- Modify: `infrastructure/pentium/atlas/modelo_visual_atlas.py`
- Test: `infrastructure/pentium/dashboard/tests/test_avatar_action_reflection.py`

**Interfaces:**
- Consumes only canonical visual fields produced by `VisualActionExecutor`.
- Produces visible gesture/posture/look/expression transitions while preserving basal breathing/blink/saccades.

- [ ] **Step 1: Write failing semantic reflection tests**

```python
engine = read_engine()
self.assertIn("SET_GESTURE", visual_mapping_contract())
self.assertIn("arm_side", visual_state_schema())
self.assertIn("semanticPosture", engine)
```

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Extend visual contract minimally**

Add explicit safe semantic fields only where existing `gesto_atual` is insufficient (e.g. arm side/posture). Engine maps those values to articulated limbs; LLM never supplies angles or Pixi coordinates.

- [ ] **Step 4: Run GREEN + Node checks + Motion/Dashboard suites**

- [ ] **Step 5: Commit**

`git commit -m "feat(atlas): refletir acoes semanticas no avatar"`

### Task 12: Segurança, boundedness e falhas

**Files:**
- Test: `infrastructure/pentium/atlas/tests/test_action_security.py`
- Test: `infrastructure/pentium/dashboard/tests/test_dashboard_chat_security.py`
- Modify only files needed to satisfy these tests.

**Interfaces:**
- Verifies all public/runtime boundaries from the spec.

- [ ] **Step 1: Write failing adversarial tests**

Cover shell-like chat text as inert text, forbidden action type rejection, sensitive capability parameter omission, oversized SSE/history trimming, Qwen unavailable -> no invented plan, TTS -> blocked, and malformed runtime files -> degraded/recoverable.

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Implement only missing guards**

Do not add generic command execution or new control permissions.

- [ ] **Step 4: Run GREEN + full Atlas/Dashboard suites**

- [ ] **Step 5: Commit**

`git commit -m "test(atlas): endurecer chat e plano de acoes"`
### Task 13: Packaging, CI e deploy idempotente

**Files:**
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `infrastructure/pentium/dashboard/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`
- Modify: `.github/workflows/atlas-avatar-ci.yml`
- Test: existing packaging tests plus new assertions in relevant suites.

**Interfaces:**
- Packages new Python modules and runtime paths; does not enable Voice.
- CI markers include action-plan/chat tests on the exact HEAD.

- [ ] **Step 1: Write failing packaging assertions**

Assert installers include new modules/assets, cognitive service remains owner, dashboard restarts cleanly, and no `enable/restart atlas-voice.service` appears.

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Update installers/workflows**

Keep service ownership unchanged: Observation + Cognitive + Dashboard active, Voice disabled/inactive.

- [ ] **Step 4: Run local syntax/tests**

Run Python compile, Node checks, `bash -n` on Linux/Pentium, `git diff --check`.

- [ ] **Step 5: Commit**

`git commit -m "ci(atlas): certificar chat e plano de acoes"`

### Task 14: Physical certification on the exact SHA

**Files:**
- No product-code edits after final SHA unless a new SHA is created and all gates rerun.
- Update PR checkpoint only after evidence exists.

**Interfaces:**
- Pentium runtime must use the same final SHA in `observation.env` and `runtime/deploy/current-sha`.

- [ ] **Step 1: Run full local verification on final HEAD**

Run Atlas discovery, Dashboard discovery, `py_compile`, Node syntax, `git diff --check`, installer syntax.

- [ ] **Step 2: Push final HEAD and require both CI workflows GREEN on that SHA**

Record workflow run IDs and conclusions.

- [ ] **Step 3: Deploy exact archive/content to Pentium**

Update expected/deploy SHA, install/restart Observation, Cognitive and Dashboard only. Verify Voice remains inactive/disabled.

- [ ] **Step 4: Execute physical chat smoke from x99 Edge**

Send a chat message such as `Olhe para o x99 e me diga o que esta fazendo.` Verify `202`, stimulus creation, plan creation, action lifecycle, chat response, visible look/expression/gesture, timeline entries and SSE reconnect.

- [ ] **Step 5: Verify blocked TTS path**

When a plan contains `SPEAK_TTS`, require dashboard evidence `BLOCKED reason=voice_paused` and confirm Voice service was not started.

- [ ] **Step 6: Capture final PR checkpoint**

Include exact SHA, local test counts, CI run IDs, physical service/socket evidence, chat/plan/action smoke and remaining blockers. Do not merge unless explicitly requested.
