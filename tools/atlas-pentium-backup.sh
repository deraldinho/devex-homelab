#!/usr/bin/env bash
set -euo pipefail
umask 077
HOME_DIR="/home/deraldinho"
RESTIC="$HOME_DIR/.local/bin/restic"
REPOSITORY="$HOME_DIR/.local/share/atlas-restic/repository"
PASSWORD_FILE="$HOME_DIR/.config/atlas-backup/restic.password"
SOURCE_ATLAS="$HOME_DIR/atlas"
SOURCE_HERMES="$HOME_DIR/.hermes"
SOURCE_LIVE_ATLAS="$HOME_DIR/pentium-agent/atlas"
HELPER="$HOME_DIR/.local/share/atlas-backup/sqlite_snapshot.py"
STATE="$HOME_DIR/.local/state/atlas-backup"
mkdir -p "$STATE"
exec 9>"$STATE/backup.lock"
flock -n 9 || { echo "ATLAS_BACKUP_LOCKED"; exit 2; }
test -r "$PASSWORD_FILE" && test -f "$HELPER" && test -x "$RESTIC"
test -d "$REPOSITORY" && test -d "$SOURCE_ATLAS" && test -d "$SOURCE_HERMES" && test -d "$SOURCE_LIVE_ATLAS"
export RESTIC_REPOSITORY="$REPOSITORY" RESTIC_PASSWORD_FILE="$PASSWORD_FILE"
STAGING="$(mktemp -d "$STATE/.restic-backup.XXXXXXXX")"
cleanup() { rm -rf -- "$STAGING"; }
trap cleanup EXIT
mkdir "$STAGING/sqlite-hermes" "$STAGING/sqlite-live"
python3 "$HELPER" prepare "$SOURCE_HERMES" "$STAGING/sqlite-hermes"
python3 "$HELPER" prepare "$SOURCE_LIVE_ATLAS" "$STAGING/sqlite-live"
"$RESTIC" snapshots --json >/dev/null
"$RESTIC" backup --tag atlas-pentium --tag node:pentium \
  --exclude '*.db' --exclude '*.sqlite' --exclude '*.sqlite3' \
  --exclude '*-wal' --exclude '*-shm' --exclude '*-journal' \
  --exclude '*.sock' --exclude '.cache' \
  --exclude 'node_modules' --exclude '__pycache__' \
  "$SOURCE_ATLAS" "$SOURCE_HERMES" "$SOURCE_LIVE_ATLAS" "$STAGING/sqlite-hermes" "$STAGING/sqlite-live"
"$RESTIC" check --read-data-subset=2%
echo ATLAS_PENTIUM_BACKUP_OK
