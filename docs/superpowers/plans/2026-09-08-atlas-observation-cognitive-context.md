# Atlas Observation → Cognitive Context Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer CLI/cognição consumir percepção, incidente, A1, emoção e foco reais do runtime observacional/afetivo, por snapshot atômico bounded, sem reativar voz nem ativação cognitiva autônoma.

**Architecture:** `atlas-observation.service` continua single-writer de A1/A2/A3/A4 e passa a publicar `cognitive-observation-context.json` após persistência do evento aceito. `HumanContextProvider` combina essa projeção somente-leitura com o health técnico existente e bloqueia o LLM em fail-safe quando o contexto observacional não é confiável.

**Tech Stack:** Python 3 stdlib, dataclasses, JSON, atomic temp+fsync+`os.replace`, `unittest`, systemd user service, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-08-atlas-observation-cognitive-context-design.md`

## Global Constraints

- Base exata: `0b6e7e974043d2e5942ad9a1ca339713b1a1149c`.
- `atlas-observation.service` permanece owner único de A1/A2/A3/A4 e do snapshot cognitivo.
- `technical_state` nunca entra na projeção; continua vindo de `health/latest.json`.
- Nenhum fallback emocional/perceptivo sintético é permitido.
- Snapshot path: `~/pentium-agent/atlas/runtime/cognitive-observation-context.json`.
- `max_snapshot_age_s = 180`.
- Voz permanece `inactive/disabled`; nenhum teste/deploy deve capturar/STT/TTS.
- Eventos observacionais não ativam LLM autonomamente nesta slice.
- CONTROL permanece default-deny; nenhuma porta/broker/dependência do x99.
- Nenhuma mudança em L2jToren.

---### Task 1: Contrato e publisher da projeção cognitiva

**Files:**
- Create: `infrastructure/pentium/atlas/cognitive_observation_projection.py`
- Test: `infrastructure/pentium/atlas/tests/test_cognitive_observation_projection.py`

**Interfaces:**
- Produces: `CognitiveObservationSnapshot`, `CognitiveObservationPublisher.publish(...)`, `load_cognitive_observation_snapshot(...)`.
- Consumes: `Stimulus`, resultado A3, impacto afetivo e `ResultadoFocoEmocao`.

- [ ] Escrever testes RED para schema v1, ausência de `technical_state`, bounds de strings/listas/payload, recovery preservado e atomic write.
- [ ] Rodar apenas `test_cognitive_observation_projection.py` e confirmar falha por módulo/API ausente.
- [ ] Implementar dataclass/serializer/validator e publisher por `.tmp` + flush + fsync + `os.replace` + fsync do diretório em POSIX.
- [ ] Validar que `recent_changes`, `affected_dependencies` e nuances são truncados pelos limites de `PoliticaContextoCognitivo` e que payload inválido é rejeitado.
- [ ] Rodar teste focal GREEN e commit `feat(atlas): adicionar projecao cognitiva observacional`.

### Task 2: Expor resultado A3 do mesmo evento

**Files:**
- Modify: `infrastructure/pentium/atlas/pipeline_afetivo_observacional.py`
- Test: `infrastructure/pentium/atlas/tests/test_pipeline_afetivo_observacional.py`

**Interfaces:**
- Produces: `ResultadoPipelineAfetivoObservacional.resultado_percepcao` para eventos aceitos.
- Preserva: `aceito`, `resultado_foco_emocao`, `impacto` e deduplicação existentes.

- [ ] Escrever teste RED provando que o retorno aceito carrega exatamente o objeto A3 retornado por `pipeline_percepcao.processar(stimulus)`.
- [ ] Escrever teste RED de recovery provando que o incidente daquele evento continua disponível no retorno mesmo quando sai da coleção ativa depois.
- [ ] Implementar somente o novo campo read-only no dataclass e preenchê-lo no retorno aceito; duplicate continua sem resultado.
- [ ] Rodar testes focais + regressão do pipeline GREEN.
- [ ] Commit `feat(atlas): expor percepcao do evento afetivo`.### Task 3: Publicar snapshot no composition boundary

**Files:**
- Modify: `infrastructure/pentium/atlas/affective_composition.py`
- Modify: `infrastructure/pentium/atlas/observation_daemon.py`
- Test: `infrastructure/pentium/atlas/tests/test_affective_composition.py`
- Test: `infrastructure/pentium/atlas/tests/test_observation_daemon.py`

**Interfaces:**
- Consumes: `ResultadoPipelineAfetivoObservacional.resultado_percepcao` e publisher da Task 1.
- Produces: estado bounded do bridge com `last_publish_at`, `last_publish_stimulus_id`, `current_error` e histórico diagnóstico limitado.

- [ ] Escrever testes RED para publish após persistência A3→A2→A1→A4, sem publish em duplicate/unmapped source.
- [ ] Escrever teste RED que força falha de publisher: evento continua aceito, `current_error` fica preenchido; publish válido posterior limpa o erro.
- [ ] Implementar deque bounded de `recent_changes` apenas em memória e montagem do snapshot com os objetos do mesmo evento.
- [ ] Expor estado corrente do bridge ao health do `observation_daemon`, degradando somente enquanto `current_error` estiver ativo.
- [ ] Rodar testes focais GREEN e commit `feat(atlas): publicar contexto cognitivo observacional`.

### Task 4: Tornar HumanContextProvider leitor canônico

**Files:**
- Modify: `infrastructure/pentium/atlas/human_context.py`
- Create: `infrastructure/pentium/atlas/tests/test_human_context_observation_bridge.py`
- Modify: `infrastructure/pentium/atlas/configuracao_cognitiva.py`
- Modify: `infrastructure/pentium/atlas/config_cognitiva.json`

**Interfaces:**
- Produces: `CognitiveContextUnavailable` e `HumanContextProvider(health_path, observation_snapshot_path, max_snapshot_age_s, expected_sha=None)`.
- Consumes: snapshot validado da Task 1 e health técnico existente.

- [ ] Escrever testes RED que reconstruam `EstadoPercepcao`, `IncidenteTecnico`, `EstadoAfetivo`, `EmocaoDerivada` e `FocoAtencao` sem síntese.
- [ ] Escrever testes RED para ausente/corrompido/schema/SHA/stale, exigindo `CognitiveContextUnavailable`.
- [ ] Escrever teste RED provando que health técnico influencia somente `GlobalAssessment` e que snapshot não contém `technical_state`.
- [ ] Implementar configuração `observation_bridge` com `snapshot_path`, `max_snapshot_age_s=180`, `require_expected_sha`.
- [ ] Implementar provider fail-safe e rodar testes focais GREEN.
- [ ] Commit `feat(atlas): usar contexto observacional real na cognicao`.### Task 5: Bloqueio local do LLM e wiring CLI/voz

**Files:**
- Modify: `infrastructure/pentium/atlas/human_interaction.py`
- Modify: `infrastructure/pentium/atlas/chat_cli.py`
- Modify: `infrastructure/pentium/atlas/voice_daemon.py`
- Test: `infrastructure/pentium/atlas/tests/test_human_interaction_observation_bridge.py`
- Test: `infrastructure/pentium/atlas/tests/test_chat_cli.py`
- Test: `infrastructure/pentium/atlas/tests/test_voice_daemon_visual_ipc.py`

**Interfaces:**
- Consumes: `CognitiveContextUnavailable` da Task 4.
- Preserva: `ReactionLoopCognitivo`, capability policy e voice visual IPC.

- [ ] Escrever teste RED: indisponibilidade do provider retorna resposta local curta e `ReactionLoopCognitivo.processar()` não é chamado.
- [ ] Escrever teste RED: CLI usa o provider observacional configurado e uma interação válida chega ao builder com A1/A3/A4 reais.
- [ ] Atualizar `_build_gateway()` e `voice_daemon.build_runtime()` para o novo provider sem habilitar serviço/áudio.
- [ ] Rodar testes focais GREEN e commit `feat(atlas): ligar interacao humana ao contexto real`.

### Task 6: Packaging, CI e certificador

**Files:**
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`
- Create: `infrastructure/pentium/atlas/cognitive_context_bridge_certification.py`
- Create: `infrastructure/pentium/atlas/tests/test_cognitive_context_bridge_certification.py`
- Modify: `infrastructure/pentium/atlas/tests/test_affective_boot_packaging.py`

**Interfaces:**
- Produces markers: `ATLAS_COGNITIVE_CONTEXT_BRIDGE_INSTALL_PASS` e `ATLAS_COGNITIVE_CONTEXT_BRIDGE_PHYSICAL_PASS`.
- Certifica: exact SHA, observation active, voice inactive/disabled, snapshot válido, matching entity/A1/A3/A4, CLI real-context e fail-safe isolado.

- [ ] Escrever testes RED para empacotamento dos novos módulos/config e certifier pure-function.
- [ ] Implementar instalação e gate `DEVEX_HOMELAB_ATLAS_COGNITIVE_CONTEXT_BRIDGE_PASS` sem tocar no enable state da voz.
- [ ] Implementar certifier que rejeita SHA mismatch, snapshot stale/inválido, voz ativa ou contexto sintético.
- [ ] Rodar testes focais GREEN e commit `ci(atlas): certificar ponte de contexto cognitivo`.### Task 7: Regressão local e certificação física no Pentium

**Files:**
- No new production files unless a defect requires a focused fix.
- Evidence: `~/pentium-agent/atlas/runtime/cognitive-context-bridge-certification.json` on Pentium.

- [ ] Rodar suíte Atlas completa: `python -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py'`.
- [ ] Rodar dashboard: `python -m unittest discover -s infrastructure/pentium/dashboard/tests -p 'test_*.py'`.
- [ ] Rodar `py_compile` nos módulos tocados, parse dos JSON, `bash -n infrastructure/pentium/atlas/install-user.sh`, `git diff --check`, guard UTF-8 e confirmar worktree limpa.
- [ ] Criar archive do HEAD exato, validar package no Pentium e executar installer sem reativar voz; confirmar `atlas-observation.service=active` e `atlas-voice.service=inactive/disabled`.
- [ ] Observar evento real e verificar snapshot novo com `expected_sha` exato; comparar entidade/percepção/A1/emoção/foco com os persistidos A3/A1/A4.
- [ ] Executar probe CLI sem TTS/STT que constrói contexto real; executar em cópia isolada probes stale/corrupt e provar zero chamada ao LLM/zero impacto no observation service.
- [ ] Reiniciar observation, confirmar restauração A1/A2/A3/A4 e nova projeção no próximo evento.
- [ ] Executar certifier e exigir `ATLAS_COGNITIVE_CONTEXT_BRIDGE_PHYSICAL_PASS`; salvar evidência JSON.
- [ ] Se qualquer ajuste for necessário, aplicar via novo ciclo RED→GREEN, commitar, repetir toda certificação no novo SHA e usar somente esse SHA como final.

### Task 8: Checkpoint e handoff

- [ ] Confirmar `git status --short --branch` limpo e registrar HEAD exato.
- [ ] Preparar checkpoint pt-BR com implementação, testes, evidência física, gates/blockers e próxima slice (ativação cognitiva autônoma), sem afirmar CI remoto GREEN antes de observá-lo.
- [ ] Invocar `superpowers:verification-before-completion` antes de declarar concluído.
- [ ] Invocar `superpowers:finishing-a-development-branch` e oferecer as opções de integração sem merge remoto automático nem exclusão silenciosa de branch/worktree.
