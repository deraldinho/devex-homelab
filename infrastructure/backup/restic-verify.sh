#!/bin/sh
set -eu

# DevEx HomeLab — Script de Verificação e Restauração de Teste (DR Smoke Test)

RESTIC_BIN="${RESTIC_BIN:-restic}"
TARGET_DIR="${1:-${VERIFY_TARGET_DIR:-/tmp/restic-restore-test}}"
NODE_NAME="${HOMELAB_NODE:-unknown-node}"

if [ -z "${RESTIC_REPOSITORY:-}" ]; then
  echo "ERRO: RESTIC_REPOSITORY não foi definido." >&2
  exit 1
fi

if [ -z "${RESTIC_PASSWORD_FILE:-}" ] && [ -z "${RESTIC_PASSWORD:-}" ]; then
  echo "ERRO: RESTIC_PASSWORD_FILE ou RESTIC_PASSWORD deve ser configurado." >&2
  exit 1
fi

echo "=== Iniciando Teste de Restauração (DR Verification) ==="
rm -rf "${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"

# 1. Obter ID do snapshot mais recente para este nó
LATEST_SNAPSHOT="$("${RESTIC_BIN}" snapshots --tag "node:${NODE_NAME}" --json | \
  python3 -c "import sys, json; data=json.load(sys.stdin); print(data[-1]['id'] if data else '')")"

if [ -z "${LATEST_SNAPSHOT}" ]; then
  echo "ERRO: Nenhum snapshot encontrado para node:${NODE_NAME}." >&2
  exit 2
fi

echo "Restaurando snapshot ${LATEST_SNAPSHOT} em ${TARGET_DIR}..."
"${RESTIC_BIN}" restore "${LATEST_SNAPSHOT}" --target "${TARGET_DIR}"

# 2. Verificar arquivos restaurados
FILE_COUNT="$(find "${TARGET_DIR}" -type f | wc -l)"
if [ "${FILE_COUNT}" -eq 0 ]; then
  echo "ERRO: Restauração completou, mas nenhum arquivo foi encontrado." >&2
  exit 3
fi

echo "Restauração bem-sucedida: ${FILE_COUNT} arquivos restaurados."

# 3. Se houver bancos SQLite, executar teste de integridade
for db in $(find "${TARGET_DIR}" -name "*.sqlite" -o -name "*.db" 2>/dev/null); do
  if command -v sqlite3 >/dev/null 2>&1; then
    echo "Verificando integridade SQLite: ${db}"
    CHECK_RESULT="$(sqlite3 "${db}" "PRAGMA integrity_check;")"
    if [ "${CHECK_RESULT}" != "ok" ]; then
      echo "ERRO: Falha na integridade do banco ${db}: ${CHECK_RESULT}" >&2
      exit 4
    fi
  fi
done

# 4. Limpeza
rm -rf "${TARGET_DIR}"

echo "=== Verificação de DR Concluída com Sucesso ==="
echo "DEVEX_HOMELAB_BACKUP_VERIFY_PASS"
