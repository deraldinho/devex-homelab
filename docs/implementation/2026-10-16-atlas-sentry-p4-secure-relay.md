# Atlas — CP-SENTRY-P4: relay isolado, índice assinado e canary Linux

**Data:** 16/10/2026
**Estado do checkpoint de desenvolvimento:** GREEN (código, testes e canary isolado).
**Estado do deploy nos serviços do Pentium:** HOLD — não confundir com release.
**Base:** P0 `8cc77ad`, P1 `efc7ba8`, P2 `4b0684d`, P3 `66819e3`.

## Invariantes entregues

### 1. Transportar sem compartilhar chaves nem SQLite

- Um **relay Linux AF_UNIX** recebe no máximo 2 KiB por conexão.
- O servidor obtém a identidade do peer pelo kernel (`SO_PEERCRED`,
  não por parâmetro JSON), rejeita UID diferente do explicitamente aprovado.
- O cliente verifica que o socket é realmente um socket Unix, não symlink;
  confere UID de proprietário e GID esperado antes de enviar.
- O servidor confere a assinatura **Ed25519 de executor**, host pentium,
  status success, operação limitada (`start_service`, `restart_service`),
  ID de ação/incidente e janela temporal de cinco minutos. Só então
  grava o recibo; não tem chave privada do executor.
- O health supervisor continua assinando com sua chave privada
  independente, apenas após avaliação real HEALTHY. O relay e o supervisor
  devem ser executados sob o principal de saúde, distinto do executor.
- Fábrica em modo `ATLAS_SENTRY_V2_TRANSPORT=unix` **não abre o
  FailureMemory SQLite pelo executor**: ele lê a projeção
  `ReadOnlyIncidentManifest` assinada pelo supervisor e protegida por
  owner UID, group GID, ED25519 e TTL 120s. Depois de recuperação, a
  publicação de índice sem incidentes revoga a possibilidade de emitir
  novo recibo sobre o incidente antigo.
- A projeção contém apenas incident_id, component, opened_at e metadados
  técnicos mínimos, nunca prompts, segredos, respostas LLM ou lições.

### 2. Retenção, replay, rotação e falha fechada

- `RotatingReceiptJournal` suporta no máximo 256 registros por segmento
  (64 por padrão) e até 12 arquivos de histórico (4 por padrão).
- Deduplicação de receipt_id persiste através de reinicialização e rotação;
  se conteúdo diferente reutilizar o mesmo ID, há recusa.
- Segmentos de arquivo expirados há mais de **48 horas** podem ser
  descartados por inteiro na rotação. Recibos ainda vivos não são apagados
  para liberar espaço: quando a capacidade atinge o limite, novos
  recibos são negados e o operador recebe erro observável.
- JSONL recebe fsync, tamanho limitado, arquivo regular não symlink,
  modo 0600, diretório com proprietário e modo apropriados. O servidor
  é escritor único por journal.
- Chaves públicas aceitam bundle `version=1` com até 3 IDs por papel,
  arquivo próprio 0600 e PEMs com owner/modo seguros. Rotação segura:
  carregar IDs velho + novo, trocar signer, depois revogar ID velho
  apenas quando evidências pendentes expirarem; reiniciar os serviços
  de maneira controlada.
- `relay-status.json` contém exclusivamente contadores
  `accepted`, `duplicates`, `denied` e `schema_version`,
  escrito atomicamente, sem dados de usuários ou credenciais.
- Não há retry automático de comando de serviço por erro de socket.
  Nenhum resultado de LLM pode criar assinatura ou contornar ACL.

### 3. Código

| Área | Arquivos |
| --- | --- |
| Relay AF_UNIX, UID, journal/retention/status | `infrastructure/pentium/atlas/sentry_receipt_relay.py` |
| Índice de incidentes health-signed | `infrastructure/pentium/atlas/sentry_incident_manifest.py` |
| Emissores Ed25519 e factories opt-in | `infrastructure/pentium/atlas/sentry_receipt_v2.py` |
| Executar relay isolado | `tools/atlas_sentry_v2_relay.py` |
| Publicação de índice após observaçao | `infrastructure/pentium/atlas/health_supervisor_daemon.py` |
| Executor sem SQLite write no modo Unix | `infrastructure/pentium/atlas/cognitive_daemon.py` |
| Testes unitários/canary | `tests/test_sentry_receipt_relay.py`, `tests/test_sentry_incident_manifest.py`, `tests/test_sentry_p4_canary.py`, `tests/test_sentry_p4_factory.py` |
| Template operacional não instalado | `infrastructure/pentium/atlas/systemd-system/` |

## Ativação de referência — somente após homologação operacional

Três identidades lógicas devem existir: executor/cognitive (somente
chave privada do executor), saúde (somente chave privada health e
FailureMemory), e verificador (somente chaves públicas para ingerir
lições). Neste estágio relay e health podem operar no mesmo UID de
saúde para que o arquivo JSONL 0600 não exija permissão de escrita
compartilhada. **Executor nunca recebe acesso de escrita ao journal
ou ao banco SQLite de saúde**.

Os templates de systemd pressupõem um principal `atlas-sentry-health`,
um grupo suplementar `atlas-sentry-relay` e um diretório de
código definido pelo operador. Não fazem criação de usuários nem
instalação automática. Antes de habilitar, auditar:

1. `getent passwd atlas-sentry-health`,
   `getent group atlas-sentry-relay`, `id deraldinho`;
   confirmar dois UIDs realmente distintos.
2. Criar diretório do socket com owner saúde e grupo compartilhado
   (`0750`), socket `0660`; executor pertence ao grupo de socket.
   Diretório de dados de saúde `0700`. A chave privada health não
   pode ser lida pelo executor e vice-versa.
3. Provisionar **duas** chaves ED25519 em contas diferentes com
   `python -m tools.atlas_sentry_v2_keys`, fora de Git.
   Instalar versões compatíveis de Python e cryptography no runtime.
4. Habilitar relay somente depois do trust bundle revisado
   (`ATLAS_SENTRY_V2_RELAY_ENABLED=1`). Em
   `ATLAS_SENTRY_V2_RELAY_ALLOWED_UID` usar o UID executor real.
   `build_relay` recusa UID de executor igual ao seu próprio UID.
5. Health `ATLAS_SENTRY_HEALTH_SHADOW=1`,
   `ATLAS_SENTRY_V2_HEALTH_ENABLED=1`,
   `ATLAS_SENTRY_V2_TRANSPORT=unix`,
   `ATLAS_SENTRY_V2_INCIDENT_MANIFEST_FILE`,
   `ATLAS_SENTRY_V2_RELAY_ACTION_JOURNAL`,
   `ATLAS_SENTRY_V2_HEALTH_PROBE_JOURNAL`,
   `ATLAS_SENTRY_V2_RELAY_GROUP_GID` e paths/key IDs.
6. Executor `ATLAS_SENTRY_V2_EXECUTOR_ENABLED=1`,
   `ATLAS_SENTRY_V2_TRANSPORT=unix`,
   `ATLAS_SENTRY_V2_RELAY_SOCKET`,
   `ATLAS_SENTRY_V2_INCIDENT_MANIFEST_FILE`,
   `ATLAS_SENTRY_V2_HEALTH_UID`,
   `ATLAS_SENTRY_V2_RELAY_GROUP_GID`, health public PEM,
   key IDs e executor private PEM.
7. Inicializar relay e supervisor em canary e testar 1 falha
   **não destrutiva** e a recuperação em duas sondas independentes,
   sem ligar mecanismo de auto-reparo. Verificar assinaturas, contador
   de mensagens aceitas/negadas, capacidade do journal e logs.
8. Depois, testar rollback retirando flags, parando o relay,
   preservando journals, chaves e SQLite para auditoria. Para rotação,
   carregar ambas as chaves públicas antes da troca e não revogar
   antes da retenção definida.

### Verificação realizada no Pentium, somente sandbox

Via SSH BatchMode, foi confirmado diretamente em 16/10/2026:
- OS Linux; Python **3.14.4**; `cryptography` **46.0.5**;
- Usuário remoto `deraldinho` UID 1000;
- `atlas-cognitive.service` ativo na user session;
- `atlas-health-supervisor.service` **inativo**;
- As contas `atlas-sentry-health` e grupo
  `atlas-sentry-relay` **não existem** (`getent` sem retorno).

O código e dois arquivos de testes P4 foram copiados temporariamente
para um diretório próprio `/tmp/atlas-sentry-p4-canary-*`, com
permissão `0700`, sem substituir o checkout do Pentium e **sem
reiniciar serviço algum**.

Resultados finais no Linux real: **19/19 testes OK, zero skipped**,
incluindo duas conexões reais AF_UNIX com SO_PEERCRED: UID correto
aceito, UID esperado diferente negado, armazenamento e recuperação
de journal, assinatura Ed25519, índice assinado, prova falsa e
retorno de erro. Exemplo de sandbox
`/tmp/atlas-sentry-p4-canary-0ea9a1da11`.

**Limitação:** o canary Linux usou a mesma conta não privilegiada
para servidor e cliente, manipulando o UID permitido para testar
a recusa pelo kernel. Não é equivalente a homologação entre contas
de serviço distintas em produção, que permanece PENDING.

### Verificação no x99

- Canary reproduzível do x99, sem modificar serviços de produção:
  `powershell -NoProfile -ExecutionPolicy Bypass -File tools/atlas_sentry_p4_linux_canary.ps1 -Cleanup`.
  A opção Cleanup remove exclusivamente o diretório temporário criado
  nessa invocação. O teste exige SSH BatchMode previamente autenticado.
- Testes P4 focados: 28 testes, 3 skips de SO_PEERCRED/symlink
  no Windows; o canary Linux executa esses casos sem skips.
- O relay publica somente contadores técnicos de recebimento/negação,
  incluindo rejeições de UID pelo kernel, quando o path de status é configurado.
- Suíte Atlas final após hardening e rotação: **1393 passed,
  8 skipped, 217 subtests passed em 37.14s**, exit code 0.
- Testes P4 focados após último ciclo: **28 executados,
  3 skipped** no Windows; nenhum skip no canary Linux.

## Release gates ainda abertos (não declarar produção 100%)

- Criar e homologar **principais de sistema** distintos. O runtime
  atual do Pentium não tem atlas-sentry-health nem grupo compartilhado.
- Migrar o supervisor de saúde (atualmente inativo na sessão do usuário)
  para identidade de serviço apta a obter sondas reais systemd/funcionais,
  sem perder visibilidade dos componentes da sessão de usuário.
- Revisar e executar nova estratégia de deploy/backup e rollback
  dos serviços em produção; este checkpoint não alterou essas unidades.
- Submeter operações não destrutivas reais sob esses UIDs, verificar
  end-to-end de diferentes processos e rotação em ambos os signers.
- Publicar métricas no painel e alertas operacionais, se necessário.

**Decisão de deploy: HOLD.** O P4 no código e canary isolado foi
implementado, mas a infraestrutura de principals e um probe real
entre serviços isolados ainda não foi homologada. Isso não autoriza
ligar autonomia corretiva em produção.
