# Atlas CP26–CP31 — relatório de execução auditável (15/10/2026)

## Escopo real versus meta
A meta completa é implementação + homologação + deploy CP26–CP31. Esta execução avançou o CP26 no código e acionou a primeira onda de agentes; **não autoriza a declaração de conclusão global** nem habilitação de políticas.

## Runtime físico e reproduções
- Acesso SSH confirmado x99 -> `pentium` e x99 -> `core-auto`.
- Pentium `atlas-cognitive`, `atlas-discord`, `atlas-observation`, `atlas-dashboard` ativos.
- `GET http://192.168.88.3:8765/`, `/healthz`, `/api/status` → HTTP 200 (local e via x99).
- `python3 -m atlas.hermes_preflight` por SSH sem PATH adequado → `profile_unavailable`; com PATH idêntico ao `atlas-cognitive.service` → `ATLAS_HERMES_PREFLIGHT_PASS`. Não alterar o perfil.
- Em 15/10, `POST /api/chat` via x99 recebeu HTTP 202, message_id `e346b865-417e-4f2c-aca4-813f4bd5ab56`, stimulus_id correlacionado `human-chat-e346b865-417e-4f2c-aca4-813f4bd5ab56`. Eventos da mesma cadeia: `ANALISANDO` → `INFERINDO` → `DEGRADADA` (cerca 26s). Causa confirmada pelo registro: `saida_llm_invalida`, **não** timeout ou falta de perfil.
- Probe físico descartável de inferência Hermes → `BACKEND_SUCCESS True` em ~29s; retornou texto natural (141 caracteres), sem abertura de JSON, sem Markdown fence. O parser estrito de 8 campos rejeita texto natural; usuários não receberam resposta comprovada.
- Dashboard LAN aceita `POST /api/chat` não autenticado; revisado pelo agente CP26 e reproduzido com mensagem de teste. Risco de injeção de eventos e consumo indevido do pipeline cognitivo. NÃO fechar porta / quebrar dashboard sem projeto de auth e UX.

## Implementação local da correção CP26 — sem deploy
- Criado `infrastructure/pentium/atlas/conversational_fallback.py`: aceita apenas fala natural humana limitada; recusa JSON, code fences, metadados de capabilities, possíveis segredos, caracteres de controle e alegações de ações já executadas.
- Alterado pontualmente `infrastructure/pentium/atlas/reaction_loop_cognitivo.py` (arquivo com alterações preexistentes): somente quando a saída JSON é inválida **e motivo=INTERACAO_HUMANA** aceita texto natural seguro, `intencao=None`, `parametros_intencao={}`, `intencao_autorizada=False`. Incidentes, auto-work e execução de capabilities continuam exigindo JSON v1 e autorização explícita.
- Criado `infrastructure/pentium/atlas/tests/test_cp26_natural_fallback.py` com regressões positivas e negativas.
- O experimento de aceitar Markdown-fenced JSON foi **revertido** porque viola contratos de testes anteriores; `saida_cognitiva.py` permanece estrito.
- Teste RED inicial comprovado; primeiro GREEN parcial introduziu duas falhas de contrato na regressão ampliada (1.247 passed, 2 failed); ajustes foram feitos no código e a execução seguinte concluiu **1.246 passed, 3 skipped, 85 subtests passed, exit 0** nos pacotes `infrastructure/pentium/atlas/tests` e `infrastructure/pentium/agent/tests` (diferença no total decorre dos novos testes).
- Dashboard + dispatcher: `98 passed, 2 subtests passed`, exit 0. Dispatcher: `8 passed`, exit 0. `git diff --check` exit 0; avisos de line endings anteriores não foram ocultados.
- Importante: testes com fake runner NÃO homologam uma resposta real pós-deploy. CP26 permanece BLOCKED na produção.

## Orquestração autenticada OpenCode
Servidor v2.0.29, recepção via `http://127.0.0.1:49374`, credencial privada local `~/.config/opencode/service.json`. O CLI x99 tem v2.0.28 e não conseguiu conectar ao servidor sem OPENCODE_PASSWORD, motivo para usar API autenticada. Dispatcher com ledger persistente, anti replay e modelo allowlist criado em `tools/atlas_cp26_cp31_dispatch.py`.

### Missões PLAN
- `cp26-security` MiMo v2.6 Flash → `ses_ebe2f8d91ffeo8O76ddp3CkCDw`, server `succeeded`; confirmou vulnerabilidade estática da LAN. Sem patch/deploy.
- `cp27-dr` Ling 3.1 Flash → `ses_ebe2f422cffeiFsR5B2mpUaXjp`, server `failed` (`provider.no-route`).
- `cp27-dr-fallback` Nemotron 3.5 Lightning → `ses_ebe2b6685ffeapYft1ZrBqp8Zb`, server `succeeded`; relatório DR histórico, não certificação física nova.
- `cp28-transport` Nemotron 3.5 Lightning → `ses_ebe2f322bffeLA3RaVQ30mYMGv`, server `succeeded`; revisão arquitetural de código, não delegação física Core comprovada.

### Missões BUILD
- `cp27-release-inventory-build` Nemotron 3.5 Lightning → `ses_ebe1d59adffedQ9pEip5qbie1b`, criados `tools/atlas_cp27_release_inventory.py` e `tools/test_atlas_cp27_release_inventory.py`; aguardando receipt terminal e revisão independente antes da integração.
- `cp30-graph-contract-build` MiMo v2.6 Flash → `ses_ebe1d4a5affeD5pYaP2s2f2GDy`, aguardando receipt terminal e revisão independente.

Servidor `succeeded` significa apenas finalização da sessão; não comprova `GREEN` de testes nem deploy. Agentes sem terminal confirmado não devem ser reexecutados automaticamente.

## Segurança e quality gates
- **CP26 = BLOCKED produção:** deploy da correção e E2E Discord→LLM→resposta ainda faltantes.
- **CP27 = BLOCKED:** checkout inicial com 113 caminhos pendentes; backup local existe; restore offsite e rollback auditáveis ainda não demonstrados. Não limpar/commitar em lote nem alterar dados persistentes.
- **CP28 = BLOCKED:** `config_agency_specialists.json` permanece `enabled:false`; testes físicos Core e comprovante durable de delegação pendentes.
- **CP29 = BLOCKED:** `self_healing_v1` permanece desabilitado; incidente sintético e auditoria pendentes.
- **CP30 = IN DEVELOPMENT:** MemoryGraph v2 ainda não migrado.
- **CP31 = BLOCKED:** web segura, voz física, auth do dashboard e observabilidade final não homologadas.

## Próximos gates verificáveis
1. Revisar artefatos BUILD CP27/CP30 depois do terminal, rodar testes reais, corrigir defeitos sem substituir alterações do usuário.
2. Corrigir autenticação de `POST /api/chat` mantendo a UI utilizável; TDD contra clientes anônimos LAN, replay/CSRF e credenciais no browser.
3. Certificar backup/restore offsite em destino independente e rollback de estado SQLite; reconciliar release e 113 caminhos antes de publicar nova versão.
4. Com rollout/rollback homologados, fazer deploy CP26 e repetir conversa física end-to-end, inclusive no Discord e memória entre sessões.
5. Somente após CP26/27, habilitar CP28 READ-only Core em canário e depois CP29+CP30+CP31 conforme gates.

## Checkpoint adicional — reconciliação dos agentes e CP26/CP28 (15/10/2026, sessão noturna)

### Evidência de terminal dos agentes anteriores
- PLAN `cp26-security`: succeeded.
- PLAN `cp27-dr`: failed (`provider.no-route`); `cp27-dr-fallback`: succeeded. Não reexecutar a falha original.
- PLAN `cp28-transport`: succeeded.
- BUILD `cp27-release-inventory-build`: succeeded. Revisão independente encontrou truncamento silencioso em 100 caminhos; corrigido com paginação e contagem de entradas totais, sinal `has_more`, offset, fingerprint especificado como hash do status, não conteúdo. `14 passed` e x99 real: 122 caminhos em páginas 100+22.
- BUILD `cp30-graph-contract-build`: succeeded. Novos `memory_graph_v2_contracts.py` e testes: `52 passed, 88 subtests passed`. Sem migração de dados.

### E2E, segurança e regressão
- O runtime continua em Pentium com `atlas-cognitive`, `atlas-discord`, `atlas-dashboard` e `atlas-observation` ativos, e `/healthz` HTTP 200.
- Comparação de revisões: source HEAD x99 `7e84c92`; runtime lê `2de0a12`. Divergência documentada; não promover release nem fazer commit indiscriminado.
- `POST /api/chat` no dashboard LAN foi comprovado anônimo; correção incremental local com TDD em `infrastructure/pentium/dashboard/atlas_dashboard.py` e `tests/test_cp26_chat_peer_security.py`.
- Sem autenticação nativa, o POST passa a aceitar somente conexões locais (loopback ou IP exato de bind no próprio Pentium). Bloqueio de outros IPs via HTTP 403 **antes da leitura do body ou gravação em inbox**. Headers `X-Forwarded-For` e `Origin` são ignorados como fontes de autorização. A leitura de métricas via LAN permanece intocada.
- Observação física de `ip route get 192.168.88.3`: socket local do Pentium para `192.168.88.3` usa origem `192.168.88.3`, portanto SSH local-forward do x99 preserva chat pelo proxy autorizado. Túnel proposto (ainda não homologado): `ssh -N -L 127.0.0.1:18765:192.168.88.3:8765 pentium` e abrir `http://127.0.0.1:18765/`. **Nunca divulgar o dashboard por HTTP aberto com POST irrestrito.**
- A alteração de peer é mitigação (capability de rede local), **não auth de usuário**. CP31 ainda precisa de HTTPS e autenticação/autorização do dashboard multiusuário. A origem do túnel não comprova identidade de pessoa; a autoridade local depende do SSH e controle do host.
- Teste RED inicial: `Handler._chat_peer_authorized` inexistente (10 subfalhas), GREEN: `5 passed, 11 subtests passed` com negação de peer remoto sintético, spoof de `X-Forwarded-For`, conservação de POST local idempotente. `py_compile` e `git diff --check` OK.
- QA full após CP30 antes do patch de peer: `1298 passed, 3 skipped, 175 subtests passed` (Atlas e agent). QA do dashboard após patch de peer: `116 passed, 13 subtests passed` incluindo dispatcher CP26 e inventário CP27; `git diff --check` exit 0. Testes ignorados não contam como homologação.
- Backup local: `atlas-pentium-backup.timer` agendado; diretórios offsite típicos inspecionados ausentes. **A ausência nesses locais não é prova definitiva de inexistência de qualquer backup remoto**, mas ainda não existe restauração offsite certificada neste checkpoint.
- Arquivos do patch de chat **somente no x99**. Não houve commit, push, restart nem deploy da correção; Pentium continua na versão anterior e o acesso anônimo deve ser tratado como risco aberto na produção.

### Nova onda OpenCode
- `cp26-chat-independent-qa`: sessão `ses_ebdec5b82ffeCCjbel3HHului4`, modelo Nemotron 3.5 Lightning, READ-only security review. Em execução na abertura do checkpoint.
- `cp28-receipt-ledger-build`: sessão `ses_ebdec533affeJU9gG5tumCodAW`, modelo Nemotron 3.5 Lightning, owner exclusivo de novo SQLite receipt ledger e respectivos testes. Em execução na abertura do checkpoint.

### Gate
CP26 LOCAL: testes GREEN, **produção BLOCKED** por ausência de rollout seguro, conversa real Discord e teste de túnel físico da nova versão. CP27: BLOCKED por release drift, árvore Git pendente e restore offsite; não prosseguir com deploy. CP28–CP31: parciais, sem toggles ativados e sem migração.

### Canário físico de segurança CP26 (sem deploy)
- Cópia isolada da implementação do dashboard, executada no Pentium em `/tmp/atlas-cp26-peer-canary/`, porta temporária `18766`, inbox temporário separado do runtime.
- Origem Pentium -> `192.168.88.3:18766/api/chat` com payload sintético: `LOCAL_HTTP:202`.
- Origem x99 -> mesma URL: `REMOTE_HTTP:403`; `GET /healthz` do x99: HTTP 200.
- O teste reproduz o comportamento do código corrigido na interface de rede real do host; ainda falta testar a abertura do browser por túnel SSH.
- Canário PID `2846165` encerrado pelo próprio script de teste; porta `18766` confirmada fechada. Nenhuma instalação/restart de serviço de produção.
- Este teste não comprova que a versão em produção esteja corrigida; `atlas-dashboard` de produção permanece inalterado em `8765`.

### Quality gate repetido após todos os patches locais
- Atlas + Agent: **1298 passed, 3 skipped, 175 subtests passed**, exit 0.
- Dashboard + Dispatcher + CP27 Inventory: **116 passed, 13 subtests passed**, exit 0.
- `git diff --check`: exit 0, com avisos de line-ending antigos.

### Reconciliador auditável do OpenCode
- O dispatcher `tools/atlas_cp26_cp31_dispatch.py` ganhou `reconcile <mission>`, que valida o ID remoto antes de persistir `SESSION_SUCCEEDED`, `SESSION_FAILED` ou `SESSION_CANCELLED`.
- Resultado desconhecido ou ID divergente não altera o recibo. A mesma reconciliação terminal é idempotente (não requisita novo estado ao servidor).
- `tools/test_atlas_cp26_cp31_dispatch.py`: teste RED demonstrou ausência da API; após implementação `11 passed, 3 subtests passed`, exit 0.
- Seis recibos originais reconciliados na pasta `.atlas/opencode/cp26-cp31/`: cinco `SESSION_SUCCEEDED`, um `SESSION_FAILED` (Ling), com fallback CP27 bem-sucedido. A existência do recibo NÃO certifica deploy, testes, nem qualidade do código.
- Após iniciar a segunda onda, `cp26-chat-independent-qa` e `cp28-receipt-ledger-build` estavam com mensagens de processamento, mas ainda sem campo remoto `outcome` terminal. Não reenviar nem registrar como concluídos antes de novo reconcile.

## Retomada 16/10/2026 — reconciliação da segunda onda e recuperação TDD

### OpenCode — estados terminais verificados no servidor
- `cp26-chat-independent-qa` sessão `ses_ebdec5b82ffeCCjbel3HHului4`: `SESSION_SUCCEEDED`. Revisão identificou como maior risco o bypass de filtro LLM em `ReactionLoopCognitivo` quando `capability_policy=None`. Outros itens de cobertura do dashboard foram classificados como menores.
- `cp28-receipt-ledger-build` sessão `ses_ebdec533affeJU9gG5tumCodAW`: `SESSION_FAILED`. Logs remotos contêm um erro `provider.internal` HTTP 502 e múltiplos `provider.internal` HTTP 504 de timeout. É uma falha de inferência do provedor; não é falha confirmada do runtime Atlas.
- Os recibos locais foram reconciliados com resultados terminais; não repetir sessões com status ambíguo e não transformar sucesso de sessão em homologação de implementação.

### Recuperação CP28 — ledger SQLite isolado no x99
- O agente deixou `infrastructure/pentium/atlas/agency_receipt_ledger.py` parcial, sem arquivo de testes.
- TDD: criado `infrastructure/pentium/atlas/tests/test_agency_receipt_ledger.py`. Baseline RED: `26 failed, 7 passed, 2 subtests passed`, evidenciando transições irrestritas, retries sem limites, conflitos de idempotência ignorados e validação insuficiente.
- Correção local: reimplementado ledger durável sem integrá-lo a produção, com inserção idempotente e verificação de imutáveis, campos limitados, SQL parametrizado, transições atômicas, estado terminal imutável, retry até o limite, marcador interno `last_started_retry` para impedir replay de retry, concorrência de SQLite verificada, erro sanitizado e limitado. A interface de leitura `get` continua com 11 campos.
- Um teste RED adicional flagrou replay do mesmo retry após falha subsequente; gate após correção: `15 passed, 21 subtests passed`. Execução não migra banco existente, não cria tarefa, não concede capacidade e não foi instalada no Pentium.
- Observação de engenharia: o schema CP28 é novo. Antes de integrar a dados persistentes, acrescentar versionamento explícito de schema/migração, restore/backup e prova de compatibilidade com consumidores/worker Core.

### Correção CP26 — fail-closed sem capability policy
- Testes RED em `infrastructure/pentium/atlas/tests/test_cp26_natural_fallback.py`: `2 failed`, provando que JSON de ação estruturado e texto de prompt-injection podiam ser exibidos em ausência de `capability_policy`.
- Corrigido `reaction_loop_cognitivo.py`: quando a política não existe, JSON com `intencao` retorna `capability_policy_unavailable` sem texto nem autorização. Texto não estruturado passa por `safe_natural_reply` e, se inválido, gera `saida_llm_invalida`. Preservado texto normal read-only dos narradores legados.
- Regressão antiga de cache esperava JSON bruto (não o texto parseado) em `test_reaction_loop_cache.py`. A expectativa foi deliberadamente atualizada para o contrato seguro `texto == "ok"`, `intencao=None` e `intencao_autorizada=False`. Não houve skip nem remoção de teste.

### Gates após recuperação (x99)
- `python -m pytest --import-mode=importlib -q infrastructure/pentium/atlas/tests infrastructure/pentium/agent/tests`: **1315 passed, 3 skipped, 196 subtests passed**, exit 0.
- `python -m pytest -q infrastructure/pentium/dashboard/tests tools/test_atlas_cp26_cp31_dispatch.py tools/test_atlas_cp27_release_inventory.py`: **119 passed, 16 subtests passed**, exit 0.
- `python -m py_compile` dos módulos modificados: exit 0. `git diff --check`: exit 0; warnings antigos de EOL sem erro.
- Status físico Pentium: serviços `atlas-cognitive`, `atlas-discord`, `atlas-dashboard`, `atlas-observation` ativos na verificação inicial. Runtime SHA `2de0a12` e x99 HEAD `7e84c92`; alterações locais sujas pré-existentes preservadas (última contagem: 128 caminhos).

### Decisão de promoção
- CP26: LOCAL GREEN, PRODUÇÃO NÃO HOMOLOGADA. Precisa da aprovação de release/backup/rollback, deploy seguro da mitigação dashboard, prova de túnel SSH ponta a ponta e resposta natural real Discord/E2E.
- CP27: BLOCKED por offsite/restore, integridade da árvore e runtime SHA divergente. Nenhum `git add .`, commit em massa, push ou deploy foi executado nesta retomada.
- CP28: LEDGER LOCAL GREEN, integração Core/ACL/correlations/receipts E2E pendente. Não considerar CP28 completo.
- CP29–CP31: permanecem pendentes de integrações e certificação física. Não alegar conclusão por teste unitário isolado.
