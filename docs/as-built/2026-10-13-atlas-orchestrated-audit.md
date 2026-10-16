# Atlas — Auditoria orquestrada e plano de recuperação de funcionalidades
Data: 2026-10-13. Repositório original: DevEx-HomeLab; branch existente atlas/v0.4.0-proprioception-autonomy.
Escopo: Atlas 5.0 (nome de roadmap, não release nem instalação já concluída).

## Estado verificado no Pentium
- Sistema Atlas realmente invocado pela unidade: `/home/deraldinho/pentium-agent` executando `python3 -m atlas.cognitive_daemon`; processo ativo. **A pasta `/home/deraldinho/atlas` também existe, mas não é o WorkingDirectory da unidade cognitiva.** Não tratar essa cópia isolada como o runtime em produção.
- atlas-cognitive, atlas-discord, atlas-observation e atlas-dashboard: active; atlas-voice: inactive (ausência de microfone declarada pelo operador).
- `~/.hermes` existe com estado e configuração; a seleção de modelos é responsabilidade do Hermes, não do Atlas.
- `opencode` não foi encontrado no PATH não interativo do Pentium. Bridge OpenCode existe no repo x99; isso não prova integração ao runtime Atlas.
- Backup real do Pentium foi ativado e restaurado isoladamente em checkpoint anterior, **mas o escopo anterior era `~/atlas` e `~/.hermes`**. **RISCO CRÍTICO**: `~/pentium-agent/atlas` (runtime real) não foi explicitamente incluído nas duas fontes anteriores. Corrigir cobertura de backup de forma compatível antes de qualquer alteração de produção.

## Frentes de especialistas
| Equipe | Plano | Critério de entrega |
|---|---|---|
| A — Arquitetura | Mapear entrypoints reais, interfaces/protocolo e módulos antigos; comparar repo x99, runtime em pentium-agent e pasta ~/atlas; classificar divergências | Matriz arquivo→dependência→consumidor→ambiente, mapa de migração e testes de import/fluxo |
| B — Feature creep | Inventário AST + referência dinâmica para distinguir módulo sem import de entrypoint CLI, worker, plugin ou código morto; rastrear feature flags e configs | Tabela KEEP/ACTIVATE/REFACTOR/REMOVE_CANDIDATE com prova e testes de regressão; não remover no primeiro checkpoint |
| C — Conversação/Hermes | Provar rota Discord/CLI→cognitive_daemon→hermes_adapter→resposta; analisar fallback e seleção de modelo gratuito sem acessar tokens | E2E offline + smoke limitado de ferramenta, orçamento e falhas |
| D — Memória e emoções | Provar leitura/gravação da memória persistente e efeitos do estado afetivo em prompts/respostas; resolver lacunas M3→Graph v2 | Testes rastreáveis de recuperação e sinal emocional refletido na resposta; consentimento e minimização de dados |
| E — OpenCode/Agentes | Estabilizar bridge/outbox/session, qualificar acesso local/remoto, garantias de TDD/default deny e limites de delegação | Agent handshake, plano→execução→relatório autenticado, testes isolados; sem deploy automático |
| F — Plataforma/DR | Certificar fontes reais do backup e do serviço, consistência de deploy, health, rollback e recursos | Artefato idempotente + restore isolado + validação física em Pentium antes de ativar feature |

## Sinais de feature creep (triagem AST, não remoção)
Auditados 176 arquivos Python no nível raiz de `infrastructure/pentium/atlas`; nenhuma SyntaxError na análise AST. Referências de import diretas (não incluem chamadas CLI/dinâmicas e testes):
- `memory_preference_tracker.py` e `memory_project_adapter.py`: zero importadores diretos identificados; candidato a revisar integração de memória, não declarado morto.
- `affective_boot_certification.py`, `cognitive_context_bridge_certification.py` e `hermes_physical_smoke.py`: zero importadores diretos; provavelmente scripts/certificações executados diretamente; não apagar.
- `agency_worker_cli.py` e `cognitive_daemon.py`: zero importadores diretos mas são entrypoints potenciais/confirmados; **exemplo de falso positivo** na identificação automática de código morto.
- `memory_graph.py` é diretamente importado por `memory_project_adapter.py`; `affective_runtime.py` por `affective_composition.py`; `hermes_adapter.py` por chat_cli, cognitive_daemon e voice_daemon. Existência de imports não prova que a feature atinge a resposta ao usuário.
- `config_agency_specialists.json`: enabled=false. Ativar sem gate CP-AA7 violaria controle atual. Voz mantida desativada até hardware.

## Bugs, riscos e inconsistências já verificados
**P0 BACKUP COVERAGE:** path de execução `~/pentium-agent/atlas` distinto de `~/atlas` usado no backup real. O backup não prova proteção da árvore instalada de execução.
**P0 DEPLOY DRIFT:** dois diretórios Atlas presentes no Pentium e 176 módulos Python de topo no repositório local versus 168 em `~/pentium-agent/atlas`. Diferença não prova bug nem quais arquivos faltam: requer comparação de hashes/versões, mantendo a live.
**P1 AGENT-ORCH:** a tentativa de criar 2 sessões OpenCode em paralelo teve resultados parciais: uma sessão criada mas sem relatório final confirmado; outra retornou launcher_error. Não contar esses agentes como trabalho concluído.
**P1 INTEGRATION:** o OpenCode está acessível por bridge no x99, mas não foi comprovado como provider Atlas→Hermes em produção; `opencode` ausente no PATH remoto do Pentium.
**P1 MEMORY/AFFECT:** há código de grafo e composição afetiva, mas fluxo fim-a-fim de memória e influência nas respostas não certificado.
**P2 VOICE:** serviço inativo, compatível com a ausência de microfone. Não usar como justificativa para bloquear interface de texto.
**P2 WEB:** há browser-use instalado no Hermes, mas pesquisa autenticada e citável Atlas→Hermes ainda não certificada. Presença de binário não é funcionalidade.

## Checkpoints com TDD e gates
- CP-AUD01: congelar inventário live com hashes apenas de código (não de segredos); mapear service→module→config→persistência. GATE: fontes de verdade identificadas.
- CP-DR15: corrigir lista de fontes backup para cobrir runtime `~/pentium-agent/atlas`, testar backup + restore isolado ANTES de mudanças em produção. GATE: recuperar o estado funcional, não só código legado.
- CP-AUD02: matriz de feature creep, separar imports dinâmicos/entrypoints e calibrar classificação com testes. GATE: nenhum componente removido sem consumer test.
- CP-CONV01: runtime Hermes ↔ Atlas texto; adapter com timeouts, modelos gratuitos selecionados pelo Hermes, métricas sem vazar credenciais.
- CP-MEM01: adapter de memória único para Hermes e Atlas, leituras explícitas, gravação auditável, recuperação contextual e política de retenção.
- CP-EMO01: evento afetivo → composição segura de prompt → resposta modificada; evitar linguagem que implique sentimentos reais.
- CP-WEB01: tool de busca via Hermes com allowlist, fontes e limite, sem acesso a credenciais.
- CP-AGENT01: bridge OpenCode validada com fila confiável, relatório obrigatório, permissão READ primeiro.
- CP-DEPLOY01: staging/teste→backup/rollback→deploy atômico→smoke Atlas/Hermes→canary; sem mexer em live até verde.
- CP-H12/AA7: revalidar gates antes de qualquer autonomia de escrita.

## Evidências
- Pentium: systemd user `atlas-cognitive` active, WorkingDirectory `/home/deraldinho/pentium-agent`; atlas-discord/observation/dashboard active; atlas-voice inactive.
- AST snapshot: `.atlas/opencode/tmp/atlas_feature_audit.json` e analisador `.atlas/opencode/tmp/atlas_feature_audit.py` no x99.
- Agentes lançados por `tools/atlas-opencode-bridge.ps1`: tasks `20261013T145925Z-37a8d48d`, `20261013T145953Z-ad7d36f1`. Não utilizar opinião do agente sem verificação independente.
- Nenhum deploy de Atlas 5.0, instalação nova de Hermes/OpenCode ou ativação de agentes nesta auditoria.


## Atualização executada: CP-DR15 — cobertura do runtime real corrigida
**2026-10-13, concluído e certificado para RESTORE LOCAL.**
- O script `tools/atlas-pentium-backup.sh` agora exige também `/home/deraldinho/pentium-agent/atlas` como fonte. O runtime real contém o banco `runtime/memory.sqlite3`, que não poderia ficar fora do plano SQLite transacional.
- A captura transacional foi separada em dois estágios no mesmo backup: `sqlite-hermes` e `sqlite-live`. O script foi validado por `bash -n`, enviado ao Pentium, e o serviço existente `atlas-pentium-backup.service` foi executado **com sucesso** (`Result=success`, `ExecMainStatus=0`). Timer diário mantido ativo, sem reiniciar os serviços Atlas.
- Novo snapshot real **`1a6a427f`**, 938,001 MiB. `restic ls` confirmou `pentium-agent/atlas/cognitive_daemon.py`, `sqlite-live/manifest.json` e imagem transacional no snapshot.
- **Restore real isolado e aprovado** de `1a6a427f`: arquivo `pentium-agent/atlas/cognitive_daemon.py` recuperado, **2 SQLite do Hermes + 1 SQLite do runtime Atlas** restaurados por `sqlite_snapshot.restore` e todos aprovados por `PRAGMA integrity_check`. Evidência remota: `LIVE_ATLAS_AND_HERMES_SQLITE_RESTORE_PASS {'sqlite-hermes': 2, 'sqlite-live': 1}` e `LIVE_RUNTIME_SNAPSHOT_RESTORE_CERTIFIED`.
- **P0 de cobertura de backup local RESOLVIDO.** Permanecem P0 **destino offsite**, recuperação após perda física do Pentium e guarda externa da chave. Recuperação local não comprova disaster recovery offsite.
- O helper DR-13 genérico pressupõe um manifesto único no estágio `sqlite`, de modo que **não cobre** este novo formato de dois estágios. A prova usada restaurou ambos os estágios de maneira explícita; CP-DR16 deve refatorar/estender o verificador genérico via TDD, sem relaxar suas restrições de symlinks nem autorizar sobrescrita de bancos vivos.

## Status efetivo da orquestração OpenCode
Agente A task `20261013T145925Z-37a8d48d`: **TIMEOUT**, sem relatório e sem evidência de análise concluída.
Agente B task `20261013T145953Z-ad7d36f1`: **LAUNCHER_ERROR**, sem relatório.
Não marcar esses agentes como `done`. Diagnóstico AST, auditoria de runtime, inventário de serviços, checagem de backup e TDD foram conduzidos independentemente pelo orquestrador, com evidências. CP-AGENT-00 deve investigar transport/API/modelo e testar contrato de relatório obrigatório antes de retomar delegações em produção.

## Testes da auditoria
`py -m pytest --import-mode=importlib infrastructure/pentium/atlas/tests infrastructure/pentium/agent/tests infrastructure/backup/tests -q` → **1.149 passed, 25 skipped, 53 subtests passed** em 27,56 s, log `.atlas/opencode/tmp/cp-aud01-full-regression.log`. `git diff --check` retornou 0. Este GREEN atesta a suíte local, **não o E2E Hermes/OpenCode live**.

## Deploy e instalação
A única alteração na máquina de produção nesta execução foi a **atualização do script já utilizado pelo serviço de backup**, com um snapshot e restore isolado subsequentes. Nenhum deploy de release Atlas 5.0, alteração nos processos cognitivos, instalação de OpenCode no Pentium ou ativação de novos agentes foi realizado. O Atlas 5.0 continua um plano de evolução, não uma versão instalada.


## Retificação final de status do Agente A
Após ter sido marcado `timeout`, o agente A **finalmente escreveu seu relatório** no outbox `.atlas/opencode/outbox/20261013T145925Z-37a8d48d.md`; status final observado: `report_written`. O arquivo contém mapa preliminar HermesAdapter→cognitive_daemon, riscos de PATH/modelo, política de capabilities e proposta TDD CP-001 a CP-005. O agente reporta testes focados 6+2+4+11 aprovados, mas o relatório contém afirmações não verificadas independentemente e resultado de 1067 testes coletados distinto da regressão canônica; **não confundir relatório com validação de deploy**. A auditoria independente local efetivamente executou **1149 passed, 25 skipped, 53 subtests passed**.

Agente B continua `launcher_error`, **não houve entrega**. CP-AGENT-00 deve tornar tolerante a concorrência/falha e exigir status terminal e outbox íntegro antes de aceitar delegação. Nenhum dos agentes recebeu autorização para alterar código ou fazer deploy.

## Contrato de backup verificado por regressão
`py -m unittest tools.test_atlas_pentium_backup_contract -q` → 3 testes aprovados; verifica inclusão explícita de runtime real, dois estágios SQLite e ausência de forget/prune/unlock automático.
