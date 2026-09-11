# Plano K1 — Cognitive Cache

## Objetivo
Implementar cache exato e bounded para reduzir inferências repetidas sem quebrar regras de negócio ou autoridade das camadas existentes.

## Ordem TDD
1. Contrato de cache, chave semântica e política de bypass.
2. LRU + TTL + métricas bounded.
3. Integração no `ReactionLoopCognitivo`.
4. Rejeição de resultados falhos e de respostas com `intencao`.
5. Configuração, installer e CI marker K1.
6. Regressão completa e Architecture & Business Rules Check final.

## DoD
- somente reflexão periódica cacheável no v1;
- top-level timestamp não invalida chave, timestamps internos invalidam;
- `INTERACAO_HUMANA`, critical/recovery/state changes sempre bypass;
- resposta com capability nunca armazenada;
- falha do cache cai para LLM normal;
- capacidade/TTL explícitos e testados;
- CI GREEN no HEAD exato antes de Ready.