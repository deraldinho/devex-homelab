# Plano de Execução — Atlas 4.0: Propriocepção Contínua & Autonomia Técnica

Este documento registra a sequência executada para a entrega dos três pilares da arquitetura Atlas 4.0 no DevEx HomeLab.

---

## 1. Escopo e Objetivos

1. **Pilar 1 (Grafo Relacional & Memória M3)**: Conectar topologia de nós, serviços e preferências do operador ao retrieval de memória contextual e ContextoCognitivo.
2. **Pilar 2 (Propriocepção Contínua)**: Monitorar envelopes normais com Welford, projetar esgotamento de recursos com regressão linear e mapear coocorrências temporais causais.
3. **Pilar 3 (Autonomia Técnica & Gestão de Tarefas)**: Estruturar formulação e resolução de hipóteses diagnósticas, sugerir e rastrear tarefas proativas e suportar ciclo de vida persistente de tarefas.
4. **Governança & Prompt Hermes 3**: Integrar blocos `<proprioceptive_trends>` e `<active_hypotheses>` no prompt de inferência sem regressão em diálogos triviais.
5. **Certificação & Packaging**: Saneamento do `install-user.sh`, baterias completas de testes automatizados e deploy físico no nó `pentium`.

---

## 2. Sequência de Fases Executadas

### Fase 1: Saneamento do Pilar 1
- **Alvo**: `infrastructure/pentium/atlas/tests/test_pilar1_packaging_integration.py`.
- **Ações**:
  - Correção do valor de enum `EstadoObservacao.ACESSIBILIDADE_TOTAL` para `EstadoObservacao.OBSERVADO`.
  - Harmonização do rótulo emocional para `"atento"`, aderente ao catálogo de 20 sentimentos canônicos.
- **Status**: **Concluído e Aprovado**.

### Fase 2: Saneamento do Instalador (`install-user.sh`)
- **Alvo**: `infrastructure/pentium/atlas/install-user.sh`.
- **Ações**:
  - Adição dos módulos `l2j_observation.py`, `git_capability_executor.py`, `task_store.py` e `task_capability_executor.py` à lista de arquivos copiados (`install -m 0644`).
  - Inclusão dos 4 módulos na rotina de compilação estrita `python3 -m py_compile`.
- **Status**: **Concluído e Aprovado**.

### Fase 3: Suíte de Packaging & Integração do Pilar 2 (Propriocepção)
- **Alvo**: `infrastructure/pentium/atlas/tests/test_pilar2_packaging_integration.py`.
- **Ações**:
  - Teste de packaging do instalador para módulos de `proprioception/` com marker `ATLAS_PROPRIOCEPTION_INSTALL_PASS`.
  - Teste roundtrip integrado combinando `BaselineTracker`, `TrendDetector`, `TemporalCorrelator` e injeção de `tendencias_relevantes` no `ContextoCognitivoBuilder`.
- **Status**: **Concluído e Aprovado**.

### Fase 4: Suíte de Packaging & Integração do Pilar 3 (Autonomia)
- **Alvo**: `infrastructure/pentium/atlas/tests/test_pilar3_packaging_integration.py`.
- **Ações**:
  - Teste de packaging do instalador para módulos de `autonomy/` e `task_*.py` com marker `ATLAS_AUTONOMY_INSTALL_PASS`.
  - Teste roundtrip integrado de formulação/evidência de hipótese (`HypothesisEngine`), sugestão automática de tarefa (`TaskTracker`), ciclo de capabilities (`TaskCapabilityExecutor`), persistência pós-reboot (`SelfWorkStore`) e injeção de `hipoteses_ativas` no `ContextoCognitivoBuilder`.
- **Status**: **Concluído e Aprovado**.

### Fase 5: Injeção no Prompt Hermes 3 e Testes de Diálogo
- **Alvo**: `infrastructure/pentium/atlas/hermes_adapter.py`, `tests/test_working_memory_dialogue.py`.
- **Ações**:
  - Extração condicional de `tendencias_relevantes` e `hipoteses_ativas` em `_build_prompt`.
  - Formatação dos blocos XML `<proprioceptive_trends>` e `<active_hypotheses>`.
  - Validação de que prompts sem esses elementos não sofrem expansão de tokens nem regressão.
- **Status**: **Concluído e Aprovado**.

### Fase 6: Deploy Físico no Nó Pentium (`100.107.230.78`)
- **Alvo**: Host físico `pentium`.
- **Ações**:
  - Sincronização dos binários via SCP.
  - Execução de `install-user.sh` com validação de compilação e markers.
  - Reinicialização e conferência de saúde dos daemons systemd `atlas-observation.service` e `atlas-cognitive.service`.
- **Status**: **Em Execução**.
