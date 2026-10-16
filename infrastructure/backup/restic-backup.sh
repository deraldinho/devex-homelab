#!/bin/sh
set -eu

# CP-DR12: fail-closed Restic backup. NO auto-unlock or auto-init.
# A repository must be provisioned and tested by an approved operator.
RESTIC_BIN="${RESTIC_BIN:-restic}"
SOURCE_DIR="${1:-${BACKUP_SOURCE_DIR:-/data}}"
STATE_DIR="${HOMELAB_STATE_DIR:-/state}"
NODE_NAME="${HOMELAB_NODE:-}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
STAGE_ROOT=""
STATUS_FILE="${STATE_DIR}/backup_status.json"

case "$NODE_NAME" in ""|*[!a-zA-Z0-9_-]*) echo "BACKUP_DENIED: invalid_node" >&2; exit 2 ;; esac

write_status() {
  result="$1"
  snapshot="${2:-}"
  [ -d "$STATE_DIR" ] && [ -w "$STATE_DIR" ] || return 1
  status_temp="$(mktemp "$STATE_DIR/.backup_status.XXXXXXXX")" || return 1
  if ! cat > "$status_temp" <<EOF
{
  "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "node": "$NODE_NAME",
  "status": "$result",
  "snapshot_id": "$snapshot"
}
EOF
  then
    rm -f -- "$status_temp"
    return 1
  fi
  mv -f -- "$status_temp" "$STATUS_FILE"
}

finish() {
  result_code="$?"
  trap - 0
  if [ -n "$STAGE_ROOT" ] && [ -d "$STAGE_ROOT" ]; then
    # Only remove our private mktemp-created child, NEVER caller-supplied paths.
    rm -rf -- "$STAGE_ROOT" || result_code=1
  fi
  if [ "$result_code" -ne 0 ]; then
    write_status failed "" || true
    echo "BACKUP_FAILED" >&2
  fi
  exit "$result_code"
}
trap finish 0
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

[ -d "$SOURCE_DIR" ] && [ ! -L "$SOURCE_DIR" ] || { echo "BACKUP_DENIED: source_invalid" >&2; exit 2; }
SOURCE_DIR="$(CDPATH= cd -- "$SOURCE_DIR" && pwd -P)"
[ "$SOURCE_DIR" != "/" ] || { echo "BACKUP_DENIED: source_root" >&2; exit 2; }
[ -d "$STATE_DIR" ] && [ -w "$STATE_DIR" ] || { echo "BACKUP_DENIED: state_unwritable" >&2; exit 2; }
[ -n "${RESTIC_REPOSITORY:-}" ] || { echo "BACKUP_DENIED: repository_missing" >&2; exit 2; }
[ -n "${RESTIC_PASSWORD_FILE:-}" ] || [ -n "${RESTIC_PASSWORD:-}" ] || { echo "BACKUP_DENIED: credential_missing" >&2; exit 2; }
if [ -n "${RESTIC_PASSWORD_FILE:-}" ]; then
  [ -f "$RESTIC_PASSWORD_FILE" ] && [ -r "$RESTIC_PASSWORD_FILE" ] || { echo "BACKUP_DENIED: credential_file_unavailable" >&2; exit 2; }
fi
command -v "$RESTIC_BIN" >/dev/null 2>&1 || { echo "BACKUP_DENIED: restic_unavailable" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "BACKUP_DENIED: python_unavailable" >&2; exit 2; }
[ -f "$SCRIPT_DIR/sqlite_snapshot.py" ] || { echo "BACKUP_DENIED: sqlite_helper_missing" >&2; exit 2; }

# NEVER unlock automatically: a lock can belong to a valid concurrent writer.
# A failed snapshots request may mean auth/network/corruption, NOT an empty repo.
if ! "$RESTIC_BIN" snapshots --json >/dev/null; then
  echo "BACKUP_DENIED: repository_unavailable_or_not_initialized" >&2
  exit 2
fi

STAGING_PARENT="${BACKUP_STAGING_PARENT:-/tmp}"
[ -d "$STAGING_PARENT" ] && [ ! -L "$STAGING_PARENT" ] || { echo "BACKUP_DENIED: staging_parent_invalid" >&2; exit 2; }
STAGING_PARENT="$(CDPATH= cd -- "$STAGING_PARENT" && pwd -P)"
STAGE_ROOT="$(mktemp -d "$STAGING_PARENT/.restic-backup.XXXXXXXX")"
mkdir "$STAGE_ROOT/sqlite"

# SQLite Python .backup API creates consistent images, even with WAL writers.
# Any damaged, locked or unreadable database aborts ALL backup work.
python3 "$SCRIPT_DIR/sqlite_snapshot.py" prepare "$SOURCE_DIR" "$STAGE_ROOT/sqlite" >/dev/null
DB_COUNT="$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1],encoding="utf-8"))["databases"]))' "$STAGE_ROOT/sqlite/manifest.json")"
case "$DB_COUNT" in ""|*[!0-9]*) echo "BACKUP_DENIED: bad_staging_manifest" >&2; exit 2 ;; esac

if [ "$DB_COUNT" -gt 0 ]; then
  set -- "$SOURCE_DIR" "$STAGE_ROOT/sqlite"
else
  set -- "$SOURCE_DIR"
fi

# NEVER include a live raw SQLite file alongside its transactional image.
# The .sqlite-snapshot files and manifest in stage are included for restore.
OUTPUT="$("$RESTIC_BIN" backup \
  --tag "homelab" \
  --tag "node:${NODE_NAME}" \
  --exclude ".cache" \
  --exclude "*.sock" \
  --exclude "*.db" \
  --exclude "*.sqlite" \
  --exclude "*.sqlite3" \
  --exclude "*-wal" \
  --exclude "*-shm" \
  --exclude "*-journal" \
  --json "$@")"

SNAPSHOT_ID="$(printf '%s\n' "$OUTPUT" | python3 -c '
import json,re,sys
try:
    lines=[json.loads(line) for line in sys.stdin if line.strip()]
    matches=[x.get("snapshot_id") for x in lines
             if isinstance(x,dict) and x.get("message_type")=="summary"]
    if len(matches)!=1 or not isinstance(matches[0],str) or not re.fullmatch("[a-fA-F0-9]{8,64}",matches[0]):
        raise ValueError()
    print(matches[0])
except (ValueError,TypeError,json.JSONDecodeError):
    sys.exit(2)
')" || { echo "BACKUP_DENIED: missing_snapshot_id" >&2; exit 2; }

# Retention is applied ONLY after a completed, validated snapshot.
"$RESTIC_BIN" forget \
  --tag "node:${NODE_NAME}" \
  --keep-daily 7 \
  --keep-weekly 4 \
  --keep-monthly 12 \
  --prune
"$RESTIC_BIN" check --read-data-subset=5%

# Offsite raw-directory sync is intentionally NOT invoked: the legacy
# github-sync.sh does not consume this consistent snapshot or encrypted repo.
# Review offsite sync as a separate security checkpoint.
write_status healthy "$SNAPSHOT_ID"
echo "DEVEX_HOMELAB_BACKUP_PASS"
