# Implementation Design — Atlas State & Reaction Foundation

## Base

- iniciativa: Issue #20;
- dependência funcional: Issue #4 / PR #19;
- base congelada para design: `93527d7f54a78f9fbf59a89a272bba8e22d234c9`;
- CI dessa base: Foundation CI run `33786729400`, conclusão `success`;
- PR #19 permanece Draft e mergeable; esta slice não altera seu escopo.

## Objetivo da slice

Criar a primeira vertical real do Atlas sem LLM e sem áudio físico: receber observed state estruturado, calcular estado global/intensidade, selecionar uma reação semântica e registrar a transição.

O resultado da slice é consumível por um Audio Engine posterior e já é útil para CLI, testes, simulação e auditoria.

## Estrutura proposta

```text
infrastructure/pentium/atlas/
  config.json
  state_model.py
  health_engine.py
  reaction_engine.py
  journal.py
  cli.py
  tests/
```

### `state_model.py`

Define enums/estruturas:

- `TechnicalState`;
- `Signal`;
- `GlobalAssessment`;
- `ReactionDecision`.

Não executa I/O.

### `health_engine.py`

Recebe sinais já coletados/classificados. Não abre SSH, não chama Tailscale e não consulta MikroTik diretamente nesta slice.

Regras iniciais:

1. qualquer sinal obrigatório `critical` -> global `critical`;
2. caso contrário, maior severidade sustentada determina `stressed/degraded/busy/active/healthy`;
3. `recovered` é uma transição derivada quando o estado anterior era `degraded|stressed|critical` e a avaliação atual volta a `healthy|active`;
4. intensidade é o máximo dos sinais relevantes, limitada a `0..4`;
5. `reasons` preserva IDs/fontes dos sinais responsáveis pela decisão.

### `reaction_engine.py`

Recebe `GlobalAssessment`, configuração e histórico recente.

Responsabilidades:

- mapear estado técnico para categoria de expressão;
- escolher variante de pool por peso;
- injetar RNG/clock para testes determinísticos;
- bloquear repetição recente;
- aplicar cooldown por categoria/severidade;
- permitir meme apenas quando configurado;
- em `critical`, sempre emitir decisão canônica de criticidade; meme, quando escolhido, é secundário.

Não reproduz áudio e não baixa conteúdo.

### `journal.py`

Append-only JSONL no diretório de dados do Atlas. Cada linha contém:

- `timestamp`;
- `previous_state`;
- `state`;
- `intensity`;
- `reasons`;
- `reaction_category`;
- `reaction_id`;
- `meme_id` opcional.

Escrita usa flush e estrutura por linha para tolerar término entre eventos sem corromper registros anteriores.

### `cli.py`

Entrada inicial: snapshot JSON por arquivo/stdin.

Saída:

- JSON estável para automação;
- resumo humano ASCII opcional.

A CLI é ferramenta de validação/simulação; não executa ações remotas.

## Configuração

`config.json` contém somente valores não secretos:

- modo (`quiet|normal|expressive|chaos`);
- duração mínima/cooldowns;
- tamanho da memória anti-repeat;
- categorias e IDs de reação;
- pesos/raridade;
- flag de memes por modo.

Nenhum caminho externo arbitrário ou URL executável entra no contrato inicial.

## Integração com contratos existentes

A slice deve consumir/adaptar resultados do heartbeat/network/Agent em uma camada posterior ou fixtures de integração. Não duplicar `tailscale status`, SSH ou health probes já existentes.

Isso preserva ownership:

```text
network/heartbeat/agent -> observed state
Atlas health_engine      -> interpretação global
Atlas reaction_engine    -> expressão
```

## Testes

TDD obrigatório.

Cobertura mínima:

- precedência de severidade;
- componente opcional degradado não vira `critical`;
- intensidade limitada a 0..4;
- transição `critical -> healthy` produz `recovered`;
- `healthy -> healthy` não produz falso `recovered`;
- seleção ponderada determinística com RNG injetado;
- anti-repeat;
- cooldown;
- critical sempre mantém reação canônica;
- meme secundário não substitui critical;
- journal grava JSONL parseável;
- CLI rejeita schema inválido com exit code distinto.

## Segurança e falhas

- schema inválido -> erro de configuração/entrada, sem side effect;
- pool vazio -> decisão silenciosa explícita, não exceção não tratada;
- journal indisponível -> avaliação/reação ainda retornam resultado e reportam erro de persistência;
- nenhuma rede, shell ou subprocesso nesta slice;
- nenhum secret/meme/áudio de terceiros no Git.

## Gate de promoção

1. testes locais GREEN;
2. `git diff --check`;
3. Foundation CI GREEN no HEAD exato;
4. somente depois, próxima slice adiciona Audio Engine e certificação física de playback no Pentium.
