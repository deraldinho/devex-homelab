# Atlas Hermes + ChatGPT/Codex OAuth Migration Design

**Data:** 2026-09-09
**Projeto:** DevEx HomeLab / Atlas
**Branch:** `atlas/issue-20-avatar-pixijs-v1-1`

## Objetivo

Remover completamente Qwen e llama.cpp da cognição da Atlas e substituir o backend cognitivo por Hermes Agent executado no Pentium, usando autenticação ChatGPT/Codex OAuth para inferência remota.

A migração deve preservar toda a arquitetura já aprovada de corpo, observabilidade e segurança: Observation, Affective, memória Atlas, dashboard/chat, `PlanoAcaoAtlas`, `ActionPolicy`, executores e avatar PixiJS.

## Decisão arquitetural

O Pentium continua sendo o nó onde a Atlas vive operacionalmente. Hermes roda no Pentium, mas não carrega modelo local.

Fluxo canônico:

`Observation + Affective + Memory + Chat -> AtlasCognitiveRuntime -> HermesAdapter -> Hermes Agent -> ChatGPT/Codex OAuth -> resposta estruturada -> PlanoAcaoAtlas -> ActionPolicy -> Executors -> Dashboard/Avatar`

## Integração Hermes

A integração inicial usa o modo one-shot programático do Hermes, não o TUI, desktop ou gateway de mensagens. O contrato de execução é equivalente a `hermes -z`, que recebe um prompt, retorna somente a resposta final e encerra. O provider será `openai-codex`, configurado via `hermes model` ou `hermes auth add openai-codex` com device-code OAuth.

O OAuth é uma operação humana única no Pentium. As credenciais ficam no auth store próprio do Hermes em `~/.hermes/auth.json`. Nenhum token OAuth deve ser copiado para o repositório, runtime JSON, dashboard, logs ou eventos.

Será criado um perfil Hermes dedicado para a Atlas, separado do uso interativo do usuário. O perfil terá configuração mínima e não herdará toolsets operacionais do perfil pessoal.

## Fronteira de segurança

Hermes não é autoridade de execução da Atlas. Ele pode produzir somente uma resposta cognitiva estruturada que o `HermesAdapter` converte para o domínio existente.

O Hermes não recebe acesso direto a shell, filesystem de projeto, systemd, SSH, PixiJS ou capabilities da Atlas. A integração cognitiva deve executar com toolsets explicitamente vazios/desabilitados no perfil dedicado. Nenhum `--yolo` será adicionado por nós; o modo one-shot já é non-interactive, portanto nossa defesa é não disponibilizar ferramentas operacionais a esse agente.

Toda ação física, visual, textual ou futura de voz continua passando por:

`HermesAdapter -> RespostaCognitiva -> PlanoAcaoAtlas -> ActionPolicy -> ActionExecutorRegistry`

## Contrato cognitivo

O `HermesAdapter` recebe o contexto cognitivo já sanitizado e bounded da Atlas e constrói uma solicitação curta. A resposta esperada será JSON estrito com os mesmos campos semânticos consumidos atualmente pelo `ReactionLoopCognitivo`: texto, resumo, motivo, confiança, intenção opcional, parâmetros de intenção opcional, confirmação necessária e solicitação de fala.

O adapter valida tamanho, encoding, schema, enums e limites antes de criar `RespostaCognitiva`. Texto fora do schema, JSON inválido, timeout, erro de autenticação, indisponibilidade de rede ou falha do Hermes resulta em `llm_indisponivel` substituído por um motivo neutro de backend, como `cognitive_backend_unavailable`, sem plano inventado.

Observation e Affective continuam funcionando quando Hermes ou internet estiverem indisponíveis. O dashboard deve mostrar o estado degradado sem bloquear o avatar basal ou a observação.

## Remoção de Qwen/llama.cpp

A migração remove do runtime de produção: `llama-server`, `llama-cli`, socket `atlas-llm.sock`, modelo GGUF Qwen, `config_llm.json`, `config_llama_server.json`, `llama_cpp_backend.py`, `llama_cpp_resident_backend.py`, `llama_server_runtime.py` e ownership desses processos pelo cognitive daemon.

Testes e harnesses históricos específicos de llama/Qwen serão removidos ou reescritos para o contrato Hermes. Nenhum fallback oculto para Qwen será preservado.

O cache cognitivo continuará existindo, mas sua identidade de modelo deixa de ser `Qwen3-*` e passa a ser uma identidade de backend Hermes/provider/model resolvida sem segredo.

## Voice

Voice permanece pausado/desabilitado durante toda a migração. O código de Voice deixará de depender do backend Qwen/llama, mas nenhum serviço de voz será iniciado como efeito colateral da mudança.

Quando a integração cognitiva de Voice for reativada em uma futura slice, ela deverá reutilizar a mesma fronteira Hermes/RespostaCognitiva em vez de manter um backend próprio.

## Dashboard e observabilidade

O dashboard troca os rótulos `Qwen Runtime` por `Hermes Runtime` e passa a mostrar apenas metadados seguros: estado, provider `openai-codex`, modelo resolvido quando disponível, duração, motivo e status de autenticação sanitizado.

A timeline operacional continua mostrando estímulo, inferência, decisão, plano e ações. Nenhum token OAuth, prompt interno, memória bruta, chain-of-thought ou saída de ferramenta do Hermes poderá aparecer no dashboard/SSE.

Chat continua sendo o canal oficial do usuário para a Atlas. Uma mensagem enviada pelo dashboard entra na mesma inbox bounded, passa pelo runtime cognitivo Hermes e gera `PlanoAcaoAtlas` antes de qualquer ação semântica.

## Discord como segundo canal oficial

Discord será o segundo canal humano oficial da Atlas, ao lado do dashboard/API. O Discord não conversa diretamente com Hermes: ele entra na mesma fila bounded e no mesmo runtime cognitivo da Atlas.

Fluxo canônico:

Discord Bot -> AtlasDiscordGateway -> ChatInbox -> AtlasCognitiveRuntime -> HermesAdapter -> PlanoAcaoAtlas -> ActionPolicy -> resposta -> Discord

O adapter preserva a origem human.discord e identificadores sanitizados de conversa/canal suficientes para correlacionar resposta e timeline. O histórico no dashboard indica a origem dashboard ou discord.

O bot opera por allowlist de usuários/canais configurada fora do código. Mensagens de bots, webhooks não autorizados e DMs/canais fora da allowlist são ignorados. Tamanho, fila, tentativas e idempotência seguem os mesmos limites do ChatInbox.

O token Discord nunca é armazenado em Git, JSON de runtime, logs, eventos ou dashboard. O serviço lê DISCORD_BOT_TOKEN de ambiente ou arquivo protegido no Pentium. O installer cria apenas o contrato de configuração; o segredo é provisionado manualmente após deploy.

A resposta ao Discord é publicada somente depois de o resultado cognitivo e o lifecycle do plano estarem persistidos. Falha de envio gera evento operacional retryable e não reexecuta a cognição nem duplica ações concluídas.

O dashboard mostra estado do canal Discord, última atividade sanitizada e erros sem expor credenciais ou headers.

## Instalação e autenticação

O installer da Atlas deve instalar/validar Hermes sem registrar credenciais. A autenticação ChatGPT/Codex é executada manualmente pelo usuário no Pentium após a instalação, via device code.

O serviço `atlas-cognitive.service` deve falhar de forma observável quando Hermes estiver ausente ou não autenticado, mas Observation, Affective e Dashboard devem continuar ativos.

## Testes e certificação

A migração será considerada pronta somente quando:

- não houver referência de produção a Qwen, GGUF, llama.cpp, llama-server, llama-cli ou `atlas-llm.sock`;
- testes de adapter cobrirem sucesso, JSON inválido, timeout, auth indisponível, resposta oversized e provider incorreto;
- `PlanoAcaoAtlas`, policy, chat, SSE e avatar continuarem GREEN;
- installers e CI validarem os novos módulos Hermes e rejeitarem regressão para Qwen/llama;
- o Pentium executar uma mensagem real do dashboard até uma resposta Hermes via ChatGPT/Codex OAuth;
- a mesma interação produzir plano e ação visual observáveis;
- Voice continuar inactive/disabled;
- Observation, Cognitive e Dashboard estiverem ativos no mesmo SHA;
- Foundation CI e Atlas Avatar CI estiverem GREEN no mesmo SHA físico.

## Fora de escopo desta slice

Não habilitar Voice, não dar tools/shell ao Hermes, não migrar para Hermes Gateway, não adicionar múltiplos providers/fallbacks, não mover Hermes para x99/core e não alterar o comportamento basal do Motion Engine.
