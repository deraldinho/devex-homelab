# Runbook — Disaster Recovery & Backup com Restic (Issue #11)

## 1. Visão Geral

Este runbook define os procedimentos operacionais para backup e recuperação de desastres (DR) do **DevEx HomeLab**.
O sistema utiliza **Restic** para snapshots criptografados, desduplicados e imutáveis por tag de nó.

- **Pentium (`homelab.control`)**: Backup dos bancos SQLite do Atlas (com pré-hook transacional `.backup`), históricos de auditoria, chaves de autenticação de nós e estado de runtime.
- **Core (`homelab.compute`)**: Backup dos volumes de persistência de runners (`core-devex-homelab`, `core-l2jtoren`) e diretório `/state`.
- **Arquitetura Cruzada via Tailscale**: Para evitar ponto único de falha local, o Pentium envia seu repositório para o Core via SFTP/REST (`sftp:core:/var/backups/homelab/pentium`), e o Core envia para o storage secundário ou Pentium (`sftp:pentium:/var/backups/homelab/core`).
- **Política de Retenção**: 7 diários, 4 semanais, 12 mensais (`--keep-daily 7 --keep-weekly 4 --keep-monthly 12 --prune`).

---

## 2. Configuração e Agendamento no Host

### 2.1 Variáveis de Ambiente
Nenhum secret de criptografia é versionado no Git. No host (`/etc/homelab/backup.env`), configure:

```bash
RESTIC_REPOSITORY="sftp:core:/var/backups/homelab/pentium"
RESTIC_PASSWORD_FILE="/etc/homelab/secrets/restic.key"
HOMELAB_NODE="pentium"
HOMELAB_STATE_DIR="/state"
DISCORD_BACKUP_WEBHOOK="https://discord.com/api/webhooks/..." # opcional
```

### 2.1.1 Contrato do Compose (não ativado)

O `infrastructure/backup/Dockerfile` fixa o Restic 0.17.3 por digest e inclui Python, SQLite e curl exigidos pelos scripts. O Compose constrói essa imagem em vez de usar a imagem upstream sem dependências. Antes de usar, o operador deve fornecer explicitamente `RESTIC_REPOSITORY`, `HOMELAB_NODE`, `BACKUP_SOURCE_DIR`, `BACKUP_REPO_DIR`, `BACKUP_STATUS_DIR` e `RESTIC_PASSWORD_FILE` (arquivo existente, fora do Git). Os volumes de dados e segredo são somente leitura para os scripts; o contêiner não tem capabilities, portas nem acesso indiscriminado ao host. O diretório de status e repositório devem ter permissões compatíveis com UID 65534.

Em 2026-10-13, apenas o **build descartável** dessa imagem foi validado no `core`: Restic, Python, SQLite, curl e três scripts estavam presentes. **Não foi executado backup real, nem instalado timer**. O `github-sync.sh` exige um processo separado de revisão e configuração de `gh`/autenticação antes de alegar retenção offsite. Revisar também a lógica de backup SQLite e retenção antes de promoção.

### 2.2 Habilitar Agendamento Systemd Timer
```bash
sudo cp infrastructure/backup/systemd/homelab-backup.service /etc/systemd/system/
sudo cp infrastructure/backup/systemd/homelab-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now homelab-backup.timer
```


---

## 3. Operação Manual de Backup

Para executar um snapshot manual fora do cron/systemd:

```bash
# Execução via script idempotente
bash infrastructure/backup/restic-backup.sh /caminho/para/dados

# Ou via Docker Compose
docker compose -f infrastructure/backup/compose.yaml run --rm restic-backup
```

---

## 4. Procedimento de Recuperação de Desastre (Disaster Recovery)

### 4.1 Recuperação a partir de GitHub Release Privada (Recomendado)

Caso o host seja totalmente destruído e você precise restaurar diretamente do GitHub:

1. **Autenticar o GitHub CLI**:
   ```bash
   gh auth login
   ```
2. **Listar e identificar a release de backup desejada**:
   ```bash
   gh release list --repo deraldinho/devex-homelab
   ```
3. **Baixar o snapshot criptografado da release**:
   ```bash
   mkdir -p /tmp/restore-gh && cd /tmp/restore-gh
   gh release download <TAG_DA_RELEASE> --repo deraldinho/devex-homelab
   ```
4. **Descriptografar e descompactar os dados**:
   ```bash
   openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 -salt \
     -pass file:/etc/homelab/secrets/restic.key \
     -in <ARQUIVO_ENCRIPTADO>.tar.gz.enc | tar -xzf - -C /target/dir
   ```
5. **Verificar a integridade dos bancos SQLite restaurados**:
   ```bash
   sqlite3 /target/dir/atlas/runtime/atlas.sqlite "PRAGMA integrity_check;"
   ```

### 4.2 Recuperação do Pentium (`homelab.control`) via Restic


Se o disco ou host do Pentium for substituído ou reinstalado do zero:

1. **Reinstalar Ubuntu base** e configurar Tailscale com IP estático do homelab.
2. **Clonar repositório canônico**:
   ```bash
   git clone https://github.com/deraldinho/devex-homelab.git ~/DevEx-HomeLab
   ```
3. **Restaurar credenciais de backup**:
   Recupere a chave `restic.key` de armazenamento seguro secundário e salve em `/etc/homelab/secrets/restic.key`.
4. **Listar snapshots disponíveis para o Pentium**:
   ```bash
   restic -r /var/backups/homelab --password-file /etc/homelab/secrets/restic.key snapshots --tag node:pentium
   ```
5. **Restaurar o snapshot mais recente**:
   ```bash
   mkdir -p ~/pentium-agent
   restic -r /var/backups/homelab --password-file /etc/homelab/secrets/restic.key restore latest \
     --tag node:pentium \
     --target ~/pentium-agent
   ```
6. **Verificar integridade dos bancos SQLite restaurados**:
   ```bash
   sqlite3 ~/pentium-agent/atlas/runtime/atlas.sqlite "PRAGMA integrity_check;"
   sqlite3 ~/pentium-agent/atlas/runtime/presence.sqlite "PRAGMA integrity_check;"
   ```
7. **Reiniciar serviços de observabilidade**:
   ```bash
   systemctl --user restart pentium-heartbeat.service
   ```

---

### 4.2 Recuperação do Core (`homelab.compute`)

Se o host de computação sofrer perda total de storage:

1. **Reinstalar Docker e Compose** no nó Core.
2. **Restaurar volumes de CI e `/state`**:
   ```bash
   mkdir -p /state
   restic -r /var/backups/homelab --password-file /etc/homelab/secrets/restic.key restore latest \
     --tag node:core \
     --target /state
   ```
3. **Subir os runners de CI conteinerizados**:
   ```bash
   docker compose -f infrastructure/core/runners/compose.yaml up -d
   ```
4. **Validar status do runner no GitHub**:
   Verifique na aba *Actions > Runners* do GitHub se `core-devex-homelab` reconectou com status `Idle/Online`.

---

## 5. Teste Periódico de DR (Smoke Test)

**Estado físico em 2026-10-13: HOLD.** Inventário autenticado constatou `restic` ausente em `core` e `pentium`, `homelab-backup.timer` não instalado/ativado, e nenhum `/etc/homelab/backup.env` ou arquivo de chave Restic encontrado. Assim, **não existe restauração Restic real certificada**. Não marque a Issue #11 como concluída até validar uma rotina de backup + restauração contra snapshots reais, sem interromper Atlas ou runners.

O verificador agora **nunca apaga o diretório passado como argumento**: somente aceita diretório-pai existente que não seja symlink ou raiz, cria uma subpasta exclusiva `mktemp` e limpa apenas essa subpasta. Ordena snapshots por timestamp e filtra tag de nó, valida arquivos e checa SQLite; falhas não produzem marcador PASS. Os 13 testes de segurança foram aprovados em contêiner descartável com backend Restic sintético. Também houve um teste separado do **Restic 0.17.3 real**, inteiramente isolado no `core`, com dados e chave descartáveis: snapshot, restauração, `PRAGMA integrity_check` e preservação de arquivos existentes passaram. **Esse teste não restaura dados reais dos servidores e não certifica Backup/DR físico.** Execute o verificador com repositório real somente após provisionar e aprovar credenciais e destino.


Para certificar que os backups continuam íntegros e restauráveis sem afetar a produção:

```bash
# Argumento é um diretório-pai EXISTENTE; o script cria um filho único.
# Nunca use a raiz, diretório do sistema ou pasta de produção.
bash infrastructure/backup/restic-verify.sh /tmp
```

Saída esperada:
```text
=== Iniciando Teste de Restauração (DR Verification) ===
Restauração bem-sucedida: N arquivos restaurados.
=== Verificação de DR Concluída com Sucesso ===
DEVEX_HOMELAB_BACKUP_VERIFY_PASS
```


---

## 6. CP-DR12/13 — Backup SQLite transacional e restauração verificada (estado local)

**Certificação 2026-10-13: GREEN de engenharia em Core descartável, HOLD para dados reais.**

O `restic-backup.sh` não libera locks automaticamente nem executa `restic init` em resposta a erro de autenticação/repositório. Antes de salvar snapshot, usa `sqlite_snapshot.py` para gerar imagens consistentes de bancos `.db`, `.sqlite` e `.sqlite3` e o respectivo `manifest.json`. Os bancos ativos e seus arquivos WAL/SHM não entram no snapshot bruto. Falha de backup transacional aborta todo o processo. A restauração em `restic-verify.sh` usa um diretório-filho `mktemp`, nunca substitui o diretório-pai informado, e chama `verify_sqlite_restore.py` para reconstruir as imagens, conferir integridade e rejeitar caminhos/traversal, symlinks, imagens órfãs, mistura de arquivos SQLite vivos com imagens transacionais e manifests duplicados.

**Testes sem infraestrutura de produção:**
```powershell
cd C:\Users\deral\DevEx-HomeLab
py -m pytest -q infrastructure/backup/tests/test_verify_sqlite_restore.py
& .\tools\atlas-dr11-test-core.ps1
& .\tools\atlas-dr12-test-core.ps1
& .\tools\atlas-dr13-real-restic-core.ps1
& .\tools\atlas-dr11-build-core.ps1
py -m pytest --import-mode=importlib infrastructure/pentium/atlas/tests infrastructure/pentium/agent/tests infrastructure/backup/tests -q
```

Evidência: `docs/as-built/2026-10-13-atlas-dr13-restic-transactional-restore.md` e logs em `.atlas/opencode/tmp/cp-dr13-*.log`. A bateria completa local obteve **1137 passed, 24 skipped, 53 subtests passed**. A prova Restic real foi executada somente com banco e senha sintéticos, sem montar volumes, chaves, socket Docker ou paths de produção.

**Proibição de promoção automática:** não instalar timer nem configurar SFTP/offsite/secrets a partir desses testes. A Issue #11 permanece sem certificação operacional até serem autorizados e comprovados destino durável criptografado, controle de acesso, backup efetivo de Pentium/Core, restauração de dados reais isolada, integridade, retenção, cadência e plano de rollback.


---

## 7. CP-DR14 — Gate de prontidão física (2026-10-13)

**Situação operacional: BLOCKED nos dois hosts.** O diagnóstico read-only foi executado com sucesso via SSH autenticado a partir do x99 e está documentado em `docs/as-built/2026-10-13-atlas-dr14-physical-preflight.md`. Não houve `restic init`, backup de dados reais, unlock, mudança de credenciais, restauração produtiva, ativação de timer nem instalação de serviço.

```powershell
cd C:\Users\deral\DevEx-HomeLab
py -m pytest -q infrastructure/backup/tests/test_dr14_preflight.py infrastructure/backup/tests/test_dr14_deployment_contract.py
& .\tools\atlas-dr14-inventory.ps1 -Node all
```

Os relatórios de execução somente leitura ficam em `.atlas/opencode/tmp/cp-dr14-core-preflight.json` e `.atlas/opencode/tmp/cp-dr14-pentium-preflight.json`.

| Pré-requisito | Core | Pentium |
|---|---|---|
| SSH Tailscale, Python e Tailscale | OK | OK |
| Restic host | AUSENTE | AUSENTE |
| sqlite3 host | AUSENTE | OK |
| Arquivos aprovados de env e credencial | AUSENTES | AUSENTES |
| Timer instalado/ativado | NÃO | NÃO |
| Restore real + offsite | NÃO CERTIFICADO | NÃO CERTIFICADO |

**Contrato de segurança:** o arquivo `infrastructure/backup/backup.env.example` é apenas um template de placeholders — não copiá-lo automaticamente para `/etc/homelab/backup.env`. A unidade `homelab-backup.service` agora declara um `EnvironmentFile` **obrigatório**, mas **não foi instalada**. Escolher e autorizar o repositório, fonte e chave antes de qualquer `restic init`. Não habilitar timer sem ensaio de restore isolado e rollback.

A implantação baseada em Docker e a unidade systemd têm caminhos/credenciais distintos e precisam de um único contrato explícito por host. Em especial, a existência do volume `/repo` no contêiner não garante que `RESTIC_REPOSITORY` o utilize; valores de ambiente precisam ser checados pelo operador, sem publicação de segredos. O documento original nesta página contém metas arquiteturais históricas; as seções DR-12 a DR-14 e o registro `docs/status/atlas-checkpoints.md` prevalecem sobre instruções antigas que pressuponham implantação física já concluída.
