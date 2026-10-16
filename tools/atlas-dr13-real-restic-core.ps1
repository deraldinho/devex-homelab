# CP-DR13: true Restic snapshot -> automated verifier -> SQLite reconstruction, synthetic only.
# No host filesystem mounts, keys, runner volumes, services or production repos.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$dir=Join-Path $root 'infrastructure\backup'
$ssh='C:\Program Files\Git\usr\bin\ssh.exe'
$paths=@((Join-Path $dir 'restic-backup.sh'),(Join-Path $dir 'sqlite_snapshot.py'),(Join-Path $dir 'restic-verify.sh'),(Join-Path $dir 'verify_sqlite_restore.py'))
foreach($f in @($ssh)+$paths){if(!(Test-Path -LiteralPath $f -PathType Leaf)){throw 'Missing test prerequisite'}}
$script64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($paths[0]))
$sqlite64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($paths[1]))
$verify64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($paths[2]))
$helper64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($paths[3]))
$remote=@'
set -euo pipefail
TAG=atlas-dr13-real-engine-test:temporary
if docker image inspect "$TAG" >/dev/null 2>&1; then
  echo 'DENY: temporary tag already exists' >&2
  exit 8
fi
trap 'docker image rm "$TAG" >/dev/null 2>&1 || true' EXIT
docker build --quiet --pull=false --network none --tag "$TAG" - <<'DOCKERFILE'
FROM devex/core-homelab-runner:2.337.0
COPY --from=restic/restic:0.17.3 /usr/bin/restic /usr/local/bin/restic
DOCKERFILE
docker run --rm --pull=never --network none --read-only \
 --tmpfs /tmp:rw,exec,nosuid,nodev,size=384m --cap-drop=ALL \
 --security-opt=no-new-privileges --pids-limit=64 --memory=512m --cpus=1 \
 --user 65534:65534 -e HOME=/tmp -e XDG_CACHE_HOME=/tmp/cache \
 -i --entrypoint /bin/bash "$TAG" -s <<'INNER_CPDR13'
set -euo pipefail
mkdir -p /tmp/source/nested /tmp/repo /tmp/state /tmp/staging /tmp/scripts /tmp/restore /tmp/restore-parent
printf '%s' '__BACKUP_B64__' | base64 -d > /tmp/scripts/restic-backup.sh
printf '%s' '__SQLITE_B64__' | base64 -d > /tmp/scripts/sqlite_snapshot.py
printf '%s' '__VERIFY_B64__' | base64 -d > /tmp/scripts/restic-verify.sh
printf '%s' '__HELPER_B64__' | base64 -d > /tmp/scripts/verify_sqlite_restore.py
python3 - <<'PY'
import sqlite3, secrets
from pathlib import Path
Path('/tmp/key').write_text(secrets.token_hex(32))
Path('/tmp/source/plain.txt').write_text('SYNTHETIC-PRESERVE')
db=sqlite3.connect('/tmp/source/nested/atlas live.sqlite')
db.execute('PRAGMA journal_mode=WAL')
db.execute('CREATE TABLE entries(value TEXT)')
db.execute("INSERT INTO entries VALUES ('TRANSACTIONAL-OK')")
db.commit()
db.close()
PY
export RESTIC_REPOSITORY=/tmp/repo RESTIC_PASSWORD_FILE=/tmp/key
export HOMELAB_NODE=pentium HOMELAB_STATE_DIR=/tmp/state BACKUP_STAGING_PARENT=/tmp/staging
restic init >/dev/null
/bin/sh /tmp/scripts/restic-backup.sh /tmp/source | tail -n 4
python3 - <<'PY'
import json
from pathlib import Path
s=json.loads(Path('/tmp/state/backup_status.json').read_text())
assert s['status']=='healthy' and len(s['snapshot_id']) >= 8,s
PY
# Verify that source SQLite was excluded while transactional images were included.
restic restore latest --tag node:pentium --target /tmp/restore >/dev/null
python3 - <<'PY'
from pathlib import Path
original=Path('/tmp/restore/tmp/source')
assert (original/'plain.txt').read_text()=='SYNTHETIC-PRESERVE'
assert not (original/'nested/atlas live.sqlite').exists(), 'RAW_DB_COPIED_INSTEAD_OF_SNAPSHOT'
manifests=list(Path('/tmp/restore/tmp/staging').rglob('manifest.json'))
assert len(manifests)==1, manifests
assert (manifests[0].parent/'databases/nested/atlas live.sqlite.sqlite-snapshot').exists()
PY
# Used only for this disposable image: sqlite3 CLI may not be installed.
cat > /tmp/scripts/sqlite3 <<'SQLITE_CLI'
#!/usr/bin/env python3
import sqlite3,sys
from pathlib import Path
target=Path(sys.argv[1])
assert "/restore-parent/.restic-verify." in str(target)
assert str(target).endswith("/nested/atlas live.sqlite")
conn=sqlite3.connect(target)
try:
    assert conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
    assert conn.execute("SELECT value FROM entries").fetchone()[0]=="TRANSACTIONAL-OK"
finally:
    conn.close()
Path('/tmp/dr13-verified-sqlite.marker').write_text('VERIFIED')
print("ok")
SQLITE_CLI
chmod +x /tmp/scripts/sqlite3
echo 'DO_NOT_REMOVE' > /tmp/restore-parent/sentinel.txt
export PATH="/tmp/scripts:$PATH"
/bin/sh /tmp/scripts/restic-verify.sh /tmp/restore-parent
test "$(cat /tmp/dr13-verified-sqlite.marker)" = VERIFIED
test "$(cat /tmp/restore-parent/sentinel.txt)" = DO_NOT_REMOVE
test "$(find /tmp/restore-parent -mindepth 1 -maxdepth 1 | wc -l)" -eq 1
echo DR13_REAL_RESTIC_VERIFIER_PASS
INNER_CPDR13
echo "CP_DR13_ENGINE_CONTAINER_EXIT:$?"
'@
$remote=$remote.Replace('__BACKUP_B64__',$script64).Replace('__SQLITE_B64__',$sqlite64).Replace('__VERIFY_B64__',$verify64).Replace('__HELPER_B64__',$helper64).Replace("`r",'')
$ErrorActionPreference='Continue'
$lines=@($remote | & $ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes core-auto bash -s 2>&1)
$sshExit=$LASTEXITCODE
$ErrorActionPreference='Stop'
$target=Join-Path $root '.atlas\opencode\tmp'
New-Item -ItemType Directory -Force -Path $target|Out-Null
$log=Join-Path $target 'cp-dr13-real-restic-engine.log'
$lines|ForEach-Object{[string]$_}|Set-Content -LiteralPath $log -Encoding UTF8
$ok=$sshExit -eq 0 -and ($lines -match 'DR13_REAL_RESTIC_VERIFIER_PASS') -and ($lines -match 'CP_DR13_ENGINE_CONTAINER_EXIT:0')
[pscustomobject]@{scope='real_restic_engine_synthetic_data_only';status=$(if($ok){'validated'}else{'failed'});ssh_exit=$sshExit;log=$log;production_backup_restored=$false}|ConvertTo-Json
if(!$ok){exit 2}
