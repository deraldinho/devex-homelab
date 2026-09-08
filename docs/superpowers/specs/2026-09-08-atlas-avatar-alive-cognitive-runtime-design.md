# Atlas Alive + Cognitive Runtime — Design

## Objetivo

Evoluir o Atlas para uma presença visual continuamente animada e conectar a mini LLM Qwen ao runtime cognitivo 24/7 sem acoplar cognição ao renderer, sem colocar inferência no caminho crítico de observação e sem reativar voz.

## Fronteiras

- `EstadoVisualAtlas` permanece a única entrada semântica do renderer.
- A LLM não escolhe coordenadas, poses, severidade ou expressão diretamente.
- Observation/Affective continuam funcionais se Qwen, cache, memória ou o serviço cognitivo falharem.
- Dashboard permanece GET-only e não expõe prompt, texto bruto da inferência, memória bruta ou ações de controle.
- Voz permanece um produtor independente de estado efêmero e não é habilitada por esta slice.

## Motion Engine v1.2

O movimento visual é local ao browser e não consome inferência por frame. Um módulo puro de motion fornece easing exponencial, respiração, transferência de peso, micro movimento de cabeça, saccades suaves, blink irregular e secondary motion. O rig PixiJS passa a possuir braços articulados com antebraços e mãos, além de torso e cabelo com movimento secundário. `prefers-reduced-motion` e pausa por `visibilitychange` permanecem obrigatórios.

## Cognitive Runtime

`atlas-cognitive.service` é um owner separado do `atlas-observation.service`. Ele consome o snapshot cognitivo observacional mais recente, deriva sinais bounded de ativação, usa `ReactionLoopCognitivo` e executa inferência preferencialmente por `llama-server` residente em Unix socket. `llama-cli` permanece fallback.

A composição reutiliza os componentes existentes: `ActivationPolicy`, `ContextoCognitivoBuilder`, `LLMGateway`, `ReasoningPolicy`, `PolicyCapabilities`, `MemoryRetriever` e `CognitiveCache`. O modelo canônico é `~/pentium-agent/runtime/llama/models/Qwen3-0.6B-Q4_0.gguf`; o socket canônico é `/run/user/1000/atlas-llm.sock`.

## Cognição → visual

O serviço cognitivo envia somente estado efêmero pelo socket `cognitive-interaction.sock`. Antes da inferência publica `pensando=true`; ao finalizar publica `pensando=false`. O runtime afetivo combina esse canal com o canal de voz `affective-interaction.sock`, preservando `ouvindo` e `falando` sem permitir que um produtor apague o outro.

## Observabilidade

O resultado operacional é persistido atomicamente em `cognitive-runtime.json`. O dashboard expõe somente metadados seguros: disponibilidade, ativação, motivo, backend, duração, confiança e necessidade de confirmação. Texto e resumo gerados não entram automaticamente no dashboard.

## Falhas

- Qwen indisponível: Reaction Loop devolve fallback estruturado; Observation/Affective seguem ativos.
- Socket residente indisponível: backend tenta fallback CLI dentro do timeout.
- IPC cognitivo ausente: falha é isolada; renderer usa o último `EstadoVisualAtlas`.
- AF_UNIX ausente em ambiente de teste Windows: listener cognitivo degrada para no-op; produção Linux mantém Unix datagram real.
- Renderer PixiJS indisponível: SVG permanece fallback.

## Critérios de certificação

A slice só é promovida com testes Atlas e Dashboard GREEN no mesmo HEAD, checks Python/Node/Bash, `git diff --check`, CI Foundation e Avatar GREEN, serviço cognitivo ativo no Pentium, socket canônico presente, inferência real registrada e browser smoke confirmando canvas PixiJS, Motion asset e painel Qwen.
