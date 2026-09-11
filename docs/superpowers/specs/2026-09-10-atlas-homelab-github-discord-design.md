# Atlas HomeLab + GitHub + Discord — Design

## Objetivo

Expandir o Atlas para observar o DevEx HomeLab inteiro e as entregas Git, mantendo Hermes como backend cognitivo único e adicionando Discord como canal de interação equivalente ao dashboard.

## Estado atual confirmado

- `ObservationRuntime` foi projetado para múltiplas fontes e já possui deduplicação, backoff, journal e isolamento de falha.
- `stimulus_sources.py` já contém `PentiumSelfSource`, `CoreHealthSource`, `X99StatusSource` e `ManagedObservationSource`.
- A composição ativa de `observation_daemon.py` usa apenas `wifi.presence` e hosts `MANAGED`.
- `agent/config.json` cadastra somente `x99` como `MANAGED`, explicando por que `core` não é observado hoje.
- `ChatInbox` + `CognitiveDaemon` + `CHAT_REPLY` já formam o pipeline canônico de conversa do dashboard.

## Arquitetura alvo

`pentium.self`, `managed.core`, `managed.x99`, `wifi.presence` e fontes `github.<repo>` publicam snapshots normalizados no mesmo `ObservationRuntime` e `StimulusBus`. O pipeline afetivo/cognitivo continua único e o Hermes continua sendo o único backend LLM.

Dashboard e Discord escrevem no mesmo `ChatInbox`. Cada mensagem carrega metadados de rota; a resposta cognitiva preserva esses metadados no evento `chat_message`, permitindo que cada adaptador entregue a resposta ao canal correto.

### Invariante emocional do Atlas

Atlas continua sendo o mini pet/IA emocional da infraestrutura. Pentium, Core, x99 e GitHub são novos sentidos do mesmo agente e precisam atravessar percepção, impacto afetivo, foco/emoção e contexto cognitivo antes de Hermes formular resposta. `NotificationPolicy` decide apenas se uma resposta cognitiva já produzida deve ganhar rota Discord; ela não cria texto técnico paralelo e não contorna memória, emoção, foco, avatar ou `ActionPlan`.

Qualquer mudança que quebre os gates afetivos, visuais, cognitivos, de memória ou voz deixa a slice RED.

## Fronteiras de segurança

- SSH permanece propriedade do `Pentium Agent/ManagedReadService`; Atlas não constrói shell arbitrário.
- GitHub é READ-only nesta slice.
- Credenciais GitHub permanecem no `gh auth`/`GH_TOKEN` do host; o token Discord vem exclusivamente de ambiente/arquivo de secret ignorado pelo Git.
- Nenhum token, Authorization header ou conteúdo de secret pode entrar em Stimulus, journal ou dashboard events.
- Discord aceita somente guild/channel/user explicitamente allowlisted.
## Observação física

`pentium.self` é coletado localmente, sem SSH. `core` e `x99` são hosts MANAGED e usam operações READ allowlisted (`uptime`, `cpu`, `memory` inicialmente). Uma falha de um host não bloqueia as demais fontes.

A composição deixa de ser rigidamente dual-zone e passa a aceitar fontes adicionais explícitas, mantendo compatibilidade com os testes e callers atuais.

## Observação GitHub

Cada repositório autorizado possui uma fonte estável `github.<owner>.<repo>`. O collector consulta somente dados reduzidos de PRs abertas, Issues abertas e runs recentes. O payload inclui IDs, estado, draft, SHA, status/conclusion e timestamps; não inclui diffs, logs brutos nem secrets.

Mudanças de fingerprint geram Stimulus. Polls sem alteração são suprimidos pelo runtime existente. Falha ou ausência do `gh`/credencial GitHub degrada somente essas fontes opcionais; observação física, estado afetivo pré-existente e canais locais continuam independentes.

## Conversa multicanal

`ChatEnvelope` ganha `channel`, `actor_id`, `conversation_id` e `reply_target`, com defaults compatíveis com dashboard. O `CognitiveDaemon` transforma a mensagem em `human.<channel>` e replica os metadados de rota no evento de resposta.

O dashboard continua funcionando sem alterações de contrato HTTP obrigatórias; mensagens antigas são lidas com defaults seguros.

## Discord

O gateway Discord é um adaptador fino. Ele valida allowlists, converte mensagem em `ChatInbox.enqueue(...)` e acompanha apenas respostas roteadas para `channel=discord`. A dependência `discord.py` é carregada somente no processo Discord, nunca pelo runtime principal.

O bot ignora mensagens de bots, limita tamanho, usa idempotência por message ID e não executa capabilities diretamente.

## DoD

A slice termina quando existem testes para composição física, GitHub normalization/redaction, ChatInbox multicanal e roteamento Discord; instaladores empacotam os novos módulos/configs; configs não contêm tokens; e a suíte relevante fica GREEN no HEAD exato quando a execução de testes estiver disponível.