# Atlas Continuous Intent v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** adicionar continuidade comportamental ao Atlas sem spam de chat, sem segundo planner e sem segundo owner de memória.

**Architecture:** corrigir primeiro os contratos de foco e lifecycle de inferência; depois adicionar unidades puras `BehaviorSelector`, `ContinuousIntentMachine` e `HabituationEngine`; por fim integrar essas unidades ao `CognitiveDaemon` e ao `ActionPlanner`. M2 continua sendo o único caminho de consolidação episódica.

**Tech Stack:** Python 3.14, unittest, SQLite/M2 existente, systemd user services, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-11-atlas-continuous-intent-v1-design.md`

## Global Constraints

- Base autoritativa: `0f40df545efcc174d656b2b8b72777ec8f9b6948`.
- Exatamente uma intenção ativa por vez.
- Interação humana preempta comportamento passivo.
- Nenhum novo writer direto de `MemoryRecord`.
- Nenhum capability de controle automático criado por intenção passiva.
- Falhas de Continuous Intent não derrubam o loop cognitivo.
- TDD obrigatório e suíte Atlas completa antes de PR.

---
### Task 1: Corrigir refresh de foco e lifecycle real de inferência

**Files:**
- Modify: `infrastructure/pentium/atlas/motor_foco.py`
- Modify: `infrastructure/pentium/atlas/reaction_loop_cognitivo.py`
- Modify: `infrastructure/pentium/atlas/cognitive_daemon.py`
- Test: `infrastructure/pentium/atlas/tests/test_motor_foco.py`
- Test: `infrastructure/pentium/atlas/tests/test_cognitive_inference_lifecycle.py`

**Interfaces:**
- `MotorFoco.atualizar(...) -> FocoAtencao` deve trocar o objeto atual pelo candidato novo do mesmo `assunto_id`.
- `ReactionLoopCognitivo(..., on_inference: Callable[[bool], None] | None)` marca apenas `gateway.inferir()`.

- [ ] Escrever/portar testes que falham no baseline.
- [ ] Rodar os testes e confirmar RED.
- [ ] Implementar o mínimo: refresh do foco e callback em `try/finally` ao redor do gateway.
- [ ] Remover `pensando=True/False` externo do `CognitiveDaemon` e injetar callback no loop.
- [ ] Rodar testes focados e regressões cognitivas.
- [ ] Commit: `fix(atlas): align focus and inference lifecycle`.

### Task 2: Modelo de intenção e BehaviorSelector

**Files:**
- Create: `infrastructure/pentium/atlas/continuous_intent.py`
- Create: `infrastructure/pentium/atlas/behavior_selector.py`
- Test: `infrastructure/pentium/atlas/tests/test_continuous_intent_model.py`
- Test: `infrastructure/pentium/atlas/tests/test_behavior_selector.py`

**Interfaces:**
- `IntentState`: `CANDIDATA`, `ATIVA`, `AGUARDANDO`, `CONCLUIDA`, `CANCELADA`, `EXPIRADA`.
- `IntentType`: `OBSERVAR`, `ACOMPANHAR_RECUPERACAO`, `INTERAGIR_COM_HUMANO`, `ENCERRAR_ACOMPANHAMENTO`.
- `BehaviorSelector.select(snapshot, *, human_interaction: bool, habituation: float) -> BehaviorDecision`.

- [ ] Criar testes RED para validação/bounds e seleção determinística.
- [ ] Implementar dataclasses/enums imutáveis e utility fixa.
- [ ] Garantir que interação humana sempre vença comportamento passivo.
- [ ] Rodar testes focados.
- [ ] Commit: `feat(atlas): add continuous intent model and selector`.
### Task 3: Máquina de estado e habituação

**Files:**
- Create: `infrastructure/pentium/atlas/continuous_intent_machine.py`
- Create: `infrastructure/pentium/atlas/habituation_engine.py`
- Test: `infrastructure/pentium/atlas/tests/test_continuous_intent_machine.py`
- Test: `infrastructure/pentium/atlas/tests/test_habituation_engine.py`

**Interfaces:**
- `ContinuousIntentMachine.update(decision, snapshot, *, now, human_interaction=False) -> IntentTransition`.
- `HabituationEngine.evaluate(intent, material_fingerprint, *, terminal=False) -> HabituationDecision`.

- [ ] Testar RED: ativação, preempção, retomada, conclusão, cancelamento e TTL.
- [ ] Testar RED: primeira mensagem permitida, equivalentes suprimidos, mudança material renova e terminal permite uma vez.
- [ ] Implementar estado único, sem persistência própria, com TTL bounded.
- [ ] Implementar habituação bounded por `intencao_id + assunto_id`.
- [ ] Rodar testes focados.
- [ ] Commit: `feat(atlas): add continuous intent state and habituation`.

### Task 4: Integração cognitiva e presença silenciosa

**Files:**
- Modify: `infrastructure/pentium/atlas/cognitive_daemon.py`
- Modify: `infrastructure/pentium/atlas/action_planner.py`
- Create: `infrastructure/pentium/atlas/continuous_intent_publisher.py`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Test: `infrastructure/pentium/atlas/tests/test_cognitive_continuous_intent.py`
- Test: `infrastructure/pentium/atlas/tests/test_action_planner.py`
- Test: `infrastructure/pentium/atlas/tests/test_continuous_intent_packaging.py`

**Interfaces:**
- Daemon avalia intenção antes do `ReactionLoop`, mas não substitui ActivationPolicy.
- Acompanhamento habituado pode produzir plano visual sem `CHAT_REPLY`.
- `continuous-intent.json` é observabilidade apenas; não é fonte de verdade no boot.

- [ ] Criar testes RED para first notify, silent tracking, human preemption e completion.
- [ ] Integrar selector/machine/habituation com fallback fail-safe.
- [ ] Estender planner com `communication_mode` (`normal`, `silent_tracking`, `terminal`) sem bypassar ActionPolicy.
- [ ] Publicar estado bounded atomicamente em `continuous-intent.json`.
- [ ] Empacotar novos módulos sem ativar Voice/Discord.
- [ ] Rodar regressões cognitivas/action/packaging.
- [ ] Commit: `feat(atlas): integrate continuous behavior runtime`.
### Task 5: Replay determinístico e M2 contract

**Files:**
- Create: `infrastructure/pentium/atlas/tests/test_continuous_behavior_replay.py`
- Modify only if required by tests: M2 adapter metadata path already approved by spec.

**Acceptance replay:**
1. core degraded;
2. foco core;
3. intenção `ACOMPANHAR_RECUPERACAO` ativa;
4. uma mensagem inicial;
5. cinco ciclos equivalentes;
6. zero mensagens adicionais e presença visual mantida;
7. chat humano preempta e depois retoma;
8. core recupera;
9. uma mensagem terminal;
10. nenhuma intenção órfã e no máximo uma memória episódica consolidada.

- [ ] Escrever replay RED de 10 snapshots.
- [ ] Corrigir apenas lacunas demonstradas pelo replay.
- [ ] Rodar replay e M2 tests.
- [ ] Commit: `test(atlas): certify continuous behavior replay`.

### Task 6: Certificação da branch

**Files:**
- Modify: `.github/workflows/foundation-ci.yml` somente se o novo teste não estiver coberto pelo discovery existente.

- [ ] `git diff --check`.
- [ ] Rodar todos os testes Atlas via unittest discovery.
- [ ] Confirmar 0 failures e registrar contagem exata.
- [ ] Push da branch e abrir PR.
- [ ] Verificar checks do HEAD exato; nenhum merge enquanto pending/RED.
- [ ] Merge somente all-GREEN.
- [ ] Criar pacote do merge SHA, backup físico, deploy Pentium.
- [ ] Smoke real: serviços active, health healthy, continuous-intent observable e chat preemption funcional.
- [ ] Não fabricar incidente/memória no banco real; replay físico deve usar estado temporário.
