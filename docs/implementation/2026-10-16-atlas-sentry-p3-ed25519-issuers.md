# Atlas — CP-SENTRY-P3: recibos de execução e saúde via Ed25519

Data: **2026-10-16**. Estado: **IMPLEMENTADO/TDD no x99 — DEPLOY PENTIUM HOLD**.
Base: P0 `8cc77ad`, P1 `efc7ba8`, P2 `4b0684d`.

## Objetivo

Conectar as fontes *reais* de eventos tipados às assinaturas independentes,
sem expor capacidade de assinatura à LLM ou usar o texto autodeclarado
pelo agente como prova de execução.

Há uma restrição importante: este é o caminho **v2 Ed25519** para
emissores, separado da verificação HMAC v1 mantida para testes anteriores.
O esquema versionado não mistura assinaturas. A validação v2 usa apenas
**chaves públicas** e, portanto, não consegue forjar recibos.

## Fluxo implementado

1. `MultiHostCapabilityExecutor` continua aplicando suas permissões,
   target allowlist e confirmação humana pelas políticas existentes. Após
   o *resultado real* de comando bem-sucedido (não um texto LLM), chama
   `on_command_succeeded(capability, arguments, result)` se configurado.
2. `ExecutorReceiptSink` procura um incidente realmente OPEN na base
   `FailureMemory`, faz correlação por componente e instante, gera
   `action_id` próprio, assina o fato com chave Ed25519 do executor e
   registra JSONL em `sentry-v2-actions.jsonl`.
3. `HealthSupervisorOwner.run_once` constrói o snapshot com sondas de
   processo, funcionalidade, frescor e dependência como antes. Se um
   `recovery_receipt_sink` estiver configurado, o `HealthReceiptSink`
   verifica a assinatura pública da ação e só assina uma evidência
   própria quando o **componente foi classificado HEALTHY** depois da
   execução. A referência nova e única é agregada ao snapshot publicado
   e observado pelo `FailureMemory`.
4. A segunda verificação HEALTHY posterior produz um segundo recibo
   do **mesmo** `action_id`, com `evidence_ref` diferente. Caso não
   exista ação assinada, não há atestado de reparo.
5. `Ed25519RecoveryVerifier` confere assinaturas das duas identidades,
   key IDs e role, mesmo incidente/ação/componente/host, ordem temporal,
   frescor, resultado de executor autorizado e a presença das duas
   `evidence_refs` na recuperação persistida.
6. `learn_from_ed25519_recovery(...)` só persiste lição após verificar
   novamente os três recibos sobre a recuperação armazenada. O conteúdo
   permanece `evidence_only`; nenhuma ferramenta é acionada pelo Sentry.
7. O registro de um comando bem-sucedido **não prova** saúde; a verificação
   funcional anterior do executor continua independente dos dois ciclos
   posteriores do supervisor. Falha no subsistema de recibos não impede
   publicação normal do health snapshot nem modifica o resultado do
   managed control.

## Escopo preciso de execução

O caminho foi conectado ao factory real `CognitiveDaemon.build_owner`
para `MultiHostCapabilityExecutor` e ao
`health_supervisor_daemon.build_owner` para o supervisor. O processo
cognitivo pode usar chave privada da **conta do serviço executor**;
o supervisor requer chave privada de **outra conta**. Chaves privadas
nunca são passadas à LLM, registradas em prompts, parâmetros de ação
ou logs, nem incluídas neste commit.

A integração E2E foi testada no x99 com instâncias reais das classes
executor, supervisor e FailureMemory, **mas com sondas e ação local
simuladas**. Não equivale a uma recuperação real no Pentium.

No estágio atual, esta política atesta apenas `restart_service` e
`start_service`. Não emite evidências de controle para `reboot_host`,
container, outros hosts, pagamentos ou mutações não autorizadas.
Falhas de inferência Hermes continuam exigindo política diferente;
não são atestadas como curadas por um restart de serviço.

## Flags opt-in (nenhuma configurada em produção neste checkpoint)

- `ATLAS_SENTRY_HEALTH_SHADOW=1` para observar incidentes físicos.
- `ATLAS_SENTRY_V2_EXECUTOR_ENABLED=1` na unidade de execução.
- `ATLAS_SENTRY_V2_EXECUTOR_PRIVATE_KEY_FILE=<caminho absoluto PEM>`.
- `ATLAS_SENTRY_V2_EXECUTOR_KEY_ID=<id autorizado>`.
- `ATLAS_SENTRY_V2_HEALTH_ENABLED=1` no supervisor.
- `ATLAS_SENTRY_V2_HEALTH_PRIVATE_KEY_FILE=<caminho absoluto PEM>`.
- `ATLAS_SENTRY_V2_HEALTH_KEY_ID=<id autorizado>`.
- `ATLAS_SENTRY_V2_EXECUTOR_PUBLIC_KEY_FILE=<caminho absoluto PEM>`.
- `ATLAS_SENTRY_V2_EXECUTOR_KEY_ID=<mesmo id de executor>` no supervisor.

Os flags de inferência (`ATLAS_SENTRY_INFERENCE_SHADOW`) não são
necessários para assinar ações de serviço, mas a base dedicada
`failure-memory.sqlite3` deve existir como parte do runtime.

### Provisionamento seguro, ainda não executado nos hosts de produção

Em contas de serviço isoladas, instale a dependência
`cryptography` compatível com o Python do Pentium; não presuma sua
disponibilidade. Crie diretórios de destino sob administração local,
com ACL restritiva, **fora do repositório**, e execute uma vez:

```shell
python -m tools.atlas_sentry_v2_keys \
  --private /secure/executor/ed25519-private.pem \
  --public /secure/executor/ed25519-public.pem
```

Repita **em outra conta/principal** para o supervisor, com outro par
de chaves. O provisionador recusa sobrescrever arquivos existentes,
grava a chave privada com permissão `0600` em sistemas POSIX, exige
diretório pai protegido contra escrita de terceiros e não imprime
segredos.

O health supervisor deve ter acesso de LEITURA ao recibo de ação,
mas **nunca** à chave privada do executor. O modelo local de spool
usa `0600` por padrão; serviços em contas Unix distintas precisam
de uma ponte autenticada/ACL ou mecanismo de relay read-only
aprovado no processo de homologação. Sem esse transporte, a ativação
em contas distintas falhará em modo seguro, sem produzir lições.
É intencionalmente um **bloqueador de produção**, não uma autorização
para unificar as contas ou dar acesso da LLM às chaves.

O diretório de recibos é somente telemetria de procedência. Não deve
ser público, servir HTTP ou ser indexado como memória de LLM.
As assinaturas são verificadas mesmo quando o JSONL vem de disco
controlável pelo atacante.

### Rollback

Remover as flags do ambiente das duas unidades, reiniciar pelos
procedimentos de mudança autorizados, preservar `sentry-v2-*.jsonl`
e o SQLite para auditoria. Não publicar/sincronizar chaves privadas.
Não ativar ações automáticas por efeito do rollback. A integração
desabilitada não importa `cryptography` na inicialização dos
factories do supervisor/cognitivo.

## Arquivos adicionados/alterados

- NOVO `infrastructure/pentium/atlas/sentry_receipt_v2.py`
- NOVO `infrastructure/pentium/atlas/tests/test_sentry_receipt_v2.py`
- NOVO `infrastructure/pentium/atlas/tests/test_sentry_p3_runtime.py`
- NOVO `tools/atlas_sentry_v2_keys.py`
- MOD `infrastructure/pentium/atlas/multi_host_executor.py`
- MOD `infrastructure/pentium/atlas/health_supervisor_daemon.py`
- MOD `infrastructure/pentium/atlas/cognitive_daemon.py` (somente
  hunks P3 no commit; alterações anteriores de grafo preservadas na
  worktree sem staging).

## Evidência real / qualidade

TDD RED: módulo v2 ausente e falha de comparação de public keys
exercitados antes das correções; GREEN:
- `py -m unittest infrastructure.pentium.atlas.tests.test_sentry_receipt_v2 infrastructure.pentium.atlas.tests.test_sentry_p3_runtime -q`: **15 testes OK, 1 skipped** (symlinks indisponíveis no token Windows).
- `py -m pytest -q infrastructure/pentium/atlas/tests --disable-warnings --maxfail=1`: **1363 passed, 5 skipped, 213 subtests passed em 35.40s**, exit 0.

Os testes verificaram ausência de assinatura quando a ação falha,
ação em componente sem incidente, necessidade de dois ciclos saudáveis,
assinatura por roles separadas, adulteração de disco, key ID inválida,
necessidade de configuração opt-in, validação de PEM, geração de chaves
sem sobrescrever, replay, isolamento do verificador e aprendizagem
exclusivamente pós-recovery.

## Bloqueios remanescentes para 100% operacional

1. Implementar e homologar transporte seguro entre contas de serviço
   Unix diferentes, sem compartilhamento de chaves privadas, com ACL
   mínima, fila limitada, retenção e rotatividade de JSONL.
2. Confirmar chaves, owners, Python e `cryptography` no Pentium sem
   divulgar segredos; backup/restore do estado e permissões.
3. Canary com incidentes reais não destrutivos e recibos cruzados de
   execução e saúde; validar reboot, desconexão e relógios dos hosts.
4. Telemetria para `last_receipt_error`, alerta de spool cheio ou
   assinatura inválida; falhas devem ficar visíveis sem vazar secrets.
5. Relacionar `action_id` ao registro imutável de autorização/controle
   do executor para evitar atestados órfãos no caminho de produção.
6. Definir política de recuperação distinta para falhas Hermes/OpenCode,
   incluindo validadores semânticos e não apenas status de serviço.
7. Integração com serviço autenticado de ingestão de lições e separação
   de privilégios entre quem executa, quem observa e quem grava memória.

**Não houve deploy, restart de serviços, geração de segredos de produção
ou execução de correção automática neste checkpoint.**
