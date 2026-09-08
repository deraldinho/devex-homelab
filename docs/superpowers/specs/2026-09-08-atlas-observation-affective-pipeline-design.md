# Atlas Observation → Affective Pipeline Design

## Objetivo
Conectar os eventos observacionais reais do Atlas ao estado afetivo e ao avatar sem colocar regras emocionais dentro do `ObservationRuntime` e sem criar um segundo consumidor destrutivo do `StimulusBus`.

## Problema atual
O `ObservationRuntime` produz `Stimulus` e publica no `StimulusBus`. O pipeline A3 (`PipelinePercepcaoCorrelacao`) transforma estímulos em percepção e incidentes, enquanto A1/A2/A4 já modelam estado afetivo, vínculos, foco e emoção. Porém não existe hoje um mapper de produção que converta percepção/incidentes/contexto em `ImpulsoAfetivo`.

Conectar `Stimulus` diretamente ao `AffectiveRuntime` faria o runtime visual inventar semântica afetiva. Adicionar outro consumidor via `StimulusBus.poll()` criaria competição destrutiva por eventos.

## Decisão arquitetural
Criar um pipeline observacional afetivo dedicado, acionado somente após um estímulo ser aceito pelo `StimulusBus`.

```text
ObservationRuntime
      │ accepted_stimulus_sink
      ▼
PipelineAfetivoObservacional
      │
      ├─ PipelinePercepcaoCorrelacao (A3)
      ├─ AdaptadorImpactoAfetivo
      ├─ MotorEstadoAfetivo (A1)
      ├─ ContextoAfetivo (A2)
      ├─ ContextoFocoEmocao (A4)
      └─ AffectiveRuntime visual
```

## Ownership e fontes de verdade
- `ObservationRuntime` continua dono apenas da coleta, deduplicação, correlação básica de source e publicação de `Stimulus`.
- `StimulusBus` continua sendo a fila bounded existente; este design não adiciona `poll()` afetivo.
- A3 continua dono de percepção e incidentes técnicos.
- A2 continua dono de entidades, vínculos, expectativas e histórico operacional.
- A1 continua dono exclusivo do `EstadoAfetivo` mutável.
- A4 continua dono de foco e emoção derivada.
- `AffectiveRuntime` continua apenas projetando `ResultadoFocoEmocao` no visual.
- `AdaptadorImpactoAfetivo` não persiste estado e não possui relógio próprio.

## Extensão mínima em `ObservationRuntime`
Adicionar callback opcional:

```python
accepted_stimulus_sink: Callable[[Stimulus], None] | None = None
```

O callback é invocado somente quando `StimulusBus.publish()` retorna `accepted=True`.

Falhas no callback são capturadas e registradas em `ObservationRuntime.errors()` com marcador estável; elas não podem impedir journal, scheduler, outras sources ou o retorno de `run_once()`.

Uma deduplicação que retorna `None` não invoca o callback. Um estímulo recusado por pressão da fila também não invoca o callback.

## `AdaptadorImpactoAfetivo`
Responsabilidade: converter somente fatos já consolidados em um impacto afetivo bounded e explicável.

Entradas mínimas:
- `Stimulus` aceito;
- `ResultadoPipelinePercepcaoCorrelacao` de A3;
- `VinculoAfetivo | None` de A2;
- fator de reincidência já calculado por A2 quando aplicável.

Saída:
- `ImpactoAfetivoObservacional`, estrutura imutável contendo `ImpulsoAfetivo`, `AssuntoFoco`, `ContextoEmocional` e metadados de idempotência.

O adaptador não consulta LLM, não lê health diretamente, não executa shell e não altera A1/A2/A3/A4.

### Regras de impacto
O vínculo modula o impacto; vínculo ausente usa peso operacional mínimo configurado, nunca importância máxima implícita.

Estados de percepção inseguros (`PARCIALMENTE_OBSERVADO`, `INACESSIVEL`, `DESCONHECIDO`) podem aumentar ativação/curiosidade/vigilância, mas não equivalem automaticamente a incidente crítico.

Incidente técnico confirmado pode elevar estresse e ativação proporcionalmente à gravidade normalizada, confiança causal e vínculo efetivo.

Recuperação produz impulso próprio: reduz estresse, favorece valência/confiança e marca `recuperacao_relevante=True` para A4.

Reincidência pode aumentar frustração por `ContextoEmocional.reincidencia`; não cria novo rótulo emocional.

## Gravidade normalizada
A tradução de gravidade técnica deve ser configurável por rótulo conhecido do domínio de incidentes e retornar valor bounded `0.0..1.0`.

Rótulo desconhecido não pode virar crítico por default. O fallback é conservador e observável.

A severidade do `Stimulus` pode contribuir para urgência/novidade, mas não substitui `IncidenteTecnico.gravidade` quando há incidente confirmado.

## Idempotência
A identidade primária do processamento é `stimulus.stimulus_id`.

`PipelineAfetivoObservacional` mantém conjunto bounded de IDs recentemente processados. Reentrega do mesmo estímulo retorna resultado `aceito=False` sem aplicar segundo impulso, registrar segunda experiência nem republicar o mesmo visual.

Incidentes são tratados por transição observada, não por mera presença repetida na lista A3. O pipeline mantém estado bounded por `incidente_id` para detectar abertura e recuperação uma única vez.

## Histórico A2
Uma abertura de incidente relevante registra `ExperienciaOperacional(..., INCIDENTE, ...)` para a entidade principal se ela existir em A2.

Uma recuperação relevante registra `RECUPERACAO` uma única vez.

Falha em registrar histórico por entidade desconhecida não deve inventar entidade nem derrubar o pipeline; deve virar erro/diagnóstico bounded no pipeline.

## `PipelineAfetivoObservacional`
Responsabilidade: coordenar as camadas existentes sem tomar ownership delas.

Fluxo por estímulo aceito:
1. rejeitar duplicata por `stimulus_id`;
2. chamar A3 `processar(stimulus)`;
3. obter vínculo efetivo A2 da entidade percebida quando existir;
4. calcular reincidência A2 quando houver histórico conhecido;
5. derivar `ImpactoAfetivoObservacional`;
6. registrar experiência A2 somente em transições relevantes;
7. aplicar `ImpulsoAfetivo` em A1 usando `stimulus.timestamp`;
8. montar assuntos de foco bounded a partir do impacto/transições ativas;
9. chamar A4 `processar(...)`;
10. enviar `ResultadoFocoEmocao` ao `AffectiveRuntime` visual.

A ordem acima impede que o visual seja publicado antes de A1/A4 consolidarem o mesmo evento.

## Foco
Cada impacto observacional gera no máximo um `AssuntoFoco` principal candidato para a entidade relacionada ao estímulo/transição.

`assunto_id` deve ser estável por incidente quando houver `incidente_id`; para observação sem incidente, deriva de entidade + categoria observacional, não de payload bruto.

A lista enviada a A4 é bounded e ordenada deterministicamente. Nenhum texto de log, transcript ou payload arbitrário vira `assunto_id`.

## Contexto emocional A4
`ContextoEmocional` é montado somente com sinais consolidados:
- `reincidencia`: valor bounded vindo de A2;
- `criticidade_relevante`: verdadeiro somente para incidente/transição classificado como crítico pela regra configurada;
- `recuperacao_relevante`: verdadeiro apenas na transição de recuperação;
- `percepcao_insegura`: verdadeiro quando A3 estiver parcial/inacessível/desconhecido ou em conflito.

## Boundedness e pressão
Não existe nova thread obrigatória nem busy loop.

O callback é síncrono nesta slice e deve ser curto. O pipeline mantém apenas:
- IDs de estímulos recentes em capacidade fixa;
- estado recente de incidentes em capacidade fixa;
- assuntos ativos em capacidade fixa;
- erros diagnósticos em capacidade fixa.

Se medição futura demonstrar que o callback excede o orçamento do Observation Runtime, uma fila dedicada bounded poderá ser adicionada em outra slice; não será antecipada aqui.

## Fail-safe
Uma falha do pipeline afetivo nunca invalida o `Stimulus` já aceito pelo bus nem impede o journal observacional.

A1 não é mutado se A3/adaptador falhar antes da geração do impulso.

Falha no `AffectiveRuntime` visual permanece isolada pelo contrato já implementado.

## Configuração
Adicionar configuração versionada para:
- capacidades bounded de idempotência/incidentes/assuntos/erros;
- pesos mínimos/máximos de impacto;
- mapa de gravidade técnica conhecida → `0.0..1.0`;
- ganhos máximos por dimensão afetiva para incidente, percepção insegura e recuperação.

Todos os ganhos devem permanecer em `[-1.0, 1.0]` e a aplicação final continua bounded pelo `EstadoAfetivo` existente.

## Arquivos planejados
- `adaptador_impacto_afetivo.py`
- `pipeline_afetivo_observacional.py`
- `config_observation_affective.json`
- testes dedicados para os dois módulos e integração com `ObservationRuntime`
- alterações mínimas em `observation_runtime.py`, `install-user.sh` e Foundation CI

## Fora de escopo
- mudar algoritmos internos de A3;
- alterar rótulos A4;
- criar entidades/vínculos automaticamente;
- LLM decidir impulso, gravidade, foco ou emoção;
- consumir `StimulusBus.poll()`;
- alterar dashboard além do contrato visual já existente;
- qualquer código em L2jToren.

## Gates de conclusão
- TDD RED→GREEN para callback aceito/recusado/deduplicado/falho;
- TDD para impacto, recuperação, percepção insegura, vínculo e fallback de gravidade;
- TDD para idempotência e transição única de incidente/recuperação;
- integração `ObservationRuntime → A3 → A2/A1/A4 → AffectiveRuntime → visual-state.json`;
- suíte Atlas completa e dashboard GREEN;
- `py_compile`, JSON, `bash -n`, `git diff --check`, guard UTF-8;
- gate CI dedicado no HEAD exato.
