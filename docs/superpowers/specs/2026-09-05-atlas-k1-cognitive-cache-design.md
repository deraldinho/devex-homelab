# Atlas K1 — Cognitive Cache Design

## Objetivo

Reduzir inferências repetidas da mini LLM sem permitir resposta obsoleta em eventos sensíveis e sem transferir autoridade ao cache.

## Architecture & Business Rules Check

- O cache fica entre `ReactionLoopCognitivo` e `LLMGateway`.
- O cache nunca altera `TechnicalState`, memória, afeto, percepção ou autorização de capabilities.
- `CapabilityPolicy` continua sendo avaliada após a obtenção da resposta.
- Cache hit não executa capability e não concede autorização.
- Falha do cache degrada para inferência normal.
- O cache é bounded, local e não persistente no K1.

## Política de cache v1

Somente `REFLEXAO_PERIODICA` é cacheável automaticamente. São bypass obrigatório: interação humana, criticidade técnica, novidade relevante, mudança de estado, mudança afetiva, recuperação importante e expectativa quebrada.

A chave é SHA-256 de um payload canônico contendo tarefa, modelo, versão da policy e contexto sem o `timestamp` top-level. Timestamps internos de incidentes, memórias ou mudanças permanecem na chave e invalidam o cache.
## Limites

- capacidade inicial: 64 entradas;
- TTL inicial: 300 segundos;
- eviction: LRU;
- somente resultados de inferência bem-sucedidos entram no cache;
- mudança de tarefa, modelo, policy ou contexto semântico gera MISS;
- cache não usa embeddings nem similaridade semântica no v1.

## Observabilidade

O cache expõe contadores bounded de hit, miss, bypass, expired e eviction. O benchmark físico C5 deverá medir taxa de hit e economia de chamadas à LLM separadamente da latência de inferência real.

## Compatibilidade

M1 continua sendo dona de memória persistente. C1 continua dono do contexto bounded. C2 continua dono do acesso à LLM. C4 continua dono da autorização de capabilities. K1 apenas evita inferência redundante em cenários explicitamente permitidos.
## Regra operacional adicional

Uma resposta estruturada que contenha `intencao` nunca é admitida no cache. Mesmo em reflexão periódica, qualquer proposta de capability deve nascer de uma inferência atual e passar novamente pela `CapabilityPolicy`.