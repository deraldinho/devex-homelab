# Atlas S3 — Fast Dispatch / Reaction Integration

## Contexto

A S2 introduziu `EventoSemantico -> FastRouter -> DecisaoFastRouter`, com decisão determinística, bounded e sem I/O. A S3 conecta essa decisão aos subsistemas já existentes sem mover ownership nem colocar inferência no caminho crítico.

Base autoritativa da S3: `9407af45c5070dc52de4cfea85bd08acc32187cc`.

## Objetivo

Introduzir um dispatcher semântico que traduza `DecisaoFastRouter` em encaminhamentos tipados para os caminhos existentes:

`EventoSemantico -> FastRouter -> DecisaoFastRouter -> FastDispatcher`

Lanes suportadas:

- `DROP`
- `FAST_REACTION`
- `AFFECT`
- `CACHE_LOOKUP`
- `SLOW_LLM`

O dispatcher não executa decisão de negócio final; ele apenas coordena entrega bounded para portas explícitas.
## Ownership e limites

- `FastRouter` continua puro e responsável apenas por selecionar lanes.
- `FastDispatcher` não recalcula score, severidade, health ou autorização.
- `ReactionEngine` mantém ownership sobre seleção/supressão de reações.
- `MotorEstadoAfetivo` mantém ownership sobre evolução do estado afetivo.
- `CognitiveCache` mantém ownership sobre chave, TTL, hit/miss e invalidação.
- `ReactionLoopCognitivo`/LLM permanecem fora do caminho crítico.
- Nenhuma lane pode executar shell, SSH, rede ou CONTROL diretamente.

## Contrato do dispatcher

A S3 deve introduzir um resultado imutável de dispatch contendo, no mínimo:

- lanes solicitadas;
- lanes efetivamente entregues;
- lanes deferidas;
- lanes falhadas;
- motivo/identificador bounded por lane quando aplicável.

`DROP` permanece exclusivo e deve resultar em zero chamadas às portas.

Cada porta deve ter uma interface mínima, explícita e testável. O dispatcher não deve importar implementações concretas de LLM, rede, shell ou SSH.
## Semântica por lane

### FAST_REACTION
Encaminha o evento para uma porta de reação imediata. A porta pode adaptar o evento ao contrato já usado pelo `ReactionEngine`, mas a política de reação continua no engine.

### AFFECT
Encaminha o evento para uma porta afetiva que converte o estímulo semântico em impulso válido para `MotorEstadoAfetivo`. A tradução deve ser determinística e bounded.

### CACHE_LOOKUP
Solicita consulta delegada. O dispatcher não conhece chave, TTL ou política interna do cache. Hit/miss vira resultado de dispatch, nunca decisão de health ou autorização.

### SLOW_LLM
Nunca chama `llm_gateway` nem `ReactionLoopCognitivo` inline. Apenas agenda/defer uma intenção tipada para processamento posterior. Falha ou indisponibilidade dessa porta não bloqueia FAST_REACTION ou AFFECT.

## Ordem e isolamento de falhas

A ordem canônica de dispatch segue a ordem das lanes da `DecisaoFastRouter`. Falha em uma lane é registrada e não cancela lanes independentes seguintes, exceto `DROP`, que é terminal por contrato.

Critical/recovery devem continuar produzindo reação/afeto mesmo se qualquer mecanismo lento estiver indisponível.
## Abordagem escolhida

Foram descartadas duas alternativas:

1. Integrar diretamente o `FastRouter` com engines concretos: reduz arquivos, mas mistura decisão com execução e quebra testabilidade/ownership.
2. Reusar `ReactionLoopCognitivo` como dispatcher geral: acopla o fast path à camada cognitiva e aumenta risco de bloqueio por LLM/cache.

A abordagem adotada é um `FastDispatcher` separado, com portas pequenas e adaptadores explícitos. Ela preserva a pureza da S2 e permite testar cada lane sem dependência externa.

## Testes e gates

A implementação deve seguir TDD e cobrir:

- `DROP` não chama nenhuma porta;
- critical/recovery entregam FAST_REACTION + AFFECT sem LLM;
- ordem canônica das lanes;
- falha isolada não impede lane independente;
- CACHE_LOOKUP é delegado;
- SLOW_LLM é somente defer/agendamento, nunca inferência inline;
- dispatcher não importa `llm_gateway`, `subprocess`, `socket`, `requests`, `urllib` ou `paramiko`;
- full regression Atlas GREEN;
- `py_compile`, `bash -n`, `git diff --check` e Foundation CI GREEN no HEAD exato.

## Definition of Done

S3 está concluída quando o dispatcher tipado estiver integrado, os adapters necessários estiverem cobertos por testes, a documentação/installer/CI estiverem atualizados, o HEAD exato estiver certificado e um `/checkpoint` tiver sido publicado na PR da S3.