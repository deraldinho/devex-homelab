#!/bin/sh
set -eu

# DevEx HomeLab — Script de Backup Idempotente e Transacional com Restic (Issue #11)
# Suporta execução no host ou em container Docker.

RESTIC_BIN="${RESTIC_BIN:-restic}"
SOURCE_DIR="${1:-${BACKUP_SOURCE_DIR:-/data}}"
NODE_NAME="${HOMELAB_NODE:-unknown-node}"
STATE_DIR="${HOMELAB_STATE_DIR:-/state}"
STATUS_FILE="${STATE_DIR}/backup_status.json"
DISCORD_WEBHOOK="${DISCORD_BACKUP_WEBHOOK:-}"

notify_failure() {
  local err_msg="$1"
  echo "ERRO CRÍTICO NO BACKUP: ${err_msg}" >&2

  # Registrar falha no status local para o heartbeat
  if [ -d "${STATE_DIR}" ]; then
    cat <<EOF > "${STATUS_FILE}"
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "node": "${NODE_NAME}",
  "status": "failed",
  "error": "${err_msg}"
}
EOF
  fi

  # Notificar Discord se webhook estiver presente
  if [ -n "${DISCORD_WEBHOOK}" ] && command -v curl >/dev/null 2>&1; then
    curl -s -X POST -H "Content-Type: application/json" \
      -d "{\"content\": \"⚠️ **[ALERTA BACKUP HOMELAB]** Falha no backup do nó \`${NODE_NAME}\`: ${err_msg}\"}" \
      "${DISCORD_WEBHOOK}" || true
  fi
}

trap 'notify_failure "Processo abortado inesperadamente"' ERR 2>/dev/null || true

if [ ! -d "${SOURCE_DIR}" ]; then
  notify_failure "Diretório fonte '${SOURCE_DIR}' não existe."
  exit 1
fi

if [ -z "${RESTIC_REPOSITORY:-}" ]; then
  notify_failure "RESTIC_REPOSITORY não foi definido."
  exit 1
fi

if [ -z "${RESTIC_PASSWORD_FILE:-}" ] && [ -z "${RESTIC_PASSWORD:-}" ]; then
  notify_failure "RESTIC_PASSWORD_FILE ou RESTIC_PASSWORD deve ser configurado."
  exit 1
fi

echo "=== DevEx HomeLab Backup Iniciado ==="
echo "Node: ${NODE_NAME}"
echo "Source: ${SOURCE_DIR}"
echo "Repository: ${RESTIC_REPOSITORY}"

# 1. Liberar locks órfãos deixados por processos anteriores
echo "Verificando e liberando locks órfãos..."
"${RESTIC_BIN}" unlock >/dev/null 2>&1 || true

# 2. Inicializar repositório se ainda não existir
if ! "${RESTIC_BIN}" snapshots >/dev/null 2>&1; then
  echo "Repositório não inicializado. Executando 'restic init'..."
  "${RESTIC_BIN}" init
fi

# 3. Pré-hook transacional para bancos SQLite (Consistência ACID em repouso)
PRE_BACKUP_TMP="/tmp/homelab-sqlite-backup.$$"
mkdir -p "${PRE_BACKUP_TMP}"
CLEANUP_REQUIRED=0

if command -v sqlite3 >/dev/null 2>&1; then
  for db in $(find "${SOURCE_DIR}" -type f \( -name "*.sqlite" -o -name "*.db" \) 2>/dev/null); do
    rel_path="${db#$SOURCE_DIR/}"
    dest_dir="${PRE_BACKUP_TMP}/$(dirname "$rel_path")"
    mkdir -p "${dest_dir}"
    target_backup="${PRE_BACKUP_TMP}/${rel_path}"
    echo "Criando snapshot transacional SQLite: ${rel_path} -> ${target_backup}"
    sqlite3 "${db}" ".backup '${target_backup}'" || cp -f "${db}" "${target_backup}"
    CLEANUP_REQUIRED=1
  done
fi

# 4. Criar Snapshot via Restic
echo "Criando snapshot dos dados..."
BACKUP_TARGETS="${SOURCE_DIR}"
if [ "${CLEANUP_REQUIRED}" -eq 1 ]; then
  BACKUP_TARGETS="${SOURCE_DIR} ${PRE_BACKUP_TMP}"
fi

SNAPSHOT_OUTPUT="$("${RESTIC_BIN}" backup \
  --tag "homelab" \
  --tag "node:${NODE_NAME}" \
  --exclude ".cache" \
  --exclude "tmp" \
  --exclude "*.sock" \
  --exclude "*.sqlite-wal" \
  --exclude "*.sqlite-shm" \
  ${BACKUP_TARGETS} --json)"

SNAPSHOT_ID="$(echo "${SNAPSHOT_OUTPUT}" | python3 -c "import sys, json; lines=[json.loads(line) for line in sys.stdin if line.strip()]; snaps=[l.get('snapshot_id') for l in lines if l.get('message_type')=='summary']; print(snaps[0] if snaps else 'unknown')" 2>/dev/null || echo "completed")"

# Limpar staging transacional
if [ -d "${PRE_BACKUP_TMP}" ]; then
  rm -rf "${PRE_BACKUP_TMP}"
fi

# 5. Aplicar Política de Retenção
echo "Aplicando política de retenção..."
"${RESTIC_BIN}" forget \
  --tag "node:${NODE_NAME}" \
  --keep-daily 7 \
  --keep-weekly 4 \
  --keep-monthly 12 \
  --prune

# 6. Verificação de Integridade Bounded
echo "Verificando integridade do repositório..."
"${RESTIC_BIN}" check --read-data-subset=5%

# 7. Sincronização Opcional com GitHub Releases Privadas (Offsite Vault)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "${SCRIPT_DIR}/github-sync.sh" ]; then
  echo "Executando sincronização com GitHub Releases..."
  sh "${SCRIPT_DIR}/github-sync.sh" "${SOURCE_DIR}" || echo "AVISO: Falha na sincronização secundária com GitHub"
fi

# 8. Registrar Sucesso no Status para o Heartbeat
if [ -d "${STATE_DIR}" ]; then
  cat <<EOF > "${STATUS_FILE}"
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "node": "${NODE_NAME}",
  "status": "healthy",
  "snapshot_id": "${SNAPSHOT_ID}"
}
EOF
fi

echo "=== Backup Concluído com Sucesso ==="
echo "STATUS=PASS"

