# Atlas Full Activation — Design

## Objetivo

Ativar de forma certificada todas as funcionalidades já implementadas no Atlas, preservando o modelo de segurança, a estabilidade alcançada e o princípio de que nenhuma capability destrutiva recebe autonomia irrestrita.

A ativação será progressiva, com um único runtime cognitivo e um único pipeline emocional. Voice, Discord, GitHub, dashboard e automação operacional devem continuar atravessando os mesmos owners de observação, cognição, memória, ActionPlan e policy.

## Baseline autoritativo

- Base inicial: `main` em `c54dafa3a0e36fbec4d3bfaae364fb41457d945e`.
- Observation, Cognitive, Dashboard, GitHub observation, memória episódica, cache e Continuous Intent já estão ativos.
- Voice e Discord estão instalados como componentes, porém `disabled/inactive` fisicamente.
- GitHub permanece READ-only.
- `get_host_status` é READ automático.
- `restart_service` possui autonomia apenas no Pentium para serviços Atlas explicitamente allowlisted.
- `start_service`, `stop_service` e `reboot_host` continuam sem autonomia automática.

## Princípios invariantes

1. Hermes nunca recebe shell arbitrário, filesystem irrestrito ou credenciais.
2. Toda capability passa por `ActionPlan -> ActionPolicy -> executor`.
3. Ações destrutivas ou remotas exigem confirmação humana.
4. Secrets não entram em Git, Stimulus, journal, memória ou dashboard events.
5. Cada função só é considerada ativa após smoke físico real no SHA exato.

## Fase V — Voice completo

O contrato antigo que exige Voice `inactive/disabled` será substituído por um contrato feature-aware. Quando Voice estiver habilitado, certificações devem exigir serviço `active`, dependências de captura/STT/TTS disponíveis, health de áudio saudável e wake phrase funcional.

A ativação inclui:
- captura ALSA usando dispositivos reais detectados no Pentium;
- VAD/streaming VAD já existentes;
- Whisper STT com o modelo já provisionado;
- wake phrase `Atlas`;
- resposta cognitiva pelo pipeline canônico;
- TTS real pelo backend suportado;
- isolamento de falha: erro de áudio não derruba observation/cognitive/dashboard.

O CognitiveDaemon deixará de fixar `voice_enabled=False`; o estado será derivado de configuração/runtime certificado. `SPEAK_TTS` continuará passando por ActionPolicy e executor dedicado.

ANC permanece opt-in. Não será ligado até existir evidência física de que os dois canais/dispositivos realmente representam microfone primário e referência adequada.

## Fase D — Discord

Discord será ativado somente após preparar o ambiente isolado `.venv-discord`, validar `discord.py` e criar `runtime/discord.env` em modo `0600`.

O token continuará exclusivamente fora do Git. Guild, channel e user precisam de allowlists explícitas. O bot ignora bots, mantém idempotência por message ID e escreve no mesmo `ChatInbox`; não executa capabilities diretamente.

## Fase C — Integração cognitiva e comunicação

Voice e Discord são canais do mesmo Atlas, não agentes paralelos. Toda entrada humana vira `human.<channel>` e percorre contexto, memória, emoção, Continuous Intent e Hermes antes de gerar resposta.

`SPEAK_TTS`, `CHAT_REPLY`, ações visuais e capabilities continuam sendo ações terminais produzidas pelo ActionPlanner. Nenhum canal cria resposta técnica paralela fora do pipeline cognitivo.

Continuous Intent continua responsável pela continuidade entre ciclos; interação humana preempta comportamento passivo. Habituation continua impedindo spam de fala/chat durante condições persistentes.

## Fase A — Autonomia operacional

A política existente permanece como limite máximo inicial:
- READ allowlisted: `AUTO`;
- `restart_service` local e reversível no Pentium: `AUTO` somente sob host/service allowlist, cooldown, action budget e closed-loop verification;
- controle fora do escopo seguro: `CONFIRM`;
- `reboot_host` e demais ações destrutivas: sempre `CONFIRM`.

Ativar todas as funcionalidades não autoriza expansão silenciosa de allowlists. Qualquer aumento futuro do escopo automático exige nova slice, testes e aprovação explícita.

## Fase O — Observabilidade e health

Dashboard deve refletir individualmente: observation, cognitive, dashboard, voice, Discord, GitHub sources, managed hosts, backend Hermes, memória/cache, Continuous Intent e capabilities.

Estados possíveis precisam distinguir `healthy`, `disabled`, `blocked`, `degraded` e `unavailable`; policy suppression normal não pode aparecer como degradação.

## Ordem de rollout e gates

A ordem obrigatória será `Voice -> Discord -> integração cognitiva -> autonomia -> observabilidade global -> certificação final`.

Cada fase segue RED -> GREEN, suíte completa, CI exact-HEAD, merge, backup físico, deploy no Pentium, smoke funcional e soak curto. Uma fase RED bloqueia a próxima.

### Gate Voice
- captura real funciona no dispositivo configurado;
- STT reconhece fala de teste;
- wake phrase entra no pipeline humano;
- resposta cognitiva é produzida;
- TTS reproduz resposta real;
- serviço permanece `active`, sem restart loop;
- falha de áudio não derruba outros serviços.

### Gate Discord
- secret em `0600` e ausente do Git/logs;
- allowlists válidas;
- mensagem autorizada entra no `ChatInbox`;
- resposta retorna ao mesmo canal;
- mensagem não autorizada/bot é ignorada;
- restart mantém idempotência e cursor.

### Gate final
Todos os serviços habilitados precisam estar GREEN no mesmo SHA implantado, sem OOM, tracebacks ou drift de deployment metadata. Dashboard `/healthz` precisa responder e todas as fontes obrigatórias devem estar frescas.

## Rollback

Antes de cada ativação física será criado backup dos units, configs e runtime metadata. Rollback desabilita apenas a fase nova e restaura o último estado certificado, sem reverter Observation/Cognitive/Dashboard já estáveis.

## Definition of Done

A iniciativa termina quando Voice e Discord estão habilitados e certificados, os canais passam pelo pipeline emocional/cognitivo canônico, TTS/STT funcionam fisicamente, GitHub/hosts permanecem observados, autonomia segue os limites v1, dashboard mostra health por capability e o runtime inteiro permanece GREEN no SHA exato.
