# Atlas 4.0 — Plano de integração Agency Agents / Hermes
Data: 2026-10-12
Estado: PLANEJADO — SEM INSTALAÇÃO, SEM DEPLOY
Repositório local: C:\Users\deral\DevEx-HomeLab
Branch-base: manter a branch atual, sem criar branch nem worktree.

## 1. Objetivo
Aproveitar os especialistas de https://github.com/msitarzewski/agency-agents por meio do plugin oficial `agency-agents-router` do Hermes, com seleção sob demanda, delegação controlada e evidências verificáveis. **Não** substituir o Atlas, seu HermesAdapter, memória, mecanismos de tarefas ou políticas de ação.

## 2. Estado conhecido e limitações
- Atlas possui HermesAdapter, contrato cognitivo JSON v1 estrito, `PlanoAcaoAtlas`, `ActionPolicy`, capability registry, memória episódica/MemoryGraph, motor de tarefas/autonomia, dashboard e serviços de observação/cognição.
- Auditoria local de 2026-10-10: 1018 passed, 3 skipped, 42 subtests; isto **não** certifica o runtime físico atual.
- `self_healing_v1: false`, inventário de CONTROL vazio e certificação CP-H12 pendente na última auditoria. Preservar estes controles.
- O SSH automatizado x99 -> pentium não fornece sessão autenticada utilizável neste momento; não inferir estado atual de systemd, processos ou plugins do Pentium.
- Governança `.agents/rules/governance.md`: Pentium é control plane leve; processamento pesado/LLM/compilação deve ficar em container no `core`; novas features não são promovidas enquanto P0 Backup/DR (Issue #11) estiver pendente. Confirmar estado atual da issue antes de qualquer implantação.
- A versão instalada de Hermes, presença real do plugin, provedor ativo e release em produção ainda precisam ser verificados.

## 3. Decisões arquiteturais (ADRs propostos)
**ADR-AA01 — Reuso em vez de nova plataforma multiagente.** O Hermes é o runtime, `agency-agents-router` é o catálogo/delegador, e o Atlas continua coordenador. Não criar segundo orchestrator, planner, task store, memory graph ou scheduler.

**ADR-AA02 — Separação entre córtex e delegação.** Preservar o perfil cognitivo `atlas` sem ferramentas arbitrárias e a saída JSON v1 de 8 campos. Propor um perfil/worker isolado `atlas-specialists` no `core` para ferramentas Hermes do catálogo; nunca abrir ferramentas indiscriminadamente no `atlas-cognitive.service`.

**ADR-AA03 — Pentium permanece leve.** Pentium recebe apenas status, solicitações tipadas, correlação e auditoria bounded; worker/LLM/subagentes são executados em container no `core`. Não instalar cargas de execução intensiva no Pentium.

**ADR-AA04 — Default deny.** Texto retornado pelos especialistas é dado não confiável, não autorização. Ações reais passam por `ActionPolicy`, allowlists específicas, autenticação, revisão/confirmacão humana conforme risco e auditoria antes/depois da execução. Nenhum shell ou SSH genérico é exposto aos especialistas.

**ADR-AA05 — Lazy routing.** Usar `agency_agents_search`, `inspect`, `load`, `delegate` sob demanda. Não adicionar todo o catálogo a `skills.external_dirs`, nem preload de centenas de agentes; fixar revisão upstream e revisar código do plugin.

**ADR-AA06 — Memória canônica.** Persistir apenas resumo da tarefa, justificativa de seleção, evidências, resultado e referências, pelos componentes existentes `MemoryStore`/`MemoryGraph`. Não criar memória paralela, não persistir segredos ou prompts brutos.

## 4. Fluxo proposto
```text
Usuário / Dashboard / Discord
        |
     Atlas (intenção + contexto + PlanoAcaoAtlas v1)
        |
TaskStore / ContinuousIntent / CapabilityRegistry / ActionPolicy
        |
SpecialistTaskPort (adaptador mínimo; fila bounded + job_id)
        |
worker isolado no core / Hermes perfil atlas-specialists
        |
agency-agents-router (search -> inspect -> load/delegate)
        |
resultado estruturado + evidências (SEM executar ações privilegiadas)
        |
validação por schema e policy -> plano/ação aprovada -> audit log
        |
MemoryStore + MemoryGraph existentes / resposta no Dashboard
```

## 5. Contratos mínimos (proposta; não criar novo domínio)
Request: `task_id`, `project_id`, `objective`, `scope`, `origin`, `requested_capability`, `risk_class`, `repo_commit`, `evidence_refs`, `max_budget`, `deadline`.
Result: `task_id`, `agent_slugs`, `summary`, `proposed_changes`, `evidence_refs`, `tests_run`, `limitations`, `approval_required`, `status`.
- Contratos bounded, versionados e validados; sem aceitar capabilities sugeridas por texto do LLM.
- Classes: READ diagnóstico sem efeitos; CONTROL somente por executor allowlisted após gate; DESTRUCTIVE exige confirmação explícita independente.
- Sem mutação de código/config/deploy por resultado de agente sem autorização e rollback.
- Falha, timeout, cancelamento, resposta inválida e economia de tokens degradam para Atlas normal, não desativam observação/alertas.
- Limitar inicialmente a 1 delegação em andamento, 2 especialistas por tarefa, fila bounded, timeout e orçamento de tokens configuráveis; valores finais devem vir de benchmark e política.

## 6. Checkpoints de implementação (não executar sem gates)
### CP-AA0 — Gate de conformidade e baseline (bloqueante)
- Consultar situação REAL da P0 Backup/DR Issue #11 e CP-H12; nenhum rollout enquanto bloqueados.
- Inventariar branch atual, arquivos alterados, testes e revisão implantada sem mexer em worktrees.
- Coletar snapshot validado do runtime, backup/restore de config Hermes + Atlas + dados persistentes e evidência de restauração; nunca armazenar segredos no relatório.
- Definir owner da task, componente consumidor, dependências, flags e rollback.
**Aceite:** backup/DR certificado; baseline de regressão documentado; runtime e rollback verificáveis.

### CP-AA1 — Compatibilidade e segurança do plugin (somente staging)
- Fixar commit/release de Agency Agents e verificar licença, dependências e `scripts/build-hermes-plugin.py`.
- Gerar plugin em staging por `scripts/convert.sh --tool hermes`; conferir 4 schemas, o catálogo e dependências.
- Validar a configuração efetiva `plugins.enabled` / `plugins.disabled`: há relatos de installer inserindo plugin no bloco errado; não confiar só na saída do instalador.
- Confirmar versão Hermes, perfil efetivo, toolsets, subagents e fallback do modelo sem impor provider obrigatório.
**Aceite:** sem segredos em logs; ferramentas carregáveis em ambiente descartável; plugin está realmente habilitado e com argumentos corretos.

### CP-AA2 — Ponte Atlas -> specialist worker
- Integrar à infraestrutura já existente de intents/tasks/executors, sem outro scheduler.
- Adaptador mínimo `SpecialistTaskPort` para job id, fila bounded, status, cancelamento, timeout, retry somente de READ idempotente.
- Preservar íntegra a resposta cognitiva v1 de 8 campos; nenhum agente delegado escreve diretamente no estado afetivo, observacional ou de sistema.
- Feature flag proposta `agency_specialists_v1: false` por padrão.
**Aceite:** teste RED/GREEN dos contratos, schema, erro e fallback; serviço Atlas continua correto com feature off.

### CP-AA3 — Política de autorização e isolamento
- Permissões por projeto + agente + capacidade + host + operação; diretórios de trabalho restritos; sem acesso a chaves, tokens, browser autenticado ou filesystem fora do escopo.
- Política nega executor externo, push, deploy, serviço/reboot e alteração do live sem gate humano.
- Testar prompt injection via descrição de agente e saída de ferramenta; provas de negação registradas.
**Aceite:** nenhum texto de especialista consegue contornar capability policy.

### CP-AA4 — Catálogo e seleção sob demanda
- Criar mapeamento declarativo de necessidades -> busca por especialidade, com justificativa e histórico de resultados.
- Primeira shortlist: Game Designer, AI Engineer, Performance Benchmarker, Test Automation Engineer, Code Reviewer, Multi-Agent Systems Architect, SRE, DevOps Automator.
- Selecionar no máximo 2 por job inicialmente; não carregar catálogo inteiro.
**Aceite:** seleção auditável, bounded, sem duplicar especialistas ou ciclos de delegação.

### CP-AA5 — Memória e observabilidade
- Publicar status `queued/running/waiting_approval/succeeded/failed/cancelled` no contrato existente de eventos/snapshots.
- Reutilizar MemoryStore/MemoryGraph para resumo/evidência, com deduplicação, TTL e confidencialidade.
- Medir duração, token/custo quando disponível, erros, contexto e uso de CPU/RAM; o Pentium não executa jobs pesados.
**Aceite:** uma única fonte de verdade; memória protegida; sem interferir no FastRouter e observação.

### CP-AA6 — Certificação E2E em três cenários
1. Atlas/DevEx: diagnóstico READ-only do estado de serviços sem CONTROL nem self-healing.
2. Rei da Laje: análise de IA e colisões no código/simulações de teste, sem alteração da live.
3. Lanchonete do Guru: revisão de arquitetura sem acesso a pagamentos reais/produção.
- Para cada cenário: teste RED, implementação mínima, GREEN, regressão completa, auditoria e evidências objetivas.
**Aceite:** propostas precisas e rastreáveis; nenhuma alteração não autorizada; sem regressão.

### CP-AA7 — Rollout progressivo
- Só após todos os gates: habilitar para tarefas manuais READ no worker do core; observar métricas antes de considerar CONTROL específico.
- Revalidar backup, certificado de rollback, logs e configuração de permissões.
- Não habilitar self-healing, Voice nem controle multi-host por efeito colateral.
**Aceite:** demonstração funcional com usuário iniciando delegação, stop/rollback testado e baseline preservado.

## 7. Estratégia de testes
- Unitários: catálogo, seleção, contratos, timeout, orçamento, parser/schema, políticas deny-by-default.
- Integração: Hermes mock e plugin real em staging, sem interferência na sessão cognitiva Atlas.
- Segurança: texto malicioso em agente, output injection, path traversal, acesso a secrets, autorização perdida no retry, alvos MANAGED não permitidos.
- Resiliência: subagent indisponível, provider indisponível, fila cheia, timeout, reinício do worker, shutdown limpo, resposta parcialmente escrita.
- Regressão: repetir suíte canônica `py -m pytest --import-mode=importlib infrastructure/pentium/atlas/tests infrastructure/pentium/agent/tests -q` e comparar ao baseline conhecido (2026-10-10, não atual).
- Performance: benchmark de RAM/CPU do Pentium e core, overhead do roteador, chamadas remotas e teto de tokens; interromper rollout se degradar funções críticas.

## 8. Rollback e promoção
- Feature flag OFF e perfil `atlas` intacto devem bastar para deixar o Atlas funcional independentemente do plugin.
- Desabilitar plugin no worker, cancelar jobs, reverter artefato/container pinado, recuperar configuração versionada e verificar health/read-only.
- Backups da memória e do estado afetivo não devem ser sobrescritos; nunca rodar migrador de memória sem plano de restauração testado.
- Promoção somente após evidências GREEN locais + físicas; nenhum push ou deploy automático como efeito do planejamento.

## 9. Fora de escopo
- Substituir Hermes, políticas de Atlas, JSON v1, FastRouter, dashboard, Discord, memória, grafo ou task engine.
- Usar modelos locais pesados, Whisper, TTS, compilação ou render no pentium; reativar Voice.
- Dar credenciais de produção aos agentes, executar shell genérico, controlar hosts por wildcard ou reiniciar serviços sem autorização.
- Instalar todos os agentes como skills ou criar branch/worktree adicional.

## 10. Fontes
- https://github.com/msitarzewski/agency-agents
- https://github.com/msitarzewski/agency-agents/blob/main/integrations/hermes/README.md
- https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/plugins.md
- Governança local `.agents/rules/governance.md`
- Auditorias `docs/as-built/2026-10-10-atlas-*.md`

**Decisão:** iniciar por CP-AA0, nunca pela instalação direta no Pentium. A liberação posterior depende de Backup/DR P0, da certificação física e da segurança do worker.
