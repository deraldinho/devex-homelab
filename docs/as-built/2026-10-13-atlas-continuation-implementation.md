# Atlas 5.0 — CP-AGENT00/MEM02/WEB01/AUD02 (continuação 2026-10-13)

## Escopo e premissas
Repositório original `C:\Users\deral\DevEx-HomeLab`, branch `atlas/v0.4.0-proprioception-autonomy`; **sem novos branches, worktrees, commits, push ou deploy cognitivo ao Pentium**. Prioridade do operador: dar mais tempo às tarefas longas do OpenCode, não tratar demora como falha instantânea.

## Orquestração efetiva
- Um agente OpenCode anterior (bridge) produziu relatório tardio reconciliado, mas deixou código de espera com laço não delimitado após a aquisição e regressões em testes. Seu resultado não foi promovido automaticamente.
- Task `20261013T160454Z-0c48767d`: CP-AGENT00, model `opencode/nemotron-3.5-lightning-free`, tempo máximo **900 segundos**. A sessão terminou em **agent_failed** depois de vários minutos (**não** timeout). Nenhum relatório dessa execução; houve alterações parciais auditadas manualmente.
- Task `20261013T161058Z-6c56f555`: CP-CONV01, modelo `opencode/ling-3.1-flash-free`, tentativa **agent_failed**, sem relatório.
- Task `20261013T161103Z-f5e72576`: CP-WEB01, modelo `opencode/ling-3.1-flash-free`, terminou **agent_failed** após aguardar por vários minutos, sem relatório.
- Task `20261013T161958Z-6c12d2f6`: último agente QA independendente, modelo gratuito `opencode/mimo-v2.6-flash-free`, **900 segundos de limite**, iniciado e acompanhado; estado final a atualizar após retorno da sessão. Seus comentários não substituem verificação por testes reais.
- Lista de modelos `opencode/*-free` consultada diretamente no binário x99 (não presumida). **Nenhum agente pode ser declarado concluído sem relatório e testes válidos.** Nenhum timeout causou reenvio automático de prompt a uma sessão já criada.

## Melhorias implementadas e testadas
### CP-AGENT00 — Espera/concorrência e segurança da fila
`tools/atlas_opencode_api.py` e `tools/atlas-opencode-bridge.ps1`:
- Tempo padrão de execução aumentado para **900 segundos** (limite já aceito).
- `wait_for_project_lock` adquire `active.lock` via criação exclusiva **O_EXCL**; aguarda o projeto sem roubar lock, com orçamento monotônico compartilhado entre fila e execução.
- Se o orçamento expira aguardando outro agente, retorna `busy` sem submeter prompt nem remover lock alheio; não reexecuta sessão após timeout.
- `reconcile()` exige que nenhuma execução detenha o lock e consulta outcome da sessão antes de aceitar relatório tardio. Sessões `failed`, `interrupted` ou `pending` não viram sucesso somente porque existe um arquivo report.
- **18 testes bridge aprovados**, incluindo fake concurrent lock, liberações, timeouts, retorno tardio e agente failed com report. Log `.atlas/opencode/tmp/cp-agent00-final-tests.log`.

### CP-MEM02 — Recuperação de memória a partir da pergunta
- `ReactionLoopCognitivo` recuperava memórias usando `fingerprint` do estímulo, que pode ser um ID opaco, em vez das palavras da conversa.
- Agora usa `mensagem_usuario` (quando existe) ou última mensagem da origem `human.*`, limitada a 512 caracteres, na busca de memórias e workspace; para estímulos não humanos preserva o fingerprint.
- `HermesAdapter` já possui bloco limitado de memórias não confiáveis, serialização escapada, e o estado afetivo no prompt.
- TDD RED confirmado: `'backup do Pentium' not found in 'random-stimulus-12345'`; GREEN: 10 testes do loop e conjunto Hermes. Log `.atlas/opencode/tmp/cp-mem02-red.log`.
- **Não confirmado em conversação LLM física** e não implantado na live.

### CP-WEB01 — Política isolada de referências seguras
- Criado `infrastructure/pentium/atlas/web_research_policy.py`: allowlist exato por hostname, somente HTTPS, rejeição de userinfo, IPs, localhost, portas anômalas e controle de caracteres; snippets e títulos escapados e limitados.
- **8 testes e 11 subtestes aprovados**, com TDD RED→GREEN. Log `.atlas/opencode/tmp/cp-web01-green.log`.
- **Módulo propositalmente inativo**. Ele não faz pesquisa nem requisição HTTP; a integração real deve validar DNS público e redirecionamentos e comprovar fontes.

### CP-AUD02 — Inventário verificável de feature creep e drift
- Comparação segura por SHA256 **apenas de arquivos Python** no x99 versus `~/pentium-agent/atlas` e `~/atlas`: 176/168/164 módulos de topo.
- **157 hashes iguais** por comparação; 7 módulos críticos divergentes, 12 presentes no repo ausentes da live e quatro exclusivos da live. Matriz: `docs/as-built/2026-10-13-atlas-runtime-drift-by-hash.md`.
- Quatro módulos host-only de `llama_cpp` / `llama_server` sem importadores diretos num levantamento AST; **candidatos para investigação, não remoção**. Verificar importlib, CLI, unidades e subpacotes antes de qualquer decisão.
- Proibido deploy automático/sobrescrita em massa: `cognitive_daemon.py`, `hermes_adapter.py` e `reaction_loop_cognitivo.py` divergem na live. Não executar cp -r para Pentium.

## QA independente local
- Suite `py -m pytest --import-mode=importlib infrastructure/pentium/atlas/tests infrastructure/pentium/agent/tests infrastructure/backup/tests -q`: **1165 passed, 25 skipped, 64 subtests passed** em 27.23 s. Log `.atlas/opencode/tmp/atlas-5-audit-full-suite.log`.
- Suite bridge/backup `py -m pytest -q tools/test_atlas_opencode_api.py tools/test_atlas_pentium_backup_contract.py`: **20 passed** antes do teste adicional de late-failed, depois `tools/test_atlas_opencode_api.py` isolado **18 passed**. Exigir execução combinada final.
- `git diff --check` sem erros. Warning de CRLF no serviço systemd já pré-existente na árvore local; não houve deploy desse arquivo.
- Pentium verificado por SSH: `atlas-cognitive`, `atlas-discord`, `atlas-observation`, `atlas-dashboard` e timer `atlas-pentium-backup` **active**; último serviço backup `Result=success`.

## Gates remanescentes
1. Conclusão verificável do último agente QA, com relatório válido e reconciliação do servidor; sem auto-replay da sessão.
2. CP-CONV01 E2E Hermes em ambiente controlado e CP-MEM02/EMO01 prova física de comportamento conversacional.
3. CP-WEB01 integração de busca real com DNS/TLS, redirecionamento seguro, proveniência e limites; controle de permissões.
4. Compatibilidade de deploy/rollback entre as **sete** diferenças críticas repo/live; backup DR15 inclui runtime real, mas offsite continua P0.
5. CP-AGENT01 delegação real e AA7 permanecem desabilitados até os gates, sem ativação automática.

**Release de Atlas 5.0 no Pentium: NOT DEPLOYED (HOLD)**.


## Certificação após o agente final de QA — conclusão desta rodada

**Agente independente CP-FINAL-QA**: task `20261013T161958Z-6c12d2f6`; modelo gratuito `opencode/mimo-v2.6-flash-free`. Sessão do OpenCode terminou com `outcome=succeeded`, bridge confirmou `state=reported`; relatório estruturado existe em `.atlas/opencode/outbox/20261013T161958Z-6c12d2f6.md` e foi verificado pelo validador de relatórios. A execução consumiu aproximadamente **873 segundos** — o limite estendido de **900 segundos** evitou encerramento prematuro.

O último agente identificou dois bugs de segurança/qualidade com evidência de código. Foram **corrigidos após a auditoria**, por TDD, sem deploy:
1. **CP-PROMPT-01 — Prompt injection em entrada, histórico e observações**: em `infrastructure/pentium/atlas/hermes_adapter.py`, texto do operador, mensagens de histórico, nome de capability e payload de ferramenta agora usam escape de markup seguro. TDD RED produziu `<system>INJECTED USER` no prompt. Após correção, `test_untrusted_history_and_tool_payload_cannot_break_prompt_tags` e demais testes Hermes passaram (**9/9**). Memória recuperada continua escapada e limitada.
2. **CP-AGENT-REPORT — Falso sucesso por arquivo mínimo**: `tools/atlas_opencode_api.py` agora só aceita relatório com Task-Id no início, até `MAX_REPORT_BYTES`, com todas as seções obrigatórias **Resumo, Arquivos alterados, Testes, Bloqueios e riscos, Proximos passos** preenchidas; rótulos com/sem acento são normalizados. `run()` e `reconcile()` usam o mesmo validador; estados previamente `reported` são revalidados, impedindo bypass de relatórios antigos incompletos. TDD RED demonstrou que apenas `Task-Id` era aceito; RED adicional demonstrou bypass por status prévio `reported`. GREEN após correção.
3. O `if __name__ == '__main__'` de `test_reaction_loop_cognitivo.py` foi movido para o final, removendo armadilha para execução unittest direta.

### Teste final da árvore local **após todas as correções**
- `py -m pytest --import-mode=importlib infrastructure/pentium/atlas/tests infrastructure/pentium/agent/tests infrastructure/backup/tests -q`: **1166 passed, 25 skipped, 64 subtests passed** em 28.21s; log `.atlas/opencode/tmp/atlas-final-verified-infra.log`.
- `py -m pytest -q tools/test_atlas_opencode_api.py tools/test_atlas_pentium_backup_contract.py`: **23 passed** em 0.73s; log `.atlas/opencode/tmp/atlas-final-verified-tools.log`.
- `py -m py_compile` dos módulos críticos revisados passou.
- `git diff --check`: exit 0 (somente warning de conversão CRLF no serviço systemd preexistente).

### Situação real do deploy
**Não foi promovido o Atlas cognitivo ao Pentium.** A árvore de desenvolvimento contém 7 divergências de código críticas em relação ao runtime real, 12 módulos não instalados e 4 módulos exclusivos no Pentium. A live está estável e o backup automático ativo, confirmados via systemd. Qualquer deploy deve ter revisão de compatibilidade dos módulos e rollback validado, com flags AA7/health ainda em default-deny.

**Pendências ainda NÃO concluídas**: integração de busca web em tempo real, ativação de agência OpenCode→Atlas, E2E de Hermes com provedor gratuito e recuperação offsite independente. Os modelos gratuitos Nemotron e Ling tiveram sessões `agent_failed`; a alternativa Mimo concluiu o QA. Não houve repetição automática de prompts após falhas, evitando trabalho duplicado.
