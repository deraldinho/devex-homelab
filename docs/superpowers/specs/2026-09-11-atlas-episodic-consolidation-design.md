# Atlas M2 — Consolidação Episódica com Provenance, Reliability e Generation Fencing

## Objetivo

Adicionar uma camada de consolidação episódica entre observações/eventos e a memória persistente do Atlas, preservando integralmente o motor afetivo, o Reaction Loop e o contrato do M1.

A slice reduz write-through de eventos isolados, agrupa experiências coerentes em segmentos bounded e só promove informação para `MemoryManager` após fechamento explícito do episódio.

## Princípios

- A LLM não decide persistência, exclusão, promoção nem fechamento de episódio.
- Segmentação, fencing, limites e aceitação são determinísticos.
- `MemoryManager`, `MemoryStore` e `MemoryRetriever` continuam sendo as portas canônicas de memória de longo prazo.
- O motor afetivo permanece independente; nenhuma memória técnica substitui `ContextoAfetivo`.
- Toda memória consolidada deve possuir provenance verificável e `generation_id` compatível.
- Falha da consolidação degrada para operação sem nova memória; não derruba o Reaction Loop.
- Nenhum segredo, payload bruto ou credencial pode entrar no buffer episódico.

## Fluxo canônico

`observação validada -> adapter -> EpisodicBuffer -> Segmentador -> episódio OPEN -> fechamento -> EpisodicConsolidator -> persistência exactly-once -> MemoryStore + provenance`

A leitura permanece:

`MemoryStore -> MemoryRetriever -> ContextoCognitivoBuilder -> LLM`

## Modelo de segmento

Cada episódio possui `segment_id`, `generation_id`, `category`, `entity_id`, `opened_at`, `updated_at`, `status`, `closure_reason`, `event_count`, `byte_count` e uma coleção bounded de evidências.

Cada evidência possui `event_id`, `occurred_at`, `source`, `source_kind`, `content_reduced`, `reliability`, `verified`, `generation_id`, `dedupe_key`, `importance` e `criticality`.

Categorias iniciais: `incident`, `deployment`, `development_session`, `human_interaction` e `generic`. Novas categorias exigem contrato explícito; não serão inferidas livremente pela LLM.

## Fechamento de episódio

Um segmento OPEN fecha quando ocorrer a primeira condição aplicável:

1. evento terminal explícito;
2. mudança incompatível de chave semântica/categoria;
3. `idle_timeout` configurável;
4. `max_events` atingido;
5. `max_bytes` atingido;
6. troca de `generation_id`.

Mudança de geração fecha o segmento anterior com `closure_reason=generation_fence`; eventos da nova geração nunca são anexados ao segmento antigo.

## Bounds e configuração

Além dos limites por segmento (`max_events` e `max_bytes`), a M2 define `max_open_segments`, `max_pending_bytes` e `idle_timeout_s`. Todos os valores efetivos no runtime devem ser positivos; saturação fecha ou rejeita de forma determinística sem crescimento ilimitado. Para preservar compatibilidade do `config_memory.json` schema 1, o loader aceita ausência das novas chaves e aplica defaults seguros; quando presentes, elas são validadas explicitamente. A versão interna do banco SQLite permanece independente desse schema de configuração.

## Consolidação

O consolidator produz no máximo um conjunto pequeno e bounded de `MemoryRecord` a partir de um segmento CLOSED. A primeira versão usa regras determinísticas para conteúdo, score e deduplicação. Um summarizer por LLM poderá ser plugado depois apenas como produtor de `MemoryCandidate`, sujeito à mesma validação do `MemoryManager`.

## Provenance e confiabilidade

A provenance preserva a origem de cada memória consolidada sem armazenar payload bruto. O registro final deve permitir rastrear `segment_id`, fontes participantes, intervalo temporal, quantidade de evidências e geração de origem.

`reliability` é um snapshot bounded entre 0 e 1 atribuído pela fonte/política no momento da ingestão. Nesta slice ele não é aprendizado autônomo: serve para filtrar e ponderar consolidação. Um registry adaptativo de competência fica fora do escopo M2.

Memórias consolidadas recebem confiança calculada a partir das evidências aceitas; evidência não verificada ou de baixa confiabilidade não pode elevar a confiança final.

## Generation fencing e restart

`generation_id` identifica a execução lógica do runtime que produziu o evento e muda a cada novo processo/runtime. O buffer rejeita append em segmento cuja geração difere da evidência. O consolidator rejeita segmentos com mistura de gerações, mesmo que o store esteja corrompido ou tenha sido manipulado externamente.

Um segmento OPEN recuperado após restart pertence necessariamente à geração anterior. Ele é carregado apenas para recuperação, fechado com `closure_reason=restart_recovery` e consolidado de forma idempotente; nenhum evento da nova geração pode ser anexado a ele. Isso preserva eventos pendentes sem enfraquecer a fence.

O `MemoryRetriever` não precisa esconder memórias históricas de gerações anteriores por padrão; geração é provenance, não TTL. Porém, memórias WORKING ou candidatos ainda não consolidados nunca atravessam a fence.

## Persistência, provenance e schema

O schema interno do banco evolui de v1 para v2 por migração transacional e idempotente. Essa versão de banco é independente do `schema_version` do arquivo `config_memory.json`, que continua versionando apenas o contrato de configuração.

A tabela `memories` mantém compatibilidade lógica. Novas tabelas armazenam segmentos, evidências e `memory_provenance`, com foreign keys e índices por `status`, `generation_id`, `entity_id` e tempo. `MemoryRecord` não recebe campos novos de provenance nesta slice; o vínculo é externo por `memory_id`, preservando callers M1.

A migração v1 -> v2 não apaga nem reescreve memórias existentes. Versão desconhecida continua falhando fechado. A consolidação usa uma operação transacional e idempotente, conceitualmente `remember_consolidated(segment_id, records, provenance)`, que grava memória, provenance e transição `CLOSED -> CONSOLIDATED` na mesma transação SQLite. Reprocessar o mesmo `segment_id` não pode incrementar `frequency` nem criar efeitos duplicados.

## Integração, ingestão e compatibilidade

Nenhum caller existente de `MemoryRetriever` ou `ReactionLoopCognitivo` muda nesta slice. A nova ingestão episódica entra antes da persistência canônica, mas não recebe `Stimulus.payload` bruto.

Para infraestrutura, apenas percepção validada/correlação ou outro resultado determinístico aceito passa por um adapter explícito que produz `EpisodicEvidence` reduzida. Interação humana, desenvolvimento/GitHub e novas fontes exigem adapters próprios, com allowlist de campos, redução de conteúdo e política de reliability. Caminhos legados que gravam memória diretamente continuam válidos até migração explícita e mensurável.

`ContextoAfetivo`, vínculos, expectativas e experiências operacionais não são reimplementados nem espelhados automaticamente em memória técnica. Quando uma experiência afetiva gerar uma memória relacional no futuro, isso exigirá um adaptador explícito e testado.

## Observabilidade

Métricas mínimas: `episodes_open`, `episodes_closed_total`, `episode_events_total`, `episode_bytes`, `consolidation_success_total`, `consolidation_rejected_total`, `generation_fence_total`, `stale_event_rejected_total` e latência de consolidação. Logs não devem conter conteúdo sensível das evidências.

## Testes e gates

- TDD para modelo, buffer, fechamento, fencing, store e consolidator.
- Teste de restart com segmento OPEN da geração anterior: recuperação fecha como `restart_recovery`, consolida uma única vez e não aceita append da nova geração.
- Teste de mistura de gerações deve falhar fechado.
- Teste de fechamento por evento terminal, idle, bytes e quantidade.
- Testes de saturação para `max_open_segments` e `max_pending_bytes` sem crescimento ilimitado.
- Teste de transação: falha antes do commit mantém segmento CLOSED e reprocessável sem memória parcial.
- Teste exactly-once: crash/retry do mesmo `segment_id` não duplica memória, provenance nem `frequency`.
- Teste de regressão do Reaction Loop e do `ContextoAfetivo` sem alteração comportamental.
- Teste de migração v1 -> v2 preservando todas as memórias existentes.
- Suite M1 existente deve permanecer GREEN.

## Fora de escopo

Vector database, embeddings obrigatórios, sumarização LLM autônoma, aprendizado online de reliability, cache KV/prompt, roteamento multiagente e coherence checker completo. Esses itens serão slices posteriores sobre a provenance criada aqui.

## DoD M2

M2 está concluído somente quando o pipeline episódico está integrado, bounded e persistente; provenance e generation fencing são verificáveis; migração v1 -> v2 é segura; todos os testes M1 + M2 estão GREEN; e o comportamento emocional existente permanece sem regressão observável.
