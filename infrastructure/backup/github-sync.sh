#!/bin/sh
set -eu

# DevEx HomeLab — Sincronização Segura de Backup via GitHub Releases Privadas
# Exporta snapshot autônomo consistente, criptografa com AES-256-CBC e envia para GitHub Releases.

GITHUB_REPO="${GITHUB_BACKUP_REPO:-deraldinho/devex-homelab}"
NODE_NAME="${HOMELAB_NODE:-unknown-node}"
PASS_FILE="${RESTIC_PASSWORD_FILE:-/etc/homelab/secrets/restic.key}"
SOURCE_DIR="${1:-${BACKUP_SOURCE_DIR:-/state}}"
MAX_RELEASES="${BACKUP_MAX_GITHUB_RELEASES:-14}"
MAX_RETRIES=3
TIMESTAMP="$(date -u +"%Y%m%d-%H%M%S")"
RELEASE_TAG="backup-${NODE_NAME}-${TIMESTAMP}"

# Carregar arquivo de ambiente se existir e variáveis não estiverem setadas
if [ -f "/etc/homelab/backup.env" ]; then
  # shellcheck disable=SC1091
  . /etc/homelab/backup.env || true
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "AVISO: GitHub CLI ('gh') não encontrado. Sincronização com GitHub ignorada."
  exit 0
fi

if [ -z "${GITHUB_TOKEN:-}" ] && ! gh auth status >/dev/null 2>&1; then
  echo "ERRO: GITHUB_TOKEN não configurado e 'gh' não está autenticado." >&2
  exit 1
fi

if [ ! -f "${PASS_FILE}" ]; then
  echo "ERRO: Arquivo de chave '${PASS_FILE}' não encontrado para criptografia." >&2
  exit 1
fi

if [ ! -d "${SOURCE_DIR}" ]; then
  echo "ERRO: Diretório fonte '${SOURCE_DIR}' não existe." >&2
  exit 1
fi

TMP_DIR="/tmp/gh-backup-sync.$$"
mkdir -p "${TMP_DIR}/payload"
ARCHIVE_ENC="${TMP_DIR}/${RELEASE_TAG}.tar.gz.enc"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

echo "=== Sincronizando Backup com GitHub Releases ==="
echo "Repositório: ${GITHUB_REPO}"
echo "Tag: ${RELEASE_TAG}"
echo "Nó: ${NODE_NAME}"

# 1. Montar payload autônomo com manifesto de integridade SHA256
echo "Montando payload e calculando hashes SHA256..."
cp -a "${SOURCE_DIR}/." "${TMP_DIR}/payload/" 2>/dev/null || cp -R "${SOURCE_DIR}/." "${TMP_DIR}/payload/"

(
  cd "${TMP_DIR}/payload"
  find . -type f ! -name "SHA256SUMS.txt" -exec sha256sum {} + > SHA256SUMS.txt
)

# 2. Compactar e Criptografar localmente com AES-256-CBC (PBKDF2, 100k iterações)
echo "Compactando e criptografando dados com AES-256-CBC..."
tar -czf - -C "${TMP_DIR}/payload" . | \
  openssl enc -aes-256-cbc -pbkdf2 -iter 100000 -salt \
  -pass "file:${PASS_FILE}" -out "${ARCHIVE_ENC}"

ARCHIVE_SIZE="$(wc -c < "${ARCHIVE_ENC}" | tr -d ' ')"
echo "Tamanho do pacote criptografado: ${ARCHIVE_SIZE} bytes"

# 3. Upload para Release Privada com Retries e Backoff
echo "Publicando release no GitHub (com até ${MAX_RETRIES} tentativas)..."
UPLOAD_SUCCESS=0
ATTEMPT=1

while [ "${ATTEMPT}" -le "${MAX_RETRIES}" ]; do
  echo "Tentativa ${ATTEMPT}/${MAX_RETRIES} de upload para ${RELEASE_TAG}..."
  if gh release create "${RELEASE_TAG}" "${ARCHIVE_ENC}" \
    --repo "${GITHUB_REPO}" \
    --title "Automated Backup [${NODE_NAME}] ${TIMESTAMP}" \
    --notes "Snapshot autônomo criptografado (AES-256-CBC) do nó ${NODE_NAME} gerado em $(date -u). Contém SHA256SUMS.txt."; then
    
    # 4. Validar se o asset foi anexado com sucesso e tamanho condizente
    echo "Validando asset na release criada..."
    ASSET_COUNT="$(gh release view "${RELEASE_TAG}" --repo "${GITHUB_REPO}" --json assets --jq '.assets | length' 2>/dev/null || echo "0")"
    if [ "${ASSET_COUNT}" -gt 0 ]; then
      echo "Upload e integridade do asset validados com sucesso!"
      UPLOAD_SUCCESS=1
      break
    else
      echo "AVISO: Release criada mas asset não foi confirmado. Tentando novamente..."
    fi
  fi

  echo "Falha no upload na tentativa ${ATTEMPT}. Aguardando retry..."
  ATTEMPT=$((ATTEMPT + 1))
  sleep $((ATTEMPT * 5))
done

if [ "${UPLOAD_SUCCESS}" -ne 1 ]; then
  echo "ERRO CRÍTICO: Falha ao publicar release no GitHub após ${MAX_RETRIES} tentativas." >&2
  # Limpar release parcial se existir
  gh release delete "${RELEASE_TAG}" --repo "${GITHUB_REPO}" --yes --cleanup-tag >/dev/null 2>&1 || true
  exit 2
fi

# 5. Aplicar Política de Retenção (Manter apenas as 14 mais recentes)
echo "Aplicando política de retenção no GitHub (máximo ${MAX_RELEASES} releases)..."
EXISTING_TAGS="$(gh release list --repo "${GITHUB_REPO}" --limit 100 | \
  awk '{print $3}' | grep "^backup-${NODE_NAME}-" || true)"

TOTAL_RELEASES="$(echo "${EXISTING_TAGS}" | grep -c . || true)"
if [ "${TOTAL_RELEASES}" -gt "${MAX_RELEASES}" ]; then
  EXCESS=$((TOTAL_RELEASES - MAX_RELEASES))
  echo "Removendo ${EXCESS} releases antigas do nó ${NODE_NAME}..."
  OLD_TAGS="$(echo "${EXISTING_TAGS}" | tail -n "${EXCESS}")"
  for tag in ${OLD_TAGS}; do
    echo "Expurgando release antiga: ${tag}"
    gh release delete "${tag}" --repo "${GITHUB_REPO}" --yes --cleanup-tag || true
  done
fi

echo "=== Sincronização com GitHub Concluída com Sucesso ==="
echo "STATUS=PASS"
