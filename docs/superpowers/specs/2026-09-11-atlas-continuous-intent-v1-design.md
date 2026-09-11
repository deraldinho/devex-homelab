# Atlas Continuous Intent v1 — Design

## Objetivo

Dar ao Atlas uma presença contínua e coerente entre ciclos de observação sem transformar cada snapshot em uma nova fala, novo plano ou nova decisão desconectada.

O Atlas deve conseguir iniciar uma intenção de acompanhamento, mantê-la ativa enquanto a condição persistir, ceder imediatamente a uma interação humana e concluir a intenção quando a condição terminal ocorrer.

A memória episódica M2 permanece como único owner da memória de longo prazo. Continuous Intent apenas produz estado transitório e evidência de conclusão compatível com o pipeline já existente.

## Baseline autoritativo

- Base: `main` em `0f40df545efcc174d656b2b8b72777ec8f9b6948`.
- M2 runtime wiring já ativo em `ObservationDaemon`.
- `MotorFoco` continua owner da seleção do assunto principal.
- `ReactionLoopCognitivo` continua owner da inferência cognitiva.
- `ActionPlanner` continua owner da tradução de resposta cognitiva em ações.
- `CognitiveDaemon` continua owner da orquestração do ciclo cognitivo.
- Nenhum novo caminho de escrita direta em `MemoryRecord` será criado.

## Arquitetura

Fluxo principal:

`Snapshot/Chat → MotorFoco → BehaviorSelector → ContinuousIntentMachine → HabituationEngine → ReactionLoopCognitivo → ActionPlanner`

A intenção contínua não substitui foco, cognição ou plano de ação. Ela atua como estado de continuidade entre ciclos, carregando o propósito de acompanhamento enquanto o assunto permanecer semanticamente o mesmo.

### BehaviorSelector

Calcula utilidade determinística para candidatos de comportamento usando sinais já existentes:

`utility = relevancia + beneficio + confianca - custo_interrupcao - habituacao`

Na v1 os pesos serão fixos em configuração de código e não haverá aprendizado online. O selector recebe foco atual, contexto técnico, estado afetivo e presença de interação humana.

Saídas permitidas na v1: `OBSERVAR`, `ACOMPANHAR_RECUPERACAO`, `INTERAGIR_COM_HUMANO` e `ENCERRAR_ACOMPANHAMENTO`.

### ContinuousIntentMachine

Estados:

`CANDIDATA → ATIVA → AGUARDANDO → ATIVA → CONCLUIDA`

Terminais adicionais: `CANCELADA` e `EXPIRADA`.

Transições obrigatórias:

- `CANDIDATA → ATIVA` quando a utilidade ultrapassar o limiar e houver assunto estável.
- `ATIVA → AGUARDANDO` quando uma interação humana de maior prioridade chegar.
- `AGUARDANDO → ATIVA` quando a interação humana terminar e a condição original ainda existir.
- `ATIVA → CONCLUIDA` quando recuperação/condição terminal for observada.
- qualquer estado não terminal pode ir para `CANCELADA` por conflito semântico ou `EXPIRADA` por TTL.

A intenção deve ser identificada por `intencao_id`, `tipo`, `estado`, `assunto_id`, `entidade_id`, `motivo`, `prioridade`, `iniciado_em`, `atualizado_em`, `valido_ate`, `notificado_usuario`, `episodio_id`.

### HabituationEngine

Controla repetição de comunicação sem apagar presença.

Regra da v1 para uma condição persistente:

- primeira detecção: pode gerar uma comunicação e presença visual;
- ciclos equivalentes seguintes: zero mensagens duplicadas, mas o Atlas continua olhando/acompanhando visualmente;
- mudança material da condição: reavalia utilidade e pode renovar a comunicação;
- recuperação/conclusão: uma única comunicação terminal é permitida.

A habituação é por intenção/assunto, bounded por TTL e contadores pequenos. Não haverá persistência própria: reinício limpa habituação transitória, enquanto a M2 mantém memória de episódio consolidado.

### Human preemption

Interação humana sempre preempta comportamento passivo. A intenção operacional vai para `AGUARDANDO`, não é perdida e não disputa fala/gesto com a conversa.

Quando o ciclo humano termina, a intenção só volta a `ATIVA` se o assunto original continuar válido. Caso contrário, ela é concluída/cancelada conforme o snapshot vigente.

## Integração com componentes existentes

### MotorFoco

Antes da implementação de Continuous Intent, a correção já validada pelo usuário deve entrar no baseline da slice: quando o mesmo `assunto_id` reaparecer em um snapshot mais novo, o foco atual deve referenciar o candidato novo, não o objeto antigo congelado.

Isso é requisito para reconhecer recuperação do mesmo assunto sem manter criticidade antiga.

### ReactionLoopCognitivo

O estado visual `pensando=True` representa inferência real do LLM, não mera avaliação de política ou cache hit.

O callback de lifecycle `on_inference(bool)` já definido pelo usuário será integrado para marcar início/fim somente ao redor de `gateway.inferir()`, com `finally` garantindo limpeza em exceção.

Continuous Intent não deve usar `pensando` como indicador de acompanhamento. A presença de tracking será expressa por intenção ativa + ações visuais.

### ActionPlanner e presença visual

O planner continua gerando ações terminais. Continuous Intent apenas informa se uma ação é primeira notificação, acompanhamento silencioso ou encerramento.

Na v1, acompanhamento silencioso pode emitir `LOOK_AT` e `SET_EXPRESSION`, mas não `CHAT_REPLY` repetido. A conclusão pode emitir uma única resposta de recuperação e ação visual coerente.

## Integração com M2

A M2 continua recebendo resultados validados do pipeline observacional. Continuous Intent não escreve `MemoryRecord` diretamente.

Quando uma intenção atingir estado terminal, seu identificador e estado podem ser anexados como metadado reduzido em evidência já permitida, desde que isso não altere o contrato público de M1/M2 nem inclua payload bruto.

A certificação v1 deve provar que início → persistência → recuperação produz no máximo uma memória consolidada para o episódio e que retry/restart não duplica essa memória.

## Persistência e restart

A intenção contínua v1 é estado operacional transitório e não terá banco próprio.

Após restart, a intenção é reconstruída do snapshot atual e das memórias M2 relevantes, nunca restaurada cegamente de um arquivo de intenção antiga. Isso evita reviver condições já resolvidas durante downtime.

O único estado persistente novo permitido na v1 é observabilidade bounded (`continuous-intent.json`) para dashboard/debug; ele não é fonte de verdade no boot.

## Falhas e isolamento

- falha do BehaviorSelector: fallback para comportamento atual sem Continuous Intent;
- falha da máquina de intenção: não interrompe observation/cognitive loop;
- falha da camada visual: não altera estado da intenção;
- falha de M2: segue política já existente de `episodic_memory` degraded sem derrubar observação;
- cache hit ou policy block nunca podem deixar `pensando=True`;
- nenhuma intenção passiva pode disparar capability de controle automaticamente.

## Testes de aceitação

Replay determinístico de 10 snapshots para o caso `core` degradado:

1. core entra degradado;
2. `MotorFoco` seleciona core;
3. intenção `ACOMPANHAR_RECUPERACAO` fica `ATIVA`;
4. primeira notificação é emitida uma vez;
5. cinco snapshots equivalentes mantêm a intenção ativa;
6. nesses cinco snapshots não há nova mensagem, mas há presença visual bounded;
7. uma interação humana preempta para `AGUARDANDO` e depois retorna a `ATIVA` se core continuar degradado;
8. core recupera;
9. intenção vira `CONCLUIDA`, com uma única comunicação de recuperação;
10. M2 consolida no máximo uma memória do episódio e a intenção não fica órfã.

Também serão testados cache hit, policy block, exceção do gateway, restart durante intenção ativa, TTL, conflito semântico e cleanup de estado visual.

## Fora de escopo da v1

- aprendizado online de pesos;
- vector DB ou embeddings obrigatórios;
- novo planner concorrente;
- persistência autônoma de intenções;
- múltiplas intenções ativas em paralelo;
- mudança da política de capability/control;
- nova camada de memória semântica fora da M2;
- ativação automática de Voice ou Discord.

## Definition of Done

- exatamente uma intenção ativa por vez;
- interação humana sempre preempta intenção passiva;
- condição persistente não gera spam de chat;
- tracking visual continua durante habituação;
- recuperação encerra a intenção uma única vez;
- `pensando` reflete apenas inferência real;
- foco do mesmo assunto usa snapshot mais novo;
- M2 permanece único caminho de consolidação episódica;
- replay determinístico e suíte Atlas completa GREEN;
- CI remoto do HEAD exato GREEN antes de merge/deploy;
- deploy físico no Pentium seguido de smoke funcional real e rollback preservado.
