# Atlas 5.0 — Orquestração de implementação e QA (2026-10-13)

## Escopo, controle e realidade de execução
Root x99: `C:\Users\deral\DevEx-HomeLab`, branch existente `atlas/v0.4.0-proprioception-autonomy`, **sem novos worktrees, commit, push ou deploy do código cognitivo**. O operador solicitou distribuir implementação entre agentes e um auditor final. O bridge OpenCode é **exclusivo por projeto** (`.atlas/opencode/tmp/active.lock`), o que impede executar múltiplos OpenCode de escrita simultaneamente dentro do mesmo repositório sem coordenação.

## Agentes executados
| Especialista | Task ID | Estado observado | Aceitação |
|---|---|---|---|
| CP-AGENT-00: confiabilidade bridge | `20261013T151812Z-d3965a34` | `timeout`, relatório ausente na verificação | **NOT DONE**. 11 testes baseline bridge passaram, mas o agente não provou patch |
| CP-MEM/EMO: conectar dados à conversa | `20261013T151818Z-7cdab8a8` | `timeout`, relatório ausente | **NOT DONE**. `hermes_adapter.py` não foi alterado nesta execução |
| CP-AUD/WEB: feature inventory | `20261013T151823Z-54f909bd` | `timeout`, mas relatório apareceu depois no disco | **PARCIAL**. Auditoria criada; teste originado pelo agente estava incorreto e foi substituído por contrato seguro |
| Agente final QA, independente/read-only | `20261013T152246Z-53421ab3` | `timeout`, relatório ausente na verificação | **NOT DONE** como relatório do agente. Auditoria final independente foi realizada pelo orquestrador com pytest |

**Não são bugs do runtime cognitivo:** `launcher_error` observado em tentativas concorrentes deve-se à exclusividade do bridge no projeto; precisa de fila explícita, não de remoção indiscriminada do lock. As sessões que ultrapassam deadline podem gravar relatórios posteriormente: reconciliar status sem reenviar o prompt, e não declarar sucesso apenas com `report_exists`.

## Correções comprovadas
- A análise de feature creep foi formalizada como `infrastructure/pentium/atlas/tests/test_feature_inventory_contract.py`, com três testes determinísticos read-only. Um primeiro teste gerado pelo agente **falhava por tratar qualquer flag ativa como bug** (inclusive Discord normal), procurava configs no diretório errado, importava pacotes em auditoria com risco de efeitos colaterais e engolia erros de import. A revisão substituiu por leitura e AST sem importar runtime. Não removemos componentes nem habilitamos flags.
- Resultados finais da regressão local: **1152 passed, 25 skipped, 53 subtests passed** em 27,10s no comando:
  `py -m pytest --import-mode=importlib infrastructure/pentium/atlas/tests infrastructure/pentium/agent/tests infrastructure/backup/tests -q`
  Log: `.atlas/opencode/tmp/atlas-final-qa-regression.log`.
- Baseline da integração OpenCode: `py -m pytest -q tools/test_atlas_opencode_api.py` — **11 passed** antes dos agentes. Não certifica execução efetiva de um modelo nem serviço Hermes live.
- `git diff --check` passou na verificação anterior; alterações posteriores exigem execução final.

## Plano de implementação remanescente — fases e gates
1. **CP-AGENT-00 P0**: fila por projeto, retries pós-lock somente na fase de launcher; status terminal e reconciliação sem duplicar prompts; teste de timeout, report tardio, status de crash e ausência de leaks. Aceitar somente depois de agente real concluir e agente QA gerar provas.
2. **CP-CONV-01**: teste offline de Discord/CLI → daemon Atlas → HermesAdapter, verificando seleção de modelos pelo Hermes, tempo limite e fallback; comprovar em Pentium com probe sem segredos.
3. **CP-MEM-01**: integrar estado consolidado do Atlas à composição de prompt do Hermes usando adapter com tipagem e proveniência, sem acoplar Hermes diretamente a SQLite. TDD de recall/contradição/retention.
4. **CP-EMO-01**: converter eventos afetivos existentes em ajustes auditáveis de tom/proatividade, sem persuasão ou alegação de sentimentos reais. Teste de efetividade da resposta.
5. **CP-WEB-01**: provar internet search via ferramenta Hermes com guardrails, timeout/citação e bloqueio de acesso a arquivos de segredo; preferir teste fechado offline primeiro.
6. **CP-AGENT-01**: fluxos OpenCode e Hermes com agentes isolados READ-only antes de escrita; manter `config_agency_specialists.json.enabled=false` até gates.
7. **CP-AUD-02**: comparar hashes de `~/pentium-agent/atlas` versus `~/atlas` e HEAD x99, classificar cada módulo `KEEP/INTEGRATE/REFACTOR/REMOVE_CANDIDATE`; não excluir por mera falta de import AST. Módulos dinâmicos e entrypoints systemd ficam explicitamente protegidos.
8. **CP-DEPLOY-01 / QA-FINAL**: montar release reversível, backup real do runtime com restore isolado validado, testes E2E físicos e rollback; somente então implantar incrementos no daemon cognitivo. Não houve deploy nesta rodada.

## Decisão de segurança
**HOLD PARA DEPLOY COGNITIVO**: OpenCode sem prova de conclusão nos checkpoints P0, memória/emoção/pesquisa sem E2E. `atlas-cognitive` e Hermes live não foram reiniciados. Os backups Restic Pentium e o timer permanecem sob gestão do checkpoint DR15 anterior.


## Rodada final após relatórios atrasados e depuração (retificação)
`reconcile` consultou as sessões OpenCode **sem reenviar prompts**:
- Agente bridge `20261013T151812Z-d3965a34`: **reported** após timeout, relatório no outbox. Não assumir que um relatório equivale à aceitação de um patch, e nenhuma alteração do bridge em produção foi implantada.
- Agente memória/afeto `20261013T151818Z-7cdab8a8`: **pending** mesmo após a janela operacional; foi **interrompido pelo orquestrador** via API retornando `{'interrupted': True}` para impedir edições tardias concorrentes. Não entregou relatório.
- Agente feature inventory `20261013T151823Z-54f909bd`: **reported** após timeout; o teste inicial gerado continha bugs de contrato e foi refeito com validação de AST/read-only. Resultado do teste revisado: **3 passed**.
- Agente final QA `20261013T152246Z-53421ab3`: **reported** após timeout. Seu relatório destacou bugs em testes de inventário e nos mocks do bridge. Essas falhas foram reproduzidas e corrigidas por revisão independente.

## Incrementos efetivos de código e TDD
**CP-MEM-01 parcial/CP-EMO-01 certificado em prompt, sem deploy**:
- `infrastructure/pentium/atlas/hermes_adapter.py`: injeta explicitamente memórias recuperadas do contexto já preparado pela `ReactionLoopCognitivo` em um bloco `<retrieved_memories>` limitado a 6 entradas e aproximadamente 2,5k caracteres; conteúdos escapam delimitadores XML e são rotulados como dados não confiáveis. O JSON contextual da seção final também escapa caracteres XML para bloquear encerramento falso de tag por memória maliciosa.
- `infrastructure/pentium/atlas/tests/test_hermes_adapter.py`: TDD RED anterior à correção, GREEN com **7/7** inicialmente; teste posterior comprova que o estado afetivo alarmado atinge o prompt Hermes. A existência do prompt **não prova** que um modelo gratuito responde conforme o tom pretendido nem que grava novas memórias. Sem mudança na seleção de modelos do Hermes.
- O teste de feature inventory foi corrigido para não tratar flags verdadeiras como erro; evitar import dinâmico durante auditoria; checar entrypoint efetivo via arquivo systemd. Config `agency_specialists.enabled=false` preservada.
- `tools/test_atlas_opencode_api.py`: os erros de teste apontados pelo auditor final (mock de path, esgotamento de iterator) foram reproduzidos e corrigidos, sem desabilitar as proteções da API.

## Validação pós-ajustes
- Regressão canônica pós-memória/emoção: **1154 passed, 25 skipped, 53 subtests passed** em 27,31s. Log: `.atlas/opencode/tmp/atlas-final-post-memory-regression.log`.
- Bridge unittest após correção: **16 tests, OK** em 0,317s. Log: `.atlas/opencode/tmp/bridge-post-agent.log`.
- `git diff --check`: **0**.
- **Deploy de novas capacidades cognitiva/memória/emoção: NÃO realizado**; exigência de smoke com modelo/Hermes real, rollback e gates operacionais continua. O Pentium permanece na versão anterior de runtime cognitivo, sem restart.
- CP-WEB-01 e CP-AGENT-01: **NÃO IMPLEMENTADOS**; pesquisar com fontes e delegação do OpenCode dentro do Atlas continuam aguardando políticas e prova E2E.
