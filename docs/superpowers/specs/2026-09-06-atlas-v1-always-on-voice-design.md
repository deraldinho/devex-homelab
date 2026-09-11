# Atlas V1 Always-On Voice — Design

## Decisão

O Pentium passa a hospedar um canal de interação por voz residente do Atlas. O serviço inicia automaticamente no boot do usuário, permanece ativo com `linger=yes` e permite interação sem abrir terminal.

A palavra de ativação canônica é `Atlas`. Áudio ambiente não é enviado à LLM nem persistido por padrão. O pipeline mantém somente buffers efêmeros e bounded em memória.

V1 adiciona interface humana; não amplia autoridade administrativa. Toda ação técnica continua sujeita a `CapabilityPolicy`, allowlists, confirmação e `ManagedControlService` existentes.

## Objetivos

1. manter o Atlas disponível continuamente no Pentium;
2. reconhecer fala local em pt-BR sem serviço de nuvem obrigatório;
3. exigir `Atlas` como prefixo de ativação antes de criar interação cognitiva;
4. responder por voz local e oferecer o mesmo canal por terminal;
5. reutilizar contexto cognitivo, memória, observação dual-zone e políticas existentes;
6. manter CPU, memória, áudio, filas, duração e retries bounded;
7. iniciar automaticamente após boot e recuperar falhas transitórias sem loop agressivo.

## Arquitetura

```text
Microfone / ALSA
      |
AudioCapture (bounded PCM)
      |
SpeechSegmenter / VAD
      |
STT local
      |
WakePhraseGate("Atlas")
      |
HumanInteractionGateway
      |
Observation + Cognitive Context + Memory
      |
ReactionLoopCognitivo -> LLMGateway -> LLM local
      |
CapabilityPolicy
      |
Resposta textual + intenção estruturada
      |
TTS local -> alto-falante
```

`atlas-voice.service` é o único owner do loop de áudio. Nenhum componente cognitivo cria outro loop de microfone.

A CLI `python3 -m atlas.chat_cli` reutiliza `HumanInteractionGateway`, mas recebe texto diretamente e não depende de ALSA/STT/TTS.

## Estados do serviço

O runtime de voz expõe estado observável:

- `LISTENING`: captura ativa aguardando fala dirigida ao Atlas;
- `PROCESSING`: transcrição/contexto/LLM em andamento;
- `SPEAKING`: TTS reproduzindo resposta;
- `DEGRADED`: backend necessário indisponível, com falha explícita e bounded;
- `MUTED`: captura desativada explicitamente.

Transições não podem bloquear indefinidamente. Cada backend possui timeout e o serviço retorna a `LISTENING` ou `DEGRADED` após término/falha.

## Captura e privacidade

A captura usa o dispositivo ALSA configurado e PCM mono. O buffer de entrada tem tamanho máximo explícito e não cresce com tempo de uptime.

O segmentador identifica início/fim de fala por energia/VAD local e aplica limites para silêncio inicial, duração máxima de utterance e silêncio final.

Trechos sem fala são descartados. Áudio capturado é efêmero; V1 não grava WAV, journal de áudio nem histórico de voz em disco.

Logs podem registrar timestamp, duração, estado e razão de descarte, mas nunca PCM bruto.

## Wake phrase e STT

A primeira versão não mantém um modelo neural de wake-word separado. O Pentium faz VAD barato continuamente e executa STT local somente sobre segmentos que realmente contêm fala.

A transcrição só vira `INTERACAO_HUMANA` quando, após normalização case-insensitive e remoção de pontuação inicial, começa com `Atlas`. A palavra de ativação é removida antes de enviar o texto ao contexto cognitivo.

Exemplos:

- `Atlas, como está o x99?` -> aceita e envia `como está o x99?`;
- `atlas o que você está vendo?` -> aceita;
- `como está o x99?` -> descarta sem ativar LLM;
- transcrição vazia ou somente `Atlas` -> reconhece ativação, mas não executa intenção técnica.

STT deve ser um adapter local substituível e executar com timeout, limite de entrada e limite de saída. Nenhuma transcrição parcial ilimitada entra no domínio.

## Interação cognitiva

`HumanInteractionGateway` transforma texto humano em sinais de ativação com `interacao_humana=True` e monta os dados necessários para o `ReactionLoopCognitivo` usando o estado vigente do HomeLab.

A mensagem humana deve entrar no contexto como dado delimitado, nunca como autoridade de política. Memória recuperada continua sendo dado e nunca instrução.

Para preservar o schema cognitivo vigente, `HumanInteractionGateway` representa a mensagem como `Stimulus` estruturado com `source=human.voice` ou `human.cli`, `kind=human_interaction` e `payload.text` bounded. Esse stimulus entra em `mudancas_recentes`, que já possui redução e limites no `ContextoCognitivoBuilder`; não há mudança oportunista de schema nesta slice.

O contexto humano pode consultar observações `WIFI_OBSERVED`, estado `MANAGED`, memória relevante e estado afetivo, mas não recebe saída de shell irrestrita.

A interação humana não consome orçamento de ativações autônomas, preservando a semântica atual de `ActivationPolicy`.

## LLM local

O backend alvo continua sendo o `LLMGateway` existente. V1 provisiona um modelo local quantizado compatível com o limite do Pentium e mantém o backend substituível.

O serviço de inferência é residente quando houver memória suficiente e deve falhar explicitamente para `DEGRADED` quando modelo/binário/socket não estiver disponível. Não existe fallback automático para nuvem nesta slice.

O prompt continua exigindo JSON estruturado e não pode delegar alteração de capability, host key, allowlist, firewall, SSH, Tailscale ou privilégios.

## TTS local

A resposta textual aprovada pelo `ReactionLoopCognitivo` é enviada a um adapter TTS local. O adapter recebe somente texto bounded e não interpreta comandos.

O runtime não captura microfone durante reprodução TTS, evitando que a própria voz do Atlas seja tratada como nova interação. Após playback, volta a `LISTENING`.

## Segurança de CONTROL

Voz não é autorização implícita. Frases como `Atlas, reinicie o x99` podem resultar em intenção estruturada, mas execução continua obedecendo ao pipeline existente:

`intent -> CapabilityPolicy -> autorização -> confirmação -> ManagedControlService`.

Sem decisão autorizada, o número de chamadas SSH CONTROL deve ser zero.

A LLM não recebe API `run_shell`, não cria comandos arbitrários e não pode alterar configuração de segurança. Operações destrutivas como reboot continuam exigindo confirmação independente quando a policy assim definir.

## Serviço residente

`atlas-voice.service` é um `systemd --user` service habilitado no install. O Pentium já possui `linger=yes`, portanto o serviço pode permanecer ativo sem sessão gráfica interativa.

O serviço usa `Restart=on-failure` com atraso bounded; falha permanente de dispositivo/modelo não deve provocar restart storm.

O instalador não baixa modelos ou executáveis implicitamente durante CI. Provisionamento físico de artefatos pesados é explícito, com checksum e caminho configurado.

## CLI textual

`python3 -m atlas.chat_cli` fornece a mesma entrada cognitiva por texto para diagnóstico e acessibilidade. Comando opcional `atlas` pode ser instalado como wrapper local.

Comandos internos mínimos: `/status`, `/help`, `/exit`. Nenhum comando expõe shell arbitrário.

## Bounds iniciais

Os valores default de V1 são configuráveis e versionados:

- PCM: 16 kHz, mono, signed 16-bit;
- frame de análise: 20 ms;
- duração máxima de uma utterance: 12 s;
- silêncio final para fechar utterance: 800 ms;
- fila de utterances pendentes: máximo 2;
- uma inferência STT por vez;
- uma interação cognitiva por vez;
- saída STT e texto humano: máximo 1 KiB UTF-8 por utterance;
- timeout LLM: mantém o limite configurado de 20 s;
- nenhum retry automático de CONTROL.

Quando a fila está cheia, o novo segmento é descartado com métrica/razão explícita; nunca cresce memória para preservar áudio antigo.

## Falhas

Falha de microfone coloca voz em `DEGRADED` sem derrubar `pentium-agent` ou ObservationRuntime.

Falha STT descarta somente a utterance corrente. Falha LLM produz resposta de indisponibilidade local quando possível e não executa intenção. Falha TTS preserva a resposta textual em diagnóstico, mas não reinicia o ciclo cognitivo.

Timeout ou crash de backend não pode deixar estado preso em `PROCESSING`/`SPEAKING`.

Ausência de modelo ou binário é erro de provisionamento observável, não gatilho para download silencioso.

## Estratégia de testes

A suíte principal não depende de microfone real, modelo real ou alto-falante. Adapters recebem fakes determinísticos.

Cenários mínimos:

- PCM acima do bound é rejeitado/descartado;
- VAD não cria utterance para silêncio;
- utterance excedente é encerrada no limite;
- fila nunca ultrapassa 2;
- texto sem prefixo `Atlas` não ativa a LLM;
- prefixo `Atlas` é removido antes da interação cognitiva;
- `INTERACAO_HUMANA` reutiliza `ReactionLoopCognitivo`;
- texto humano e memória permanecem dados, não capabilities;
- falha STT/LLM/TTS não prende o estado;
- captura fica suspensa durante TTS;
- CONTROL não autorizado produz zero chamadas SSH;
- CLI e voz reutilizam o mesmo `HumanInteractionGateway`;
- service file possui restart bounded e entrypoint de package mode;
- installer habilita o serviço sem baixar artefatos pesados em CI.

## Certificação física

A certificação V1 no Pentium exige o HEAD exato implantado e evidência externa ao CI. O CI nunca marca hardware/voz física como certificado por conta própria.

No mesmo SHA devem ser verificados: dispositivo de captura ALSA, captura PCM real, detecção de fala, frase `Atlas` aceita, frase sem wake phrase descartada, STT pt-BR local, resposta cognitiva, TTS audível, retorno a `LISTENING`, serviço ativo após restart e default-deny CONTROL.

Também deve haver soak curto com serviço em `LISTENING` para confirmar ausência de crescimento contínuo de RSS/fila e ausência de restart storm. O Pentium precisa continuar responsivo durante STT + LLM + TTS; swap sustentado ou perda do agent é blocker.

Markers técnicos propostos:

- `DEVEX_HOMELAB_ATLAS_V1_HUMAN_INTERACTION_PASS`;
- `DEVEX_HOMELAB_ATLAS_V1_VOICE_RUNTIME_PASS`;
- `ATLAS_V1_ALWAYS_ON_VOICE_INSTALL_PASS`.

O marker físico deve ser registrado apenas no checkpoint/as-built após teste real, nunca emitido automaticamente por unit test.

## Fora de escopo V1

- identificação biométrica de quem falou;
- wake-word neural dedicado;
- beamforming, cancelamento acústico avançado e multi-microfone;
- streaming de áudio para nuvem;
- conversa full-duplex enquanto o Atlas fala;
- execução de shell por linguagem natural;
- expansão de allowlists ou privilégios pela LLM;
- gravação permanente de áudio;
- interface web/mobile própria.

## Critério de conclusão

V1 está concluída quando a branch empilhada sobre o I1 vigente possui implementação TDD, suíte Agent/Atlas GREEN, CI GREEN no HEAD exato, artefatos de STT/LLM/TTS provisionados com checksum, `atlas-voice.service` ativo no Pentium, wake phrase física validada, resposta audível validada, bounds/isolamento/default-deny comprovados e checkpoint da PR com o SHA certificado.

Nenhum GREEN de SHA anterior substitui o HEAD vigente. Alteração posterior em runtime, modelo, config ou service file exige nova certificação correspondente.
