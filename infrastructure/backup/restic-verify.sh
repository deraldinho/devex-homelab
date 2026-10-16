#!/bin/sh
set -eu

# DR verification only: restore into an owned, unique child of an EXISTING
# directory. The caller-supplied parent is NEVER removed or overwritten.
RESTIC_BIN="${RESTIC_BIN:-restic}"
PARENT_DIR="${1:-${VERIFY_TARGET_DIR:-/tmp}}"
NODE_NAME="${HOMELAB_NODE:-}"

deny() {
  echo "DR_VERIFY_DENIED: $1" >&2
  exit 2
}

[ -n "${RESTIC_REPOSITORY:-}" ] || deny "repository_missing"
[ -n "${RESTIC_PASSWORD_FILE:-}" ] || [ -n "${RESTIC_PASSWORD:-}" ] || deny "credential_reference_missing"
[ -n "$NODE_NAME" ] || deny "node_missing"
case "$NODE_NAME" in *[!a-zA-Z0-9_-]* ) deny "node_invalid" ;; esac
[ -d "$PARENT_DIR" ] || deny "existing_parent_required"
[ ! -L "$PARENT_DIR" ] || deny "symlink_parent_forbidden"
PARENT_REAL="$(cd "$PARENT_DIR" && pwd -P)" || deny "parent_unresolvable"
case "$PARENT_REAL" in
  /|/etc|/sys|/proc|/dev|/run) deny "unsafe_parent" ;;
esac

command -v "$RESTIC_BIN" >/dev/null 2>&1 || deny "restic_unavailable"
command -v python3 >/dev/null 2>&1 || deny "python3_unavailable"
command -v mktemp >/dev/null 2>&1 || deny "mktemp_unavailable"

RESTORE_DIR="$(mktemp -d "$PARENT_REAL/.restic-verify.XXXXXXXX")" || deny "scratch_creation_failed"
case "$RESTORE_DIR" in
  "$PARENT_REAL"/.restic-verify.*) ;;
  *) deny "scratch_outside_parent" ;;
esac

cleanup() {
  # The only path ever removed is our private mktemp-generated child.
  if [ -n "${RESTORE_DIR:-}" ] && [ -d "$RESTORE_DIR" ]; then
    rm -rf -- "$RESTORE_DIR"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

echo "=== Iniciando Teste de Restauração (DR Verification) ==="
# Restic snapshots may not be returned in chronological order.
# Reject malformed IDs/timestamps, and never use non-matching node snapshots.
if ! SNAPSHOT_JSON="$("$RESTIC_BIN" snapshots --tag "node:$NODE_NAME" --json)"; then
  deny "snapshot_listing_failed"
fi
if ! LATEST_SNAPSHOT="$(printf '%s\n' "$SNAPSHOT_JSON" | python3 -c '
import datetime
import json
import re
import sys
try:
    rows=json.load(sys.stdin)
    if not isinstance(rows,list):
        raise ValueError()
    valid=[]
    for s in rows:
        if not isinstance(s,dict):
            continue
        ident=s.get("id")
        stamp=s.get("time")
        tags=s.get("tags")
        if (not isinstance(ident,str) or not re.fullmatch("[0-9a-fA-F]{8,64}",ident)
                or not isinstance(stamp,str) or not isinstance(tags,list)
                or sys.argv[1] not in tags):
            continue
        dt=datetime.datetime.fromisoformat(stamp.replace("Z","+00:00"))
        if dt.tzinfo is None:
            continue
        valid.append((dt,ident))
    if not valid:
        raise ValueError()
    print(max(valid)[1])
except (ValueError, TypeError, KeyError, json.JSONDecodeError):
    sys.exit(2)
' "node:$NODE_NAME")"; then
  deny "no_valid_node_snapshot"
fi
[ -n "$LATEST_SNAPSHOT" ] || deny "no_valid_node_snapshot"

echo "Restaurando snapshot validado em diretório temporário isolado..."
"$RESTIC_BIN" restore "$LATEST_SNAPSHOT" --target "$RESTORE_DIR" || deny "restore_failed"

FILE_COUNT="$(find "$RESTORE_DIR" -type f | wc -l | tr -d '[:space:]')"
[ "$FILE_COUNT" -gt 0 ] || deny "empty_restore"

# Restored symlinks are not acceptable for this bounded integrity smoke.
if find "$RESTORE_DIR" -type l -print | grep -q .; then
  deny "restored_symlink_forbidden"
fi

# CP-DR13: verify *all* restored SQLite images, including the transient
# .restic-backup.XXXXXXXX/sqlite/manifest.json which Restic places under
# the ORIGINAL absolute source path inside the private restore directory.
# A snapshot with images but without a valid manifest must fail closed.
# The helper reconstructs SQLite files only within our private scratch tree.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
[ -f "$SCRIPT_DIR/verify_sqlite_restore.py" ] || deny "sqlite_verifier_missing"
[ -f "$SCRIPT_DIR/sqlite_snapshot.py" ] || deny "sqlite_snapshot_helper_missing"
if ! python3 "$SCRIPT_DIR/verify_sqlite_restore.py" "$RESTORE_DIR"; then
  deny "sqlite_transactional_verification_failed"
fi

# LEGACY PATH: no manifest found — check raw SQLite files for backwards compatibility.
DB_COUNT="$(find "$RESTORE_DIR" -type f \( -name '*.sqlite' -o -name '*.db' \) | wc -l | tr -d '[:space:]')"
if [ "$DB_COUNT" -gt 0 ]; then
  command -v sqlite3 >/dev/null 2>&1 || deny "sqlite3_unavailable"
  if ! find "$RESTORE_DIR" -type f \( -name '*.sqlite' -o -name '*.db' \) \
    -exec sh -c '
      for db do
        result="$(sqlite3 "$db" "PRAGMA integrity_check;")" || exit 1
        [ "$result" = ok ] || exit 1
      done
    ' sh {} +; then
    deny "sqlite_integrity_failure"
  fi
fi

echo "Restauração verificada: $FILE_COUNT arquivos; $DB_COUNT bancos SQLite."
echo "=== Verificação de DR Concluída com Sucesso ==="
echo "DEVEX_HOMELAB_BACKUP_VERIFY_PASS"
