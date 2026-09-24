# Plano de Execução — Atlas 3.0: Governador Afetivo & Tecido Sensorial SSH

Este documento registra a sequência executada para a entrega da fatia cognitiva e sensorial do Atlas 3.0 no DevEx HomeLab.

---

## 1. Escopo e Objetivos

1. **Saneamento de Runtime**: Extinção de crashes por overflow em cálculo de backoff e expurgo de memórias órfãs.
2. **Matriz Afetiva Expandida**: Introdução de 20 sentimentos canônicos derivados deterministicamente.
3. **Governador Afetivo & Diálogo**: Modulação viva de tom e histórico de memória de trabalho de diálogo no Hermes 3.
4. **Tecido Sensorial SSH**: Conector observacional determinístico para o ecossistema L2jToren hospedado no host `x99`.
5. **Certificação E2E**: Bateria de testes automatizados e validação com inferência ao vivo no hardware físico.

---

## 2. Sequência de Fases Executadas

### Fase 1: Resiliência contra Overflow no Backoff
- **Alvo**: `infrastructure/pentium/atlas/observation_runtime.py`.
- **Ação**: Limitar o expoente em `min(failures, 10)` antes de calcular `2 ** exp`.
- **Critério de Aceite**: O teste de estresse com 3.000 falhas contínuas deve rodar sem gerar `OverflowError` nem degradar performance.
- **Status**: **Concluído e Aprovado** (`test_observation_backoff_overflow.py`).

### Fase 2: Expansão Afetiva para 20 Sentimentos
- **Alvo**: `infrastructure/pentium/atlas/emocao_derivada.py`.
- **Ação**: Ampliar `ROTULOS_EMOCAO` com 20 rótulos e mapear scores proporcionais em `_scores()`.
- **Critério de Aceite**: Toda combinação válida de ativação, valência, estresse e novidade deve classificar uma emoção primária e nuances de apoio.
- **Status**: **Concluído e Aprovado** (`test_emocao_derivada_20.py`).

### Fase 3: Governador Afetivo e Memória no Hermes 3
- **Alvo**: `infrastructure/pentium/atlas/hermes_adapter.py`, `modelo_contexto_cognitivo.py`, `contexto_cognitivo.py`.
- **Ação**: Criar tags XML `<affective_state_governor>` e `<recent_conversation_history>`, passando histórico recente de 4 a 6 turnos.
- **Critério de Aceite**: Prompt do Hermes deve conter o tom orientado pela emoção ativa e preservar continuidade entre perguntas encadeadas.
- **Status**: **Concluído e Aprovado** (`test_working_memory_dialogue.py`).

### Fase 4: Conector Observacional L2jToren e SSH no x99
- **Alvo**: `infrastructure/pentium/atlas/l2j_observation.py`, `capability_registry.py`, `capability_dispatch.py`, `cognitive_daemon.py`.
- **Ação**: Implementar sondas TCP e flash query SSH com autenticação via chave privada do x99 e comandos PowerShell bounded.
- **Critério de Aceite**: Portas 7777, 2106, 3306 e containers Docker devem ser auditados em menos de 1.5s.
- **Status**: **Concluído e Aprovado** (`test_l2j_observation.py`).

### Fase 5: Expurgo de Memórias e Deploy Físico no Pentium
- **Alvo**: Host físico `pentium` (`100.107.230.78`).
- **Ação**:
  - Expurgo das chaves de teste `test_parent_1789808712` e `test_child_1789808712` da base SQLite.
  - Sincronização de binários via SCP, compilação via `py_compile` e reinício dos daemons systemd.
  - Teste de inferência real ao vivo via console e inbox.
- **Critério de Aceite**: Daemons ativos, resposta produzida em JSON schema v1 estrito, acionamento da capability `l2j_get_status` e tom emocional coerente.
- **Status**: **Concluído e Aprovado**.
