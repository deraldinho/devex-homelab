# Atlas Observation → Cognitive Context Bridge Design

## Objetivo
Ligar a cognição do Atlas ao estado observacional/afetivo real já certificado, sem permitir que cognição/LLM alterem A1/A2/A3/A4 e sem reativar a voz nesta slice.

## Base
A slice parte do SHA certificado `0b6e7e974043d2e5942ad9a1ca339713b1a1149c` da branch `atlas/issue-20-affective-runtime-boot`.

## Problema atual
`ReactionLoopCognitivo` e `ContextoCognitivoBuilder` já aceitam percepção, incidente, estado afetivo, emoção e foco reais. Porém `HumanContextProvider` ainda sintetiza esses valores a partir de `health/latest.json`.

Consequência: CLI/voz podem enviar ao LLM um estado afetivo fictício e desconectado do owner real A1/A3/A4.

## Decisão arquitetural
O `atlas-observation.service` continuará sendo o único owner afetivo e publicará uma projeção cognitiva atômica após concluir o processamento/persistência do evento aceito.

Arquivo canônico de leitura:
`~/pentium-agent/atlas/runtime/cognitive-observation-context.json`

Cognição, CLI e voz serão somente readers dessa projeção. Nenhum reader escreverá A1/A2/A3/A4, `visual-state.json` ou o snapshot cognitivo.

## Fronteira de verdade
- estado técnico continua vindo do health engine existente;
- percepção/incidente vêm de A3;
- estado afetivo vem de A1;
- emoção/foco vêm de A4;
- a projeção cognitiva é snapshot de leitura, nunca nova fonte de verdade.
## Schema da projeção
`cognitive-observation-context.json` terá `schema_version: 1`, `generated_at`, `expected_sha`, `source_stimulus_id`, `entity_id`, `perception`, `incident`, `affective_state`, `emotion`, `focus`, `recent_changes` e `affected_dependencies`.

A projeção NÃO contém `technical_state`; o `HumanContextProvider` combina o snapshot com `health/latest.json` somente na leitura cognitiva.

Campos bounded:
- `recent_changes`: máximo igual a `config_cognitiva.contexto.max_mudancas_recentes`;
- `affected_dependencies`: máximo igual a `max_dependencias_afetadas`;
- nuances: máximo igual a `max_nuances`;
- strings e payload total respeitam os limites cognitivos já existentes.

`recent_changes` contém somente metadados/fields técnicos do `Stimulus` já aceito; não inclui áudio, transcript, prompts, secrets ou conteúdo arbitrário não filtrado.

## Publicação
Criar `cognitive_observation_projection.py` com serializer/validator/publisher atômico.

`AffectiveComposition.processar()` permanece o boundary de evento aceito. Quando o pipeline retorna `aceito=True`, a ordem será:
1. processar A3/A2/A1/A4;
2. persistir A3 → A2 → A1 → A4;
3. construir projeção usando os objetos em memória do mesmo evento;
4. publicar por temp + fsync + `os.replace`;
5. registrar falha de projeção em diagnóstico bounded sem retroagir o Stimulus.

Falha da projeção não torna o ObservationRuntime indisponível, mas o health observacional deve marcar o bridge como degradado até uma publicação válida subsequente.

Eventos ignorados por source routing ou duplicados não publicam nova geração cognitiva.
## HumanContextProvider real
`HumanContextProvider` passa a receber dois caminhos: health técnico e projeção cognitiva observacional.

Na leitura:
- lê o health técnico e converte somente o estado técnico para `GlobalAssessment`;
- lê/valida a projeção cognitiva;
- desserializa percepção, incidente, A1, emoção e foco reais;
- entrega esses objetos ao `HumanInteractionGateway`/`ReactionLoopCognitivo`.

Nenhum fallback emocional sintético é permitido.

Se a projeção estiver ausente, inválida, com schema desconhecido, SHA incompatível quando exigido, ou stale além do limite configurado, o provider lança `CognitiveContextUnavailable`.

`HumanInteractionGateway` trata essa condição sem chamar o LLM e retorna uma resposta local curta informando que o contexto observacional está indisponível. A indisponibilidade cognitiva não afeta observation/afeto.

Adicionar em `config_cognitiva.json` seção versionada `observation_bridge` com:
- `snapshot_path`: `~/pentium-agent/atlas/runtime/cognitive-observation-context.json`;
- `max_snapshot_age_s`: 180;
- `require_expected_sha`: true em certificação/produção quando `ATLAS_EXPECTED_SHA` estiver definido.

## Incidente e entidade relevantes
A projeção usa a percepção do evento processado e o incidente relevante já selecionado pelo pipeline/adaptador. `entity_id` deve corresponder à percepção real daquele evento.

`affected_dependencies` vem das entidades afetadas do incidente relevante quando existir; sem incidente, é vazio. Não será inferido um incidente a partir de emoção/foco.

## Mudanças recentes
A composição mantém um deque bounded dos últimos Stimuli afetivos aceitos e roteados. O deque existe apenas para projeção cognitiva e não é persistido como nova memória semântica.

Após restart, `recent_changes` começa vazio e é preenchido por novos eventos; A1/A3/A4 restaurados continuam disponíveis na primeira projeção nova.
## Voz e ativação autônoma
A voz permanece `inactive/disabled` nesta slice. `voice_daemon` poderá consumir o novo provider quando reativado futuramente, mas nenhum teste/deploy desta slice habilita captura/STT/TTS.

Eventos observacionais NÃO disparam `ReactionLoopCognitivo` autonomamente nesta slice. O bridge fornece contexto real para interações humanas; ativação autônoma por criticidade/mudança afetiva/recuperação fica para a próxima slice.

## Segurança
- LLM permanece reader de contexto e não recebe referência mutável aos owners;
- prompt continua proibindo alteração de estado técnico/afetivo/memória/capabilities;
- CONTROL continua default-deny;
- snapshot não contém transcript, áudio, biometria, tokens, chaves ou comandos;
- nenhuma nova porta TCP, broker ou dependência do x99;
- dashboard permanece read-only.

## Testes e gates
TDD RED→GREEN deve cobrir:
- serializer/validator e atomic write do snapshot;
- bounds e rejeição de schema/payload inválidos;
- ausência de `technical_state` na projeção;
- publicação somente após evento afetivo aceito;
- nenhum publish em duplicate/unmapped source;
- `HumanContextProvider` reconstruindo A1/A3/A4 reais;
- snapshot ausente/inválido/stale bloqueando LLM sem fabricar estado;
- CLI usando o provider real;
- health do observation bridge degraded/healthy conforme publish;
- voz permanece inactive/disabled.

Regressão obrigatória: suíte Atlas + dashboard, py_compile, JSON, `bash -n`, diff-check e UTF-8.

## Certificação física no Pentium
No SHA exato:
1. observation service active/healthy;
2. voz inactive/disabled;
3. evento real gera `cognitive-observation-context.json`;
4. snapshot e A1/A3/A4 persistidos correspondem à mesma entidade/estado do evento;
5. CLI constrói `ContextoCognitivo` com percepção/emoção/foco reais do snapshot;
6. snapshot stale/corrompido em cópia isolada não chama LLM e não impacta observation;
7. restart continua restaurando A1/A2/A3/A4 e gera nova projeção no próximo evento.

## Fora de escopo
- ativação cognitiva autônoma por eventos observacionais;
- reativar voz ou ANC;
- permitir LLM alterar afeto/percepção;
- substituir health engine por A3;
- persistir `recent_changes` como memória;
- mudanças em L2jToren.

## Contratos internos necessários
`ResultadoPipelineAfetivoObservacional` passa a expor também o `ResultadoPipelinePercepcaoCorrelacao` do mesmo processamento aceito. Isso evita reler A3 depois que um incidente recuperado já foi removido da coleção de ativos.

O publisher cognitivo recebe diretamente: `Stimulus`, resultado A3 daquele evento, `ImpactoAfetivoObservacional` e `ResultadoFocoEmocao`. Assim percepção, incidente/recovery, A1 e A4 pertencem à mesma transição lógica.

Essa ampliação é somente leitura; não transfere ownership nem duplica processamento.

## Estado do bridge no health
A composição mantém estado corrente bounded do bridge: `last_publish_at`, `last_publish_stimulus_id` e `current_error`.

Falha de publish define `current_error`; publicação válida posterior limpa `current_error`. O health usa o estado corrente, não o histórico completo de erros, portanto uma falha transitória recuperada não deixa o serviço permanentemente degraded.

O histórico diagnóstico pode permanecer em deque bounded separado para troubleshooting.

## Compatibilidade do health técnico
A conversão de `health/latest.json` para `GlobalAssessment` mantém a política técnica atual nesta slice. O bridge apenas remove a síntese de percepção/afeto/emoção/foco do `HumanContextProvider`; não redefine severidade técnica nem thresholds do health engine.
