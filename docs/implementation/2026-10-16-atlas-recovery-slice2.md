# Atlas — Slice 2: recibos operacionais de falha (16/10/2026)

Checkpoint RECOVERY-S2-LOCAL. Estado: implementado/testado em desenvolvimento; publicação BLOQUEADA. Raiz oficial: C:\Users\deral\DevEx-HomeLab; branch atlas/v0.4.0-proprioception-autonomy. Árvore já estava modificada; não houve reset, worktree, commit, push, deploy, migration em produção ou restart.

## Implementação

- AgencyGateway._record (infrastructure/pentium/atlas/agency_specialists.py): falhas de worker persistem metadata de evento em MemoryStore injetado, sem incluir objetivo, prompt, exception ou resposta livre.
- Recibos possuem event_id, task_id, project, reason_code, attempt, created_at em UTC, schema_version 1. Reasons permitidos são constantes definidas pelo código; strings arbitrárias são rejeitadas.
- MemoryStore (infrastructure/pentium/atlas/memory_store.py): tabela operacional agency_failure_receipts separada de memories/episodic. Índice task_id+created_at; transação SQLite; replay idêntico retorna False e replay divergente rejeitado.
- Retenção manual: prune_agency_failure_receipts(before_utc, max_delete), limite 1..1000 por operação; não existe autoexpurgo nem acesso da LLM a estes recibos.
- Falha do SQLite mantém o resultado original de SelfWork e gera telemetria failure_receipts_store_errors. O evento operacional opcional não inclui detalhes sensíveis.

## TDD / Quality Gates

- Baseline Slice 1 reexecutado: test_self_work_recovery 8/8 PASS; test_self_work 7/7 PASS.
- RED reproduzido: 4/4 testes novos falhavam por métodos/counters ausentes antes da implementação.
- GREEN final: 5 novos testes cobrindo durabilidade/restart, dedupe/replay, segredo em reason, degradação do storage e retenção limitada.
- Gate combinado: 90/90 testes PASS, 0 falhas (MemoryStore, Agency, SelfWork, episodic, ledger, coherence).
- Python compileall nos arquivos envolvidos: exit 0; git diff --check: exit 0.
- Auditoria independente OpenCode somente leitura em modelo free iniciada (PID 32980), ainda sem relatório de conclusão verificado.

## Arquivos tocados neste checkpoint

- infrastructure/pentium/atlas/memory_store.py
- infrastructure/pentium/atlas/agency_specialists.py
- infrastructure/pentium/atlas/tests/test_agency_failure_receipts.py (novo)
- docs/implementation/2026-10-16-atlas-recovery-slice2.md (novo)

## Bloqueios para produção e próximos gates

- AgencyGateway aceita MemoryStore opcional. Não foi identificada composição ativa do adapter no diretório raiz da aplicação: é preciso provar injeção e E2E em QA antes de deploy.
- Na indisponibilidade total do SQLite, a perda do recibo é observável mas NÃO existe fallback durável. Zero-loss não está certificado; projetar spool/outbox seguro e reconciliação.
- Não foram testados lock/concorrência multi-processo nem restart forçado durante commit em runtime real.
- Retenção exige parametrização e agendamento específicos, sem destruir evidências antes do prazo.
- Não iniciar trigger_recovery ou circuit breaker de produção sem aprovação e gates independentes das Slices 3/4/5.
