# Atlas 4.0 — auditoria incremental de feature creep (2026-10-10)

## Escopo e evidências
- Repositório x99: `C:\Users\deral\DevEx-HomeLab`
- Branch observada: `atlas/v0.4.0-proprioception-autonomy`, 14 commits locais à frente do remoto; HEAD `2a62765`.
- Fonte de requisitos: `docs/superpowers/specs/2026-10-09-atlas-health-self-healing-memory-coherence-autonomy-design.md`.
- Plano: `docs/superpowers/plans/2026-10-09-atlas-health-self-healing-phase1.md`.
- A auditoria é NÃO DESTRUTIVA. Presença de arquivo ou teste não equivale a serviço operacional no Pentium.

## Matriz inicial de capacidades e classificação
| Capacidade | Evidência no código | Estado verificável | Próxima ação |
|---|---|---|---|
| Health Supervisor | `health_supervisor.py`, `health_supervisor_daemon.py`, testes | YELLOW: testes locais focados passaram; deploy não validado | Verificar rollout, snapshot e prova funcional no Pentium |
| Recovery Controller | `recovery_controller.py`, testes | YELLOW: testes locais focados passaram; recuperação física não verificada | Certificar precondições/limites e smoke reversível seguro |
| Memory Graph | `memory_graph.py`, testes | YELLOW: camada presente; Graph v2 e coerência propostos | Evitar grafo paralelo, definir interface e benchmark antes de ampliar |
| Capability Registry | `capability_registry.py`, testes | YELLOW: testes locais focados passaram; alvos remotos não certificados | Validar allowlists por host e negação de wildcards |
| Hermes | `hermes_adapter.py`, configuração e testes | YELLOW: presente, runtime não verificado nesta auditoria | Prova ponta a ponta com executor e política |
| Memória textual/episódica | `memory_store.py`, `episodic_consolidator.py` | YELLOW: presente, integridade operacional não aferida | Confirmar lifecycle/supersession e compatibilidade |
| Autonomia e tarefas | `autonomy_executor.py`, `continuous_intent.py`, `task_store.py` | YELLOW: presente, testes E2E pendentes | Não criar segunda task engine |
| Discord / Dashboard | `discord_gateway.py`, `atlas_dashboard.py` | YELLOW: integração existe; estado vivo não auditado | Consumir snapshot canônico com fallback |
| Operação multi-host | `multi_host_executor.py`, inventário gerenciado | YELLOW: código presente; inventário físico não validado | Verificar alvos reais antes de controle automático |

Legenda: GREEN exige integração e certificação; YELLOW exige validação; RED exige falha comprovada; PLANNED exige ausência confirmada da implementação.

## Observações de feature creep
1. A especificação **já exige composição**, não substituição: `health_engine` + supervisor agregador; `MemoryStore` + `MemoryGraph`; `ContinuousIntent` + `SelfWorkStore`; política única de capabilities. Isto define os limites arquiteturais para prevenir duplicação.
2. Os arquivos `health_engine.py`, `local_health.py`, `health_supervisor.py` podem parecer redundantes, mas o desenho formal atribui responsabilidades diferentes. **Não remover nem fundir sem rastrear consumidores e provar equivalência**.
3. Memória em grafo v2, admission/coherence e goals persistentes constam na especificação como evolução posterior; **não marcar como implementados somente por haver componentes anteriores**.
4. O plano Phase 1 inclui CP-H/CP-S e termina em Task 11 (inventário aprovado) e Task 12 (certificação física). Verificar estas tarefas antes de expandir escopo.
5. O comando de teste combinado sugerido no plano falhou na **coleta** por dois módulos chamados `test_cli.py` (um em atlas/tests e outro em agent/tests); trata-se de conflito de importação do pytest, não falha funcional demonstrada. Usar `--import-mode=importlib` ou testes separados, sem apagar caches arbitrariamente.

## Verificações executadas
- `py -m pytest infrastructure/pentium/atlas/tests/test_health_supervisor.py infrastructure/pentium/atlas/tests/test_recovery_controller.py infrastructure/pentium/atlas/tests/test_memory_graph.py infrastructure/pentium/atlas/tests/test_capability_registry.py -q` → **21 passed**.
- `py -m pytest infrastructure/pentium/atlas/tests infrastructure/pentium/agent/tests -q` → bloqueado na coleta: `import file mismatch` de `test_cli.py`.
- Retentativa com `--import-mode=importlib`: resultado final deve ser anexado após conclusão.

## Gate de mudança de escopo
Nova feature só avança com: consumidor identificado, owner do estado único, contratos testáveis, prova RED/GREEN, autorização de risco, flags/fallback, benchmark quando relevante e aceite físico quando envolver serviços.

## Próxima ação prioritária
1. Encerrar suíte completa sem conflito de coleta e registrar regressões.
2. Investigar Task 11 do plano (inventário de alvos), **somente observação** antes de qualquer controle.
3. Task 12: certificar implantação/estado do Pentium, gates de risco, falhas e evidências.
4. Só depois avaliar próximos planos de Operational Event Log, Memory Lifecycle, Knowledge Graph v2 e Memory Decision Layer.

Sem remoção de funcionalidades, sem novo agente, sem worktrees nem alteração de branch.

## Resultado consolidado da regressão local
- `py -m pytest --import-mode=importlib infrastructure/pentium/atlas/tests infrastructure/pentium/agent/tests -q` → **1018 passed, 3 skipped, 42 subtests passed**, exit code 0, duração de execução informada pelo pytest 26.49s.
- `git diff --check` → sem erros detectados.
- `git status --short --branch` → branch original preservada, 14 commits ahead; apenas este relatório Markdown aparece como arquivo não rastreado.
- Nenhum código de produção, serviço, configuração operacional, memória ou inventário foi modificado nesta auditoria.
- A certificação física e a medição de duplicação de responsabilidades entre funções/consumidores ainda estão pendentes; não tratar o relatório como auditoria integral concluída.
