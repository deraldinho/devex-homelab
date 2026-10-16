# Atlas CP-AUD02 — Drift de código entre repo, runtime e cópia do Pentium
**Data:** 2026-10-13 · **Estado:** diagnóstico read-only executado. **Não autoriza deploy/cópia em massa.**

## Fontes comparadas
Foram calculados hashes SHA-256 **apenas** de arquivos Python no primeiro nível da árvore (não houve transferência de conteúdo de bancos, arquivos .env, chaves nem credenciais).
- Fonte de desenvolvimento: `C:\Users\deral\DevEx-HomeLab\infrastructure\pentium\atlas` — **176** módulos de topo.
- Runtime da unidade cognitiva: `/home/deraldinho/pentium-agent/atlas` — **168** módulos de topo.
- Cópia antiga: `/home/deraldinho/atlas` — **164** módulos de topo.

O manifesto por hash SHA-256 reside em `.atlas/opencode/tmp/atlas-pentium-source-hashes.json`. Resumo determinístico em `.atlas/opencode/tmp/atlas-pentium-drift-summary.json`; script somente leitura em `.atlas/opencode/tmp/atlas_compare_source_hashes.py`.

## Resultados exatos
| Comparação com repo x99 | Runtime Pentium | Cópia ~/atlas |
|---|---:|---:|
| Hashes de módulos Python iguais | 157 | 157 |
| Mesmos nomes com conteúdo divergente | **7** | **7** |
| Existem no repo mas não no host | **12** | **12** |
| Existem no host mas não no repo | **4** | **0** |

**Sete divergentes em ambos os diretórios:** `capability_registry.py`, `cognitive_daemon.py`, `discord_gateway.py`, `hermes_adapter.py`, `policy_capabilities.py`, `reaction_loop_cognitivo.py` e `task_capability_executor.py`. Estes são arquivos **críticos no percurso da conversação e da política de ações**. Parte da divergência é esperada por alterações locais ainda não implantadas; não confundir hash diferente com bug real.

**Doze presentes no repo mas não nas duas cópias:** `agency_specialist_selector.py`, `agency_specialists.py`, `agency_worker_cli.py`, `decision_preconditions.py`, `health_probes.py`, `health_supervisor.py`, `health_supervisor_daemon.py`, `health_supervisor_model.py`, `host_adapters.py`, `multi_host_executor.py`, `recovery_controller.py` e `recovery_model.py`. Nem todos são releases aprovados; manter gates CP-H12/AA7 até homologação.

**Quatro exclusivos no runtime Pentium, ausentes no repo:** `configuracao_llm.py`, `llama_cpp_backend.py`, `llama_cpp_resident_backend.py` e `llama_server_runtime.py`. São candidatos a **legado não integrado**, mas não devem ser removidos sem prova de consumidores dinâmicos (entrypoints CLI, plugins e referências em config).

## Impacto para o Atlas 5.0
- A memória `memory_retriever.py` e a composição `affective_runtime.py` têm SHA igual no repo e runtime, **mas seu chamador `reaction_loop_cognitivo.py` e o adaptador Hermes diferem**. Isso impede afirmar que o recall e a inteligência emocional do código novo já alcançam a live.
- A ordem de atualização deve ser `CP-DR15 backup confirmado → CP-AUD02 revisão compatibilidade/entrada → CP-CONV E2E → CP-MEM/EMO → CP-DEPLOY canary`, com os controles e callbacks do processo real validados e rollback pronto.
- Um deploy que simplesmente substitua `~/pentium-agent/atlas` pelo diretório repo apagaria quatro módulos host-only e poderia quebrar o runtime. **Esse tipo de deploy está explicitamente vetado.**
- As listas são apenas de módulos Python de topo, não cobrem subpacotes, configurações, unit files, dados ou assets; expandir inventário antes de remover recursos.

## Critérios para refatorar/remover
1. Inventariar importadores diretos, carregadores dinâmicos, comandos, config e services; marcar `KEEP / INTEGRATE / REFACTOR / REMOVE_CANDIDATE`.
2. Para cada `REMOVE_CANDIDATE`, criar teste que comprove ausência de consumidores em produção e cobertura de fallback, e permitir rollback.
3. Não alterar nem reiniciar serviços do Atlas sem revisão dos sete módulos divergentes e smoke seguro da versão preparada.


## Triagem complementar de componentes host-only (AST, runtime real)
Foi realizada uma varredura **somente leitura**, por AST, de imports diretos dos módulos Python de topo no runtime `~/pentium-agent/atlas`. Os quatro módulos exclusivos do Pentium, `configuracao_llm.py`, `llama_cpp_backend.py`, `llama_cpp_resident_backend.py` e `llama_server_runtime.py`, apresentaram **zero consumidores por import estático nessa amostra**. Esse resultado **não prova ausência de uso**: o ambiente pode invocá-los como entrypoints, por `importlib`, outros subpacotes, shell, cron ou configuração. Status de todos: `REMOVE_CANDIDATE / DEPENDENCY_AUDIT_REQUIRED`, **não apagar**.
