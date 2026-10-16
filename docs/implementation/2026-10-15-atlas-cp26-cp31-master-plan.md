# Atlas — plano mestre de execução CP26–CP31 (2026-10-15)

## Baseline e regras invariantes
- Source of truth: `C:\Users\deral\DevEx-HomeLab` (branch `atlas/v0.4.0-proprioception-autonomy`, HEAD inicial `7e84c92`). O checkout possui 113 caminhos pendentes **preexistentes**. Não limpar, sobrescrever, rebasear, criar worktree, commitar ou fazer push em lote.
- Staging anterior: `C:\Users\deral\Documents\Atlas-DevOps\CP-ATLAS-RECON-20261015`, repositório SEPARADO e bloqueado para produção. Seus módulos só podem ser promovidos mediante revisão, cherry-pick/manual port e regressões independentes.
- x99 = código, OpenCode, direção técnica; core = workloads descartáveis e especialistas; pentium = runtime permanente e dados persistentes. Não executar builds/LLM de especialistas no pentium.
- Hermes é engine de inferência, não proprietário de identidade nem das permissões. Atlas é proprietário de planejamento, memória, ações e comunicação.
- Perfis/tooling/capabilities permanecem default-deny; nunca habilitar `config_agency_specialists.enabled` ou `self_healing_v1` antes dos respectivos gates.
- Preferir modelos gratuitos; fallback verificável e com orçamento/quota; sem loops infinitos. Atribuir no máximo duas tarefas simultâneas por área de escrita, sempre ownership exclusivo.
- Testes reais e logs sanitizados; preservar segredos, consentimento para mensagens externas e capacidade de rollback. Nenhum claim de sucesso sem exit code, artifact diff e evidência E2E.

## Orquestração por equipes
- A0 CTO Orchestrator (Atlas): ordem de execução, baseline Git e política, registry de sessões, arbitragem de conflitos, integração final.
- A1 Runtime E2E (CP26): `infrastructure/pentium/atlas` gateway/cognitive/Hermes/dashboard; reproduzir falhas, TDD e E2E local + host; não alterar configs produtivas antes de rollback.
- A2 Release/DR (CP27): `infrastructure/backup`, `tools/atlas_*deploy*`, manifestos; SHA drift, aprovação, restore isolado/offsite, rollback sem sobrescrever dados persistentes.
- A3 Multiagent (CP28): `infrastructure/core/agency-agents`, bridges/transporte/worker, model fallback; core isolado, READ-only, signed receipts, idempotency.
- A4 Autonomy (CP29): `infrastructure/pentium/atlas` supervisor/policies; incidents, triagem, decision approval, apply/verify/compensate; conflitos com A1 sob integração serial.
- A5 MemoryGraph (CP30): memory modules, graph contexts, schema versioning, privacy, replay, migração backward-compatible; conflitos com A1 sob integração serial.
- A6 Interfaces (CP31): `dashboard`, consulta web READ/SSRF, voz opcional condicionado a dispositivo, correlação logs/traces.
- A7 Security+QA: leitura independente, testes negativos, race/crash, revisão da autoridade; não autorizar releases apenas com relatórios dos implementadores.

## Quality gates ordenados
### CP26 — homologação Pentium [P0]
1. Capturar estado dos serviços, unit files/timers, versões/release e logs sanitizados.
2. Reproduzir fluxo Discord -> inbox -> CognitiveDaemon -> Hermes -> outbox -> ACK Discord; nunca classificar `service active` como conversa certificada.
3. Testar endpoint HTTP `/health` do dashboard; preferir `GET` sem efeitos.
4. Confirmar memória persistente entre duas inicializações isoladas; registrar SLA observável e falhas.
5. Corrigir bugs em staging com TDD. Comprovar em produção apenas após CP27 deployment gate aprovado.
Gate: entradas/respostas reais, IDs correlacionáveis, zero exceções críticas novas, timers saudáveis.

### CP27 — release e disaster recovery [P0]
1. Inventariar os 113 caminhos por propriedade/procedência, separar track/untracked e hashes de Pentium.
2. Integrar somente mudanças pertencentes ao Atlas; manifestos rastreáveis; `git diff --check` e CI; revisão de segredos.
3. Backup restic com restore isolado dos SQLite ativos via snapshots transacionais; `PRAGMA integrity_check`, sem restore sobre produção.
4. Teste rollback sintético e de release sem perda de estado persistente; demonstrar cópia offsite e restauração, caso destino autorizado esteja configurado.
Gate: release reproduzível, QA independente, rollback reversível; caso offsite ausente manter status BLOCKED.

### CP28 — execução multiagente [P1]
1. Transporte tipado Atlas/Core/worker de mínimo privilégio, com assinatura/autenticação, allowlist READ, deadline, limites, idempotency key e ACK durable.
2. Adapter Hermes e OpenCode v2 com sessão (ID, role, diretório, modelo, custo), reconciler de estados, fallback econômico com retry bounded.
3. Core container não privilegiado, sem mounts/chaves de produção, QA malicioso e tempestade de falhas.
4. Integrar evidência ao Atlas e grafo, mantendo contrato de política existente.
Gate: agente executou tarefa READ real e provas independentes validaram resultado; toggle só após rollout autorizado.

### CP29 — autonomia segura [P1]
1. Detect -> classify -> decide -> authorize -> execute -> verify -> rollback -> notify; filas duráveis, DLQ e circuit breakers.
2. Exercitar incidentes descartáveis (processo de teste indisponível, timeout, falha de worker), limites de retries, ausência de escalada.
3. Comunicação natural via LLM é apresentação; nunca autoriza execução.
Gate: incidente controlado resolvido, supervisão e audit log completos, default-deny de operações CONTROL/WRITE.

### CP30 — contexto e MemoryGraph v2 [P1]
1. ADR de schema versionado (nó, evento, relacionamento, proveniência, política de retenção, invalidação).
2. Contratos TDD, migração reexecutável com backup, dual-read/rollback, reconciliação do grafo.
3. Recuperar objetivos, preferências e decisões em sessão posterior, com testes contra vazamento cruzado.
Gate: recuperação contextual precisa e lineage/correlation IDs.

### CP31 — capacidades/interfaces [P2]
1. Pesquisa web via ferramenta READ isolada (URLs/SSRF/DNS/TLS/allowlist e citações), não habilitar tools no profile cognitivo.
2. Dashboard operacional HTTP, agentes, tracing, latência/custos e alarmes; segurança de acesso.
3. Voz somente após hardware apto e testes de VAD/ALSA; caso contrário registrar bloqueio explícito.
Gate: testes reais, proteção de dados, desempenho e gates de acessibilidade.

## Evidência inicial desta execução
- x99 e SSH x99 -> pentium/core acessíveis; `opencode v2.0.28`; servidor de fundo OpenCode ativo.
- Em Pentium: `atlas-cognitive`, `atlas-discord`, `atlas-dashboard`, `atlas-observation` ativos pelo systemd.
- `GET http://127.0.0.1:8765/health` respondeu HTTP 200; `GET /api/health` respondeu 404 (não é rota comprovada).
- **Bug P0 reproduzido:** `python3 -m atlas.hermes_preflight` no Pentium retornou `ATLAS_HERMES_PREFLIGHT_FAIL:profile_unavailable` (a confirmar raiz).
- Existem processos/sessões antigos OpenCode ainda sem recibo final confirmado; NÃO duplicar seus trabalhos antes da reconciliação.
- Os relatórios CP22/CP23 do staging anterior declaram `PRODUCTION_BLOCKED` por execução BUILD incompleta.
- Último deploy referido: `~/.local/state/atlas-deploy/releases/20261015-1945-retry2/`; não promover sem manifesto/verificação.
## Registro de conclusão
Cada checkpoint deve adicionar: hash base/novo, arquivos efetivamente alterados, testes rodados (com exit), artefatos, sessões OpenCode efetivas, validação física e riscos residuais. Marcar como `BLOCKED` se qualquer gate falhar.