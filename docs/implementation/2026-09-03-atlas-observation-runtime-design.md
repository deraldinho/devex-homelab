# Implementation Design — Atlas Observation Runtime 24/7 + Stimulus Bus

## Base e objetivo

- iniciativa: Issue #20 / Atlas Local Intelligence;
- base certificada: PR #22 / Atlas State & Reaction Foundation;
- base SHA: `8daca8506a17656388c9ff9c823af6830f9be578`;
- host autoritativo: `pentium`;
- modo operacional: observação contínua 24h/7d;
- consumidores futuros: Affective State Engine, LLM Reaction Loop, Audio Engine e Voice.

A slice cria o sistema nervoso do Atlas: observar equipamentos administrados, converter mudanças em estímulos estruturados, filtrar ruído e disponibilizar esses estímulos para consumidores internos sem acoplar a coleta à LLM ou à expressão.

## Princípios

1. Observação contínua, mas bounded.
2. Estado técnico continua determinístico e separado da interpretação afetiva.
3. A LLM não recebe polling bruto nem dados sem normalização.
4. Mudanças relevantes geram estímulos; ausência de mudança não gera spam.
5. Nenhum estímulo concede autoridade para executar ação.
6. Falha de um observador não derruba o runtime inteiro.
## Arquitetura

```text
Equipment / Service Adapters
        |
        v
StimulusSource collectors
        |
        v
ObservationRuntime
  |-- polling schedule
  |-- timeout/backoff
  |-- dedup/change detection
  |-- novelty scoring
        |
        v
StimulusBus (bounded)
  |             |
  |             +--> future Affective Engine
  |             +--> future LLM Reaction Loop
  |             `--> future Audio/Voice
  v
StimulusJournal (JSONL)
```

`ObservationRuntime` orquestra fontes, mas não interpreta emoções e não gera linguagem. `StimulusBus` publica apenas estruturas internas já normalizadas.

## Contrato `Stimulus`

Cada estímulo contém, no mínimo:

- `stimulus_id` único;
- `source`: equipamento/serviço de origem;
- `kind`: tipo estável do evento;
- `severity`: `info|notice|warning|critical`;
- `timestamp` UTC/local-aware ISO-8601;
- `payload`: mapa reduzido e serializável;
- `novelty`: `0.0..1.0`;
- `correlation_id` para agrupar eventos relacionados;
- `previous_fingerprint` e `current_fingerprint` quando houver mudança observada.
## Fontes iniciais

A primeira promoção cobre apenas fontes já administráveis pelo Pentium e com contrato observável existente:

- `pentium.self`: saúde local resumida;
- `core`: disponibilidade/saúde resumida;
- `x99`: disponibilidade/saúde resumida via contratos existentes;
- runners/jobs locais quando expostos por contrato já versionado.

MikroTik, DNS e Internet entram em slices posteriores, sem antecipar novos adapters nesta etapa.

## Detecção de mudança e ruído

Cada `StimulusSource` retorna um snapshot reduzido e determinístico. O runtime calcula fingerprint estável do conteúdo relevante.

- fingerprint igual ao anterior: não publica estímulo;
- fingerprint diferente: publica mudança;
- primeiro snapshot saudável: pode gerar `baseline_observed`, uma única vez por fonte;
- falhas repetidas idênticas são suprimidas durante cooldown;
- recuperação após falha gera estímulo explícito `recovered`;
- payloads grandes, logs brutos e secrets nunca entram no bus.

A novidade é calculada por regra leve, não por LLM. Eventos inéditos ou raros recebem novelty maior; repetição conhecida recebe novelty menor.

## StimulusBus

O bus é in-process e bounded. Ele não é broker distribuído e não cria dependência de Redis, Kafka ou MQTT nesta slice.

Regras:

- capacidade fixa configurável;
- consumidores usam leitura explícita/poll controlado;
- ao atingir capacidade, estímulos menos relevantes/mais antigos podem ser descartados por política determinística;
- `critical` não pode ser silenciosamente descartado enquanto houver item não crítico removível;
- métricas mínimas: publicados, deduplicados, descartados e critical preservados.
## ObservationRuntime 24/7

O runtime executa um loop cooperativo com intervalos por fonte, timeout e backoff. Uma fonte lenta ou falha não bloqueia as demais.

- polling padrão configurável por fonte;
- timeout obrigatório;
- backoff limitado após falha;
- jitter pequeno opcional para evitar alinhamento de probes;
- shutdown limpo;
- nenhum busy-loop;
- consumo de CPU/RAM deve permanecer baixo no Pentium em repouso.

Esta slice implementa o runtime como processo Python contínuo, mas não instala nova unidade systemd durante desenvolvimento. A promoção para serviço persistente ocorre somente depois de testes locais e CI; instalação física exige aprovação explícita porque altera execução persistente no Pentium.

## StimulusJournal

Todo estímulo publicado é registrado em JSONL append-only com campos do contrato e metadados mínimos do runtime. O journal é evidência operacional e futura fonte de memória episódica, mas não substitui uma base de memória de longo prazo.

Falha de escrita no journal é explícita e observável; não deve corromper o bus nem alterar estado técnico.

## Gatilhos futuros da LLM

A LLM não faz parte desta slice, mas o contrato deve permitir que o futuro LLM Reaction Loop seja acionado por:

- `severity=critical`;
- novelty acima de threshold;
- mudança relevante de estado;
- recuperação;
- interação humana;
- janela periódica de reflexão/resumo.

A LLM recebe estímulos normalizados e contexto reduzido, nunca o controle do loop de observação.

## Segurança e limites

- nenhuma ação CONTROL/DESTRUCTIVE;
- nenhum shell arbitrário;
- nenhuma URL arbitrária;
- sem alteração de rede, SSH, Tailscale ou MikroTik;
- sem LLM, áudio, STT ou TTS;
- sem secrets/logs brutos no payload;
- adapters usam apenas contratos já existentes ou fakes em teste.
## Testes e gates

TDD obrigatório para:

- modelo/freeze/serialização de `Stimulus`;
- fingerprint e deduplicação;
- novelty determinística;
- fila bounded e preservação de `critical`;
- timeout/backoff por fonte;
- isolamento de falha entre fontes;
- recuperação explícita;
- journal JSONL;
- shutdown limpo;
- ausência de polling quando nada mudou.

CI usa fontes fake e relógio injetável; não depende de equipamentos físicos. Após HEAD exato GREEN, a certificação física READ-only pode observar Pentium/Core/x99 sem alterar rede ou serviços.

## Definition of Done

A slice termina somente quando o runtime 24/7 está implementado e testado; estímulos são bounded, deduplicados e journaled; critical é preservado sob pressão; consumidores futuros têm contrato estável; toda suíte existente permanece GREEN; Foundation CI está GREEN no HEAD final; e a evidência física/as-built só é registrada se efetivamente observada.
