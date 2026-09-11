# Atlas Affective Runtime Boot Design

## Objetivo
Colocar o pipeline observacional afetivo em operação contínua no Pentium sem fundir os loops de voz e observação e sem criar um terceiro owner de estado afetivo.

## Base
Esta slice parte do merge local `07a082c768a9f61033a7090a485f8fd24fdc1f54`, que já contém o pipeline `ObservationRuntime -> A3 -> A2/A1/A4 -> AffectiveRuntime -> visual-state.json` certificado localmente.

## Decisão arquitetural
Manter dois processos systemd independentes:
- `atlas-observation.service` para observação dual-zone + pipeline afetivo;
- `atlas-voice.service` para captura/STT/cognição/TTS.

Os dois processos não compartilham memória mutável. Compartilham apenas contratos persistidos/efêmeros em disco de forma bounded e atômica.

## Ownership
- `atlas-observation.service` é o único processo que aplica `ImpulsoAfetivo` e persiste A1/A2/A3/A4.
- `atlas-voice.service` nunca aplica impulso, não altera percepção/incidentes e não reclassifica emoção.
- `visual-state.json` permanece projeção efêmera, não fonte de verdade afetiva.
- O dashboard permanece read-only.

## Composition factory afetivo
Criar `affective_composition.py` como factory único para montar A1/A2/A3/A4, `PipelineAfetivoObservacional`, `AffectiveRuntime` e repositórios.

Entradas: caminhos de config/state, relógio e factories de IDs. Saída: objeto composto com `pipeline`, `runtime_visual`, repositórios e método de persistência.

Na inicialização:
- carregar `config_afetiva.json`, `config_percepcao.json`, `config_foco_emocao.json` e `config_observation_affective.json`;
- restaurar A1 com decaimento offline;
- restaurar A2; ausência/corrupção não cria entidades automaticamente;
- restaurar A4 apenas como continuidade visual auxiliar;
- restaurar A3 quando houver estado válido;
- publicar o último A4 válido no visual somente se compatível com A1 restaurado.

## Persistência transacional por evento
Após um `Stimulus` afetivo aceito e processado com sucesso, persistir em ordem A3 -> A2 -> A1 -> A4. Cada repositório já usa replace atômico; falhas são diagnosticadas e não retroagem o `Stimulus` no bus.

A persistência é best-effort por arquivo, mas um marcador de health deve expor `degraded` se qualquer camada falhar. Não haverá transação distribuída falsa.

## Daemon observacional always-on
Criar `observation_daemon.py` como entrypoint do `atlas-observation.service`.

Ele monta o dual-zone runtime existente com `accepted_stimulus_sink=composition.pipeline.processar`, inicia o scheduler único de observação, recebe SIGTERM/SIGINT e encerra de forma limpa.

Não haverá segundo `ObservationRuntime`, segundo scheduler ou polling paralelo de MANAGED/Wi-Fi.

O daemon publica health/readiness bounded em `~/pentium-agent/atlas/runtime/observation-affective-health.json` com schema versionado, HEAD esperado quando fornecido, último ciclo, origem de restauração e erros de persistência/pipeline.

## IPC efêmero de voz
Para preservar single-writer do `visual-state.json`, `voice_daemon` não escreverá visual diretamente.

O processo observacional cria um socket Unix local `~/pentium-agent/atlas/runtime/affective-interaction.sock`. A voz envia datagramas pequenos e versionados contendo somente `ouvindo`, `pensando`, `falando`, `duvida_identidade` e timestamp UTC.

O listener valida tamanho/schema, descarta mensagens inválidas e chama `AffectiveRuntime.atualizar_interacao`. Não persiste as flags como estado afetivo.

Se o socket não existir ou estiver indisponível, a voz segue funcionando; o erro visual é fail-safe e não afeta STT/LLM/TTS.

## Systemd e packaging
Adicionar `atlas-observation.service` como user service independente. `install-user.sh` instala e habilita observation + voice sem alterar dependências operacionais do x99.

`atlas-observation.service` terá restart on-failure, shutdown bounded e working directory `%h/pentium-agent`. O socket Unix pertence ao processo observacional e é removido no shutdown/startup stale-safe.

Foundation CI compila novos módulos, valida unit files/configs, executa testes e emite gate dedicado `DEVEX_HOMELAB_ATLAS_AFFECTIVE_BOOT_PASS`.

## Certificação física
Após CI/local GREEN, fazer deploy no Pentium e provar no SHA exato:
1. installer concluído;
2. `atlas-observation.service` active e estável após restart;
3. `atlas-voice.service` continua ativo ou deliberadamente pausado conforme configuração operacional existente;
4. health observacional com schema válido e sem erro fatal;
5. evento observacional real chega ao pipeline sem depender do x99;
6. `visual-state.json` é atualizado pelo processo observacional;
7. IPC de interação efêmera altera visual sem dar ownership afetivo à voz;
8. restart restaura A1/A2/A3/A4 conforme contratos dos repositórios.

Nenhum PASS físico será emitido por simulação local.

## Segurança e limites
- socket aceita apenas datagramas locais bounded; sem comandos, transcript, áudio ou payload arbitrário;
- CONTROL continua default-deny e fora do polling;
- nenhuma thread/fila ilimitada;
- nenhum busy loop: listener bloqueia no socket com timeout bounded e scheduler usa sleeps existentes;
- arquivos persistidos não contêm áudio/transcript/biometria;
- dashboard continua sem write/control.

## Fora de escopo
- fundir voice e observation no mesmo processo;
- novo supervisor global;
- mudar rótulos emocionais ou pesos aprovados na slice anterior;
- permitir que voz/LLM aplique `ImpulsoAfetivo`;
- introduzir Redis, broker externo ou dependência de x99;
- mudanças em L2jToren.

## Gates
- TDD RED→GREEN por composition factory, persistência pós-evento, daemon, IPC e wiring voice;
- regressão Atlas + dashboard;
- py_compile, JSON, `bash -n`, systemd verify quando disponível, diff-check e UTF-8;
- Foundation CI no HEAD exato;
- deploy/certificação física no Pentium antes de afirmar always-on operacional.

## Namespace de fontes e roteamento afetivo
O sink afetivo não aceitará cegamente toda fonte do I1. `affective_composition` mantém allowlist derivada de `config_percepcao.json`; fontes sem mapping afetivo são ignoradas com métrica/diagnóstico bounded, não tratadas como falha do `ObservationRuntime`.

`managed.x99` será mapeado explicitamente para a entidade A2/A3 `x99`. O `ManagedObservationSource` exporá um campo booleano normalizado de saúde do canal administrativo; esse sinal pode tornar a percepção parcial, mas nunca prova sozinho host offline.

`wifi.presence` permanece observacional nesta slice e não cria entidades afetivas dinamicamente. Ele só entrará no pipeline afetivo quando houver mapping explícito futuro para entidade conhecida.

Assim, indisponibilidade do x99 não impede o serviço no Pentium e não é dependência operacional; é apenas um objeto observado.

## Restauração A3
O estado persistido A3 não será apenas lido e descartado. `PipelinePercepcaoCorrelacao`/`CorrelacionadorIncidentes` receberão APIs de restauração explícitas e validadas para percepções/incidentes ativos, sem restaurar IDs de estímulos antigos como novos eventos.

A restauração deve respeitar capacities atuais, rejeitar entidades/fontes incompatíveis e nunca reaplicar impulsos históricos em A1. Incidentes restaurados servem apenas para continuidade e detecção correta de recuperação futura.
