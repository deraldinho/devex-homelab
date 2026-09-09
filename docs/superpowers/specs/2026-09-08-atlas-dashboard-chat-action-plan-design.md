# Atlas Dashboard Chat + PlanoAcaoAtlas Design

**Data:** 2026-09-08
**Projeto:** DevEx HomeLab / Atlas
**Branch:** `atlas/issue-20-avatar-pixijs-v1-1`

## Objetivo

Transformar o Atlas Observability Dashboard no canal operacional principal da Atlas: observabilidade cognitiva, chat humano, decisões explícitas e reflexo visual de cada ação sem permitir que o LLM controle diretamente renderer, shell ou serviços.

## Princípios obrigatórios

- O dashboard continua LAN-first e observável; ações de usuário entram por endpoints explícitos e autenticados pelo contexto local da aplicação.
- O Qwen nunca controla PixiJS diretamente.
- O Qwen nunca executa shell arbitrário.
- Toda ação semântica passa por `PlanoAcaoAtlas` e política de autorização.
- `EstadoVisualAtlas` continua a fronteira canônica do renderer.
- Voice permanece pausado nesta slice; ações de fala aparecem como bloqueadas por política quando aplicável.
- Movimentos basais do Motion Engine (respiração, blink, micro-saccades) não precisam gerar uma decisão cognitiva individual.
- Movimentos semânticos (olhar, gesto, expressão, postura) devem aparecer no plano e no dashboard.
## Contrato `PlanoAcaoAtlas`

Cada ciclo cognitivo que produz uma resposta ou comportamento semântico gera um plano versionado com:

- `plan_id`, `stimulus_id`, `created_at`, `objective`, `confidence`.
- `response_text` para chat, truncado e sanitizado.
- `actions[]` ordenadas com `action_id`, `type`, `target`, `parameters`, `status`, `reason` e timestamps.
- `requires_confirmation` no plano e por ação quando necessário.
- `policy_decision` separada do conteúdo gerado pelo LLM.

Tipos mínimos nesta slice:

- `CHAT_REPLY`
- `LOOK_AT`
- `SET_EXPRESSION`
- `SET_GESTURE`
- `SET_POSTURE`
- `SPEAK_TTS`
- `CAPABILITY_REQUEST`
- `WAIT`

Lifecycle por ação: `PLANNED -> AUTHORIZED -> EXECUTING -> COMPLETED`; desvios válidos: `BLOCKED`, `FAILED`, `CANCELLED`.
## Chat no dashboard

O dashboard passa a oferecer um canal textual oficial com histórico bounded.

Fluxo:

`POST /api/chat -> Stimulus(interacao_humana) -> Cognitive Runtime -> PlanoAcaoAtlas -> Policy -> Executors -> eventos -> dashboard`

Contrato mínimo do `POST /api/chat`:

- entrada: `{message, client_message_id}`;
- validação de tamanho e UTF-8;
- idempotência por `client_message_id`;
- resposta imediata `202` com `stimulus_id` e `plan_pending=true`;
- a resposta final chega pelo stream/eventos, não bloqueia o request até a inferência terminar.

O histórico visível mostra mensagens do usuário, respostas Atlas, erros e estados de entrega. Não armazena prompt interno ou memória bruta.

## Stream de eventos

Usar SSE em `GET /api/stream` nesta etapa. Eventos mínimos:

- `cognitive_state`
- `plan_created`
- `action_status`
- `chat_message`
- `visual_action`
- `confirmation_required`
- `runtime_error`

O stream é complementar ao polling existente; reconexão usa `Last-Event-ID` e buffer bounded.
## Execução e reflexo visual

Executores são especializados e não recebem texto livre do LLM.

- `VisualActionExecutor` traduz ações semânticas autorizadas para alterações em `EstadoVisualAtlas`.
- `ChatActionExecutor` publica a resposta textual no histórico/stream.
- `TtsActionExecutor` permanece bloqueado enquanto Voice estiver pausado e registra `BLOCKED reason=voice_paused`.
- `CapabilityActionExecutor` continua subordinado a `PolicyCapabilities`; nesta slice não ganha shell arbitrário.

Exemplos de mapeamento visual:

- `LOOK_AT(target=x99)` -> `foco_visual=x99`, `direcao_olhar` coerente.
- `SET_EXPRESSION(CURIOSO)` -> `expressao=CURIOSO`.
- `SET_GESTURE(ACENO, arm=right)` -> gesto semântico no contrato visual/motion.
- `SET_POSTURE(ABERTO)` -> postura semântica representada pelo rig.

O dashboard mostra lado a lado `planejado`, `autorizado`, `executando` e `resultado` para impedir que decisão e execução pareçam a mesma coisa.

## UI

Adicionar três superfícies principais:

1. **Chat com Atlas** — histórico, caixa de mensagem, estado de envio e resposta.
2. **Plano/Decisão atual** — objetivo, confiança, resposta prevista e lista ordenada de ações com status.
3. **Timeline operacional** — estímulo, cognição, criação do plano, autorização, início/fim de ações e erros.

O painel atual de cognição permanece e continua mostrando contexto, afeto, foco, backend e latência.
## Persistência bounded

Arquivos runtime propostos:

- `action-plan-current.json` — plano corrente e lifecycle das ações.
- `action-plan-history.jsonl` — histórico bounded de planos concluídos/bloqueados.
- `chat-history.jsonl` — histórico bounded de mensagens observáveis.
- `dashboard-events.jsonl` — replay bounded do stream SSE.

Todos devem usar escrita atômica quando representarem estado corrente; JSONL deve ser truncado por quantidade/bytes e nunca crescer sem limite.

## Falhas e recuperação

- Qwen indisponível: plano não é inventado; runtime publica `DEGRADED` e chat recebe erro observável.
- Executor visual falha: ação `FAILED`, plano continua registrando as demais ações independentes.
- SSE cai: frontend reconecta e usa polling/`Last-Event-ID` para recuperar estado.
- Dashboard reinicia: estado corrente é reconstruído dos arquivos runtime bounded.
- Voice pausado: `SPEAK_TTS` é `BLOCKED`, sem tentativa de ativar serviço.
- Capability requer confirmação: ação para em `AUTHORIZED/confirmation_required` até decisão explícita do usuário em fluxo futuro; nesta slice não há execução automática de controles.

## Segurança e privacidade

O dashboard pode mostrar texto de resposta, resumo, intenção, status e parâmetros visuais seguros. Não expõe chain-of-thought, prompt do sistema, prompt completo, memória bruta, segredos, tokens ou parâmetros sensíveis de capabilities.

`POST /api/chat` aceita apenas texto; não aceita comandos shell, nomes de executáveis ou payload genérico de ferramenta como caminho de execução.
## Testes e certificação

TDD obrigatório por slice:

- modelo e validação de `PlanoAcaoAtlas`;
- lifecycle de ações e transições inválidas;
- política de autorização e bloqueio de TTS com Voice pausado;
- persistência bounded/idempotência;
- `POST /api/chat` e SSE com reconexão;
- execução visual refletida em `EstadoVisualAtlas`;
- UI mostrando plano, status de ações e chat;
- ausência de chain-of-thought e dados sensíveis na API;
- smoke físico Edge no x99 contra `192.168.88.3:8765`.

Critério de sucesso físico: enviar mensagem no chat, observar criação do estímulo e plano, ver cada ação mudar de status e confirmar que o avatar executa os movimentos semânticos correspondentes; se houver `SPEAK_TTS`, o dashboard deve mostrar `BLOCKED voice_paused` enquanto Voice permanecer pausado.

## Fora de escopo desta slice

- reativar Voice/TTS/microfones;
- shell arbitrário ou controle direto de systemd pelo Qwen;
- WebSocket;
- multimodalidade no chat;
- persistência ilimitada;
- exposição de raciocínio interno bruto.

## Ordem arquitetural de implementação

1. `PlanoAcaoAtlas` + lifecycle + persistência bounded.
2. Planner/adaptação da saída cognitiva para plano explícito.
3. Policy + executores especializados, começando por visual/chat e TTS bloqueado.
4. API `POST /api/chat` + event bus/SSE.
5. UI Chat + Plano/Decisão + timeline operacional.
6. integração física e certificação no Pentium/x99 no mesmo SHA.
