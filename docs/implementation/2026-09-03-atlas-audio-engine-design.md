# Implementation Design — Atlas Audio Engine + Creative Commons Library

## Base e objetivo

- iniciativa: Issue #20 / Atlas Local Intelligence;
- base funcional certificada: PR #22;
- base SHA: `8daca8506a17656388c9ff9c823af6830f9be578`;
- Foundation CI da base: GREEN;
- host autoritativo de execução: `pentium`;
- saída física: exclusivamente o dispositivo de áudio padrão do Pentium.

A slice transforma `ReactionDecision` em playback local real, preservando a separação entre decisão semântica e reprodução física.

## Escopo

Incluído nesta slice:

- resolução de mídia por `reaction_id`/categoria;
- manifesto versionado da biblioteca sonora;
- download de mídia durante instalação, sem armazenar áudio binário no Git;
- validação SHA-256 antes de promover asset para uso;
- licenças permitidas: `CC0`, `CC-BY` e `CC-BY-SA`;
- backend leve para playback no dispositivo padrão do Pentium;
- fila bounded, prioridade e preempção crítica;
- journal de resultado de playback;
- certificação física com áudio real no Pentium.
## Fora de escopo

- LLM, STT e TTS;
- captura de microfone;
- reprodução em x99, Core ou MikroTik;
- seleção manual de placa/índice ALSA;
- shell arbitrário;
- mídia sem licença Creative Commons verificável;
- download ou execução de conteúdo cujo hash não corresponda ao manifesto.

## Arquitetura

```text
ReactionDecision
      |
      v
AudioResolver ----> audio-library.json
      |
      v
PriorityQueue (bounded)
      |
      v
AudioEngine
      |
      +--> AudioBackend(aplay/ALSA default device)
      |
      `--> playback journal
```

`ReactionEngine` continua sendo dono da decisão semântica. `AudioEngine` apenas resolve, agenda e reproduz o asset correspondente.
## Manifesto da biblioteca

Cada asset declara no mínimo:

- `asset_id`;
- `reaction_id` e/ou categoria;
- `source_url`;
- `author`;
- `license`: `CC0|CC-BY|CC-BY-SA`;
- `license_url`;
- `attribution` quando aplicável;
- `sha256`;
- `format`;
- `duration_ms` quando conhecida.

Política de preferência: `CC0` > `CC-BY` > `CC-BY-SA`. Assets CC-BY/CC-BY-SA mantêm atribuição no manifesto e documentação gerada. Nenhum binário de áudio entra no Git nesta slice.

## Biblioteca inicial

A primeira certificação exige sons reais para:

- `healthy` / calm;
- `busy` / working;
- `critical`;
- `recovered` / relief.

Cada família deve possuir múltiplas variantes quando houver mídia licenciada adequada. `critical.canonical` deve possuir pelo menos um asset obrigatório independente de meme.
## Prioridade, fila e preempção

- a fila é bounded e pequena;
- eventos obsoletos podem ser descartados antes do playback;
- `critical` possui prioridade máxima;
- chegada de `critical` interrompe imediatamente qualquer playback não crítico em andamento;
- um meme nunca substitui nem bloqueia `critical.canonical`;
- eventos não críticos não devem acumular backlog audível.

## Backend de áudio

O backend inicial é ALSA via `aplay`, encapsulado por uma interface testável. O domínio não conhece argumentos de `aplay`, hardware ALSA ou índice de dispositivo.

Regras:

- usar sempre o dispositivo padrão do sistema;
- não persistir nome/id de hardware;
- timeout obrigatório por playback;
- processo de playback deve ser terminável para suportar preempção crítica;
- ausência do backend é falha explícita do Audio Engine, não falha do Health/Reaction Engine.

## Instalação e mídia

O instalador user-level cria `~/pentium-agent/atlas/media/`, baixa cada asset para arquivo temporário, valida SHA-256 e só então faz promoção atômica para o nome final. Download parcial, licença não permitida ou hash divergente não podem substituir um asset válido existente.
## Falhas e journal

Resultados mínimos de playback:

- `played`;
- `suppressed`;
- `dropped_obsolete`;
- `preempted`;
- `asset_missing`;
- `hash_invalid`;
- `backend_unavailable`;
- `playback_failed`;
- `timeout`.

O journal registra `timestamp`, `reaction_id`, `asset_id`, `result`, duração observada e causa de erro quando houver. Falhas de áudio não alteram o estado técnico calculado pelo Health Engine.

## Segurança

O manifest é a única autoridade para URLs e hashes de mídia. O runtime não recebe URL arbitrária e não executa comandos derivados de conteúdo externo. O backend monta argv fixo e nunca usa shell. Downloads acontecem somente na etapa explícita de instalação/sincronização da biblioteca, não no hot path de reação.

## Testes e gates

TDD obrigatório para resolver assets, validar licenças, SHA-256, fila bounded, descarte de obsoletos, prioridade, preempção de `critical`, backend fake, timeout e journal.

CI usa backend fake e não depende de placa de som. Após HEAD exato GREEN, a certificação física no Pentium deve comprovar `healthy`, `busy`, `critical` preemptando áudio normal e `recovered`, sempre pelo dispositivo padrão.

A slice só é considerada concluída após teste físico audível, evidência no as-built, CI GREEN do HEAD final e `/checkpoint` da PR correspondente.