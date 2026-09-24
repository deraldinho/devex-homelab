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

Para certificar que os backups continuam íntegros e restauráveis sem afetar a produção:

```bash
bash infrastructure/backup/restic-verify.sh /tmp/test-restore
```

Saída esperada:
```text
=== Iniciando Teste de Restauração (DR Verification) ===
Restauração bem-sucedida: N arquivos restaurados.
=== Verificação de DR Concluída com Sucesso ===
DEVEX_HOMELAB_BACKUP_VERIFY_PASS
```
