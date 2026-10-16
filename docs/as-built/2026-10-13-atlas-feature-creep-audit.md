# Atlas CP-AUD03 — Inventário estático verificável de feature creep
Data: 2026-10-13. Escopo: apenas os módulos Python de topo e configs locais no repositório x99; **não prova ausência de uso em produção**.

## Implementação
- `tools/atlas_feature_inventory.py`: analisa código via AST sem importar/executar módulos; rastreia imports diretos, algumas referências dinâmicas literais e entrypoints em arquivos `.service` e `.sh`; percorre somente flags booleanas em `config*.json`. Não lê conteúdo de `.env`, segredos, bancos, arquivos pessoais; não faz rede e não remove artefatos.
- `tools/test_atlas_feature_inventory.py`: **5 testes PASS**, garantindo diferenciação de entrypoint/importado/candidato, inexistência de import com side effects, flags aninhadas, fonte inválida e sintaxe quebrada.
- Manifesto completo com **177 módulos e classificação individual**: `.atlas/opencode/tmp/cp-aud03-feature-inventory.json`.

## Distribuição observada
| Classificação estática | Total | Interpretação |
|---|---:|---|
| REFERENCED | 137 | Um import direto foi observado; não garante execução efetiva |
| ENTRYPOINT_REFERENCED | 7 | Aparece em unit/service/script; **proibido classificar como morto apenas por import** |
| REVIEW_DYNAMIC_OR_LEGACY | 33 | Nenhum import/entrypoint capturado por esta análise limitada; precisa confirmar chamadas dinâmicas, scripts externos, CLI e runtime |

**Sete entrypoints protegidos:** `cli.py`, `cognitive_daemon.py`, `discord_gateway.py`, `health_supervisor_daemon.py`, `hermes_preflight.py`, `observation_daemon.py`, `voice_daemon.py`.

**Candidatos para investigação por domínio** (não são recursos comprovadamente mortos):
- **Memória/conversação:** `memory_preference_tracker.py`, `memory_project_adapter.py`, `prompt_cognitivo.py`, `context_pack.py`, `chat_cli.py`, `registro_semantico.py`, `adaptadores_semanticos.py`.
- **Agentes/autoexecução:** `agency_worker_cli.py`, `c5_physical_orchestrator.py`, `enqueue_and_watch.py`, `slow_llm_defer_queue.py`, `fast_router.py`, `fast_dispatch.py`, `recovery_controller.py`.
- **Internet:** `web_research_policy.py` — deliberadamente inativo, em desenvolvimento; **integrar**, não remover.
- **Voz:** `energy_vad.py` — verificar cadeia ALSA/VAD e ausência de microfone.
- **Certificação/CLI/diagnóstico:** `affective_boot_certification.py`, `cognitive_context_bridge_certification.py`, `debug_exact_message.py`, `hermes_physical_smoke.py`, `i1_certification.py`, `network_discovery_smoke.py`, `workspace_certification.py`, `unix_http.py`, `config_llama_server.py`; ferramentas potencialmente invocadas diretamente.
- **Testes/scripts (não remover por critério de produção):** `test_discord_real_context.py`, `test_dual_persona.py`, `test_e2e_usabilities.py`, `test_example_l2j.py`, `test_hermes_tool_use.py`, `test_jarvis_universal.py`, `test_raw_discord_format.py`, `__init__.py`.

**Flags booleanas falsas:** `config_agency_specialists.json:enabled`, `config_health_supervisor.json:features.self_healing_v1`, `config_health_supervisor.json:managed_hosts.x99.required` e `config_voice.json:anc_enabled`. As duas primeiras são bloqueios de segurança por design e **não devem ser ativadas automaticamente**. `required=false` é configuração de host, não feature flag a ativar. A ausência de microfone não deve impedir conversação textual.

## Limitações
A análise não cobre imports de subpacotes, runtime via `importlib` com nomes dinâmicos, cron externos, scripts de outro projeto, logs de uso, perfis/plugins Hermes nem chamadas do Core. A classificação `REVIEW_DYNAMIC_OR_LEGACY` é um **pedido de investigação**, não prova de inatividade. Aplicar `KEEP / INTEGRATE / REFACTOR / REMOVE_CANDIDATE` após evidência de consumidor/uso físico e rollback. Não houve remoção nem deploy.
