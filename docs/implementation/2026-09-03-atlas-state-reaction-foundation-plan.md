# Atlas State & Reaction Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a primeira vertical funcional do Atlas no Pentium: receber sinais observados, calcular `global_state`/`intensity`, selecionar uma reação semântica variada e registrar a transição em JSONL, sem LLM, áudio físico ou ações remotas.

**Architecture:** O Atlas não coleta rede nem executa shell nesta slice. Ele consome sinais já normalizados pelos contratos existentes de network/heartbeat/agent, interpreta severidade de forma determinística e produz uma decisão de reação desacoplada da mídia. `reaction_engine.py` seleciona IDs semânticos; um Audio Engine posterior fará playback real.

**Tech Stack:** Python 3 stdlib, `unittest`, JSON/JSONL, GitHub Actions.

**Spec:** `docs/implementation/2026-09-03-atlas-state-reaction-foundation-design.md`

## Global Constraints

- Base funcional: `93527d7f54a78f9fbf59a89a272bba8e22d234c9` ou descendente certificado.
- Issue autoritativa: #20.
- Nenhuma LLM, STT, TTS ou reprodução de áudio nesta slice.
- Nenhuma rede, SSH, Tailscale, MikroTik ou subprocesso nesta slice.
- Nenhuma mídia de terceiros, URL executável, secret, chave ou token no Git.
- Estado técnico deve ser determinístico; memes são somente camada secundária de expressão.
- `critical` nunca pode ser substituído por meme ou silêncio.
- TDD obrigatório: teste RED observado antes de cada implementação GREEN.
- PR permanece Draft até CI GREEN no HEAD exato e checkpoint.

---
### Task 1: Congelar o modelo de estado do Atlas

**Files:**
- Create: `infrastructure/pentium/atlas/state_model.py`
- Create: `infrastructure/pentium/atlas/tests/test_state_model.py`

**Interfaces:**
- Produces: `TechnicalState`, `Signal`, `GlobalAssessment`, `ReactionDecision`.
- `Signal(source: str, state: TechnicalState, intensity: int, required: bool=True, reason: str="")`.
- `GlobalAssessment(previous_state, state, intensity, reasons, recovered=False)`.
- `ReactionDecision(category, reaction_id, meme_id=None, suppressed=False)`.

- [ ] **Step 1:** criar testes para enum completo, clamp de intensidade `0..4` e estruturas imutáveis/serializáveis.
- [ ] **Step 2:** rodar `python -m unittest infrastructure.pentium.atlas.tests.test_state_model -v` e confirmar RED por ausência de `state_model.py`.
- [ ] **Step 3:** implementar somente enums/dataclasses necessários aos testes, sem I/O.
- [ ] **Step 4:** rodar novamente o teste e confirmar GREEN.
- [ ] **Step 5:** rodar `python -m py_compile infrastructure/pentium/atlas/state_model.py`.
- [ ] **Step 6:** commit `feat(atlas): define canonical state model`.

### Task 2: Implementar Health Engine determinístico

**Files:**
- Create: `infrastructure/pentium/atlas/health_engine.py`
- Create: `infrastructure/pentium/atlas/tests/test_health_engine.py`

**Interfaces:**
- Consumes: `Signal`, `TechnicalState`, `GlobalAssessment`.
- Produces: `assess(signals: list[Signal], previous_state: TechnicalState | None) -> GlobalAssessment`.
- [ ] **Step 1:** escrever testes para precedência `critical > stressed > degraded > busy > active > healthy`, componente opcional degradado e `recovered` apenas em transição de problema para normal.
- [ ] **Step 2:** rodar `python -m unittest infrastructure.pentium.atlas.tests.test_health_engine -v` e confirmar RED por ausência de `health_engine.py`.
- [ ] **Step 3:** implementar tabela explícita de severidade e agregação sem chamadas externas.
- [ ] **Step 4:** garantir que `intensity` seja o máximo relevante limitado a `0..4` e que `reasons` preserve origem/causa.
- [ ] **Step 5:** rodar testes do Health Engine e depois `python -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v`.
- [ ] **Step 6:** commit `feat(atlas): add deterministic global health engine`.

### Task 3: Implementar configuração e Reaction Engine

**Files:**
- Create: `infrastructure/pentium/atlas/config.json`
- Create: `infrastructure/pentium/atlas/reaction_engine.py`
- Create: `infrastructure/pentium/atlas/tests/test_reaction_engine.py`

**Interfaces:**
- Consumes: `GlobalAssessment`, `ReactionDecision`.
- Produces: `ReactionEngine(config: dict, rng, clock)` e `decide(assessment, recent_ids: tuple[str, ...]) -> ReactionDecision`.
- Config contém `mode`, `anti_repeat_window`, `cooldowns`, `reaction_pools` e `memes_enabled`.

- [ ] **Step 1:** escrever testes RED para seleção determinística por RNG injetado, pesos, anti-repeat, cooldown, pool vazio, meme opcional e reação crítica canônica.
- [ ] **Step 2:** validar RED com `python -m unittest infrastructure.pentium.atlas.tests.test_reaction_engine -v`.
- [ ] **Step 3:** criar `config.json` mínimo com IDs semânticos, sem caminhos de mídia ou URLs.
- [ ] **Step 4:** implementar seleção ponderada usando apenas `random.Random` injetável e clock injetável.
- [ ] **Step 5:** implementar regra: `critical` sempre retorna categoria/reaction_id crítica; `meme_id`, se houver, é secundário.
- [ ] **Step 6:** validar `python -m json.tool infrastructure/pentium/atlas/config.json` e toda a suíte Atlas.
- [ ] **Step 7:** commit `feat(atlas): add semantic reaction engine`.
### Task 4: Implementar journal append-only

**Files:**
- Create: `infrastructure/pentium/atlas/journal.py`
- Create: `infrastructure/pentium/atlas/tests/test_journal.py`

**Interfaces:**
- Consumes: `GlobalAssessment`, `ReactionDecision`.
- Produces: `append_event(path: Path, timestamp: str, assessment: GlobalAssessment, decision: ReactionDecision) -> None`.

- [ ] **Step 1:** escrever teste que grava duas linhas JSONL, reabre o arquivo e valida cada linha individualmente com `json.loads`.
- [ ] **Step 2:** escrever teste para diretório inexistente e erro de escrita controlado.
- [ ] **Step 3:** rodar `python -m unittest infrastructure.pentium.atlas.tests.test_journal -v` e confirmar RED.
- [ ] **Step 4:** implementar criação do diretório pai, append UTF-8, uma linha por evento e `flush()` antes de fechar.
- [ ] **Step 5:** garantir campos `timestamp`, `previous_state`, `state`, `intensity`, `reasons`, `reaction_category`, `reaction_id`, `meme_id`.
- [ ] **Step 6:** rodar toda a suíte Atlas e confirmar GREEN.
- [ ] **Step 7:** commit `feat(atlas): add append-only reaction journal`.

### Task 5: Implementar CLI de avaliação

**Files:**
- Create: `infrastructure/pentium/atlas/cli.py`
- Create: `infrastructure/pentium/atlas/tests/test_cli.py`
- Modify: `infrastructure/pentium/atlas/config.json`

**Interfaces:**
- Consumes: snapshot JSON por arquivo ou stdin.
- Produces: JSON estável em stdout; exit `0` sucesso, `2` input/config inválido, `3` erro de journal.
- Snapshot inicial: `{ "previous_state": "healthy", "signals": [{"source":"core","state":"busy","intensity":1,"required":true,"reason":"core.cpu.high"}] }`.
- [ ] **Step 1:** escrever testes de CLI para snapshot válido, schema inválido, estado desconhecido e saída JSON estável.
- [ ] **Step 2:** rodar `python -m unittest infrastructure.pentium.atlas.tests.test_cli -v` e confirmar RED.
- [ ] **Step 3:** implementar parser estrito, conversão para `Signal`, chamada `assess()`, `ReactionEngine.decide()` e journal opcional.
- [ ] **Step 4:** implementar resumo humano ASCII opcional sem caracteres dependentes de codepage.
- [ ] **Step 5:** rodar teste da CLI e toda a suíte Atlas.
- [ ] **Step 6:** executar smoke manual com fixture JSON e verificar stdout/exit code.
- [ ] **Step 7:** commit `feat(atlas): add state reaction cli`.

### Task 6: Integrar gate de CI e empacotamento

**Files:**
- Modify: `.github/workflows/foundation-ci.yml`
- Create: `infrastructure/pentium/atlas/install-user.sh`
- Create: `infrastructure/pentium/atlas/tests/fixtures/healthy.json`
- Create: `infrastructure/pentium/atlas/tests/fixtures/critical.json`

**Interfaces:**
- Installer copia somente código/config do Atlas para `~/pentium-agent/atlas/`.
- Não instala mídia, LLM, TTS, STT nem altera systemd nesta slice.

- [ ] **Step 1:** adicionar fixture `healthy.json` e `critical.json` e validar ambas via CLI.
- [ ] **Step 2:** escrever `install-user.sh` idempotente, sem sudo e sem tocar em chaves/secrets.
- [ ] **Step 3:** adicionar ao Foundation CI: `py_compile`, `json.tool`, `unittest discover`, `bash -n` e smoke das duas fixtures.
- [ ] **Step 4:** rodar localmente `git diff --check` e todas as validações equivalentes ao CI.
- [ ] **Step 5:** commit `ci(atlas): validate state reaction foundation`.

### Task 7: Certificar HEAD, abrir PR e registrar checkpoint

**Files:**
- Modify somente evidência as-built confirmada em `docs/implementation/2026-09-03-atlas-state-reaction-foundation-design.md` se necessário.
- [ ] **Step 1:** push da branch `atlas/issue-20-state-reaction-foundation`.
- [ ] **Step 2:** abrir PR Draft empilhada sobre `control/issue-4-pentium-heartbeat`, relacionando Issue #20.
- [ ] **Step 3:** consultar HEAD exato da PR e workflow run associado; não reutilizar GREEN anterior.
- [ ] **Step 4:** inspecionar jobs/logs do Foundation CI e confirmar marcador Atlas no mesmo SHA.
- [ ] **Step 5:** se CI falhar, corrigir via TDD/revisão e repetir certificação do novo HEAD.
- [ ] **Step 6:** somente após GREEN, executar smoke físico READ-only no Pentium com snapshots/observed state; nenhum playback nesta slice.
- [ ] **Step 7:** registrar `/checkpoint` pt-BR na PR com implementação, testes, CI/HEAD, blockers e próximo passo seguro: Audio Engine.
- [ ] **Step 8:** atualizar as-built apenas com fatos comprovados no host real.

## Critérios finais da slice

- `global_state`, `intensity` e `reasons` são determinísticos para a mesma entrada;
- `recovered` aparece somente em transição válida;
- reaction pool suporta variedade, peso, cooldown e anti-repeat sem tocar mídia;
- meme nunca substitui sinal crítico;
- journal é JSONL parseável e append-only;
- CLI rejeita entrada inválida sem side effects;
- nenhuma chamada de rede, subprocesso ou shell é introduzida;
- nenhuma mídia/LLM/STT/TTS é implantada nesta slice;
- CI deve estar GREEN no HEAD exato antes de qualquer deploy físico;
- checkpoint fecha a etapa e aponta Audio Engine como próxima vertical.
