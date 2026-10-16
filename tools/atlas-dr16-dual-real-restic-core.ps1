# CP-DR16: real Restic backup + dual SQLite stage restore, synthetic only.
# Runs in a disposable Core Docker container. No production volumes/secrets.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$dir=Join-Path $root 'infrastructure\backup'
$ssh='C:\Program Files\Git\usr\bin\ssh.exe'
$sqlite=(Join-Path $dir 'sqlite_snapshot.py')
$verifier=(Join-Path $dir 'verify_sqlite_restore.py')
foreach($f in @($ssh,$sqlite,$verifier)){if(!(Test-Path -LiteralPath $f -PathType Leaf)){throw 'DR16 test prerequisite missing'}}
$sqlite64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($sqlite))
$verifier64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($verifier))
$remote=@'
set -euo pipefail
TAG=atlas-dr16-dual-restic-temporary
if docker image inspect "$TAG" >/dev/null 2>&1; then echo "DR16_DENIED:tag_exists" >&2; exit 8; fi
trap 'docker image rm "$TAG" >/dev/null 2>&1 || true' EXIT
docker build --quiet --pull=false --network none --tag "$TAG" - <<'DOCKERFILE'
FROM devex/core-homelab-runner:2.337.0
COPY --from=restic/restic:0.17.3 /usr/bin/restic /usr/local/bin/restic
DOCKERFILE
docker run --rm --pull=never --network none --read-only \
 --tmpfs /tmp:rw,exec,nosuid,nodev,size=512m --cap-drop=ALL \
 --security-opt=no-new-privileges --pids-limit=64 --memory=512m --cpus=1 \
 --user 65534:65534 -e HOME=/tmp -e XDG_CACHE_HOME=/tmp/cache \
 -i --entrypoint /bin/bash "$TAG" -s <<'DR16_INNER'
set -euo pipefail
mkdir -p /tmp/scripts /tmp/live/atlas/runtime /tmp/hermes /tmp/repo /tmp/restore
STAGE=/tmp/staging/.restic-backup.ABCDEFGH
mkdir -p "$STAGE/sqlite-live" "$STAGE/sqlite-hermes"
printf '%s' '__SQLITE64__' | base64 -d > /tmp/scripts/sqlite_snapshot.py
printf '%s' '__VERIFIER64__' | base64 -d > /tmp/scripts/verify_sqlite_restore.py
python3 - <<'PY'
import sqlite3
from pathlib import Path
for name, value in (('/tmp/live/atlas/runtime/memory.sqlite3','LIVE-ATLAS'),('/tmp/hermes/state.db','HERMES')):
    c=sqlite3.connect(name)
    c.execute('CREATE TABLE sample(value TEXT)')
    c.execute('INSERT INTO sample VALUES (?)',(value,))
    c.commit()
    c.close()
Path('/tmp/live/atlas/cognitive_daemon.py').write_text('SYNTHETIC-CODE',encoding='utf-8')
PY
python3 /tmp/scripts/sqlite_snapshot.py prepare /tmp/live/atlas "$STAGE/sqlite-live"
python3 /tmp/scripts/sqlite_snapshot.py prepare /tmp/hermes "$STAGE/sqlite-hermes"
echo 'random-only-disposable-test-key' > /tmp/password
export RESTIC_REPOSITORY=/tmp/repo RESTIC_PASSWORD_FILE=/tmp/password
restic init >/dev/null
restic backup --exclude '*.db' --exclude '*.sqlite' --exclude '*.sqlite3' \
 --exclude '*-wal' --exclude '*-shm' \
 /tmp/live/atlas /tmp/hermes "$STAGE/sqlite-live" "$STAGE/sqlite-hermes" >/dev/null
restic restore latest --target /tmp/restore >/dev/null
test ! -e /tmp/restore/tmp/live/atlas/runtime/memory.sqlite3
test -f /tmp/restore/tmp/live/atlas/cognitive_daemon.py
python3 /tmp/scripts/verify_sqlite_restore.py /tmp/restore
python3 - <<'PY'
import sqlite3
from pathlib import Path
base=Path('/tmp/restore/.sqlite-verified-dr13')
for stage,path,expected in (('sqlite-live','runtime/memory.sqlite3','LIVE-ATLAS'),('sqlite-hermes','state.db','HERMES')):
    db=base/stage/path
    assert db.is_file(),str(db)
    with sqlite3.connect(db) as con:
        assert con.execute('PRAGMA integrity_check').fetchone()==('ok',)
        assert con.execute('SELECT value FROM sample').fetchone()[0]==expected
print('DR16_DUAL_SQLITE_REAL_RESTIC_PASS')
PY
DR16_INNER
echo "DR16_DISPOSABLE_CORE_EXIT:$?"
'@
$remote=$remote.Replace('__SQLITE64__',$sqlite64).Replace('__VERIFIER64__',$verifier64).Replace("`r",'')
$ErrorActionPreference='Continue'
$lines=@($remote | & $ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes core-auto bash -s 2>&1)
$sshExit=$LASTEXITCODE
$ErrorActionPreference='Stop'
$target=Join-Path $root '.atlas\opencode\tmp'
New-Item -ItemType Directory -Force -Path $target|Out-Null
$log=Join-Path $target 'cp-dr16-dual-real-restic.log'
$lines|ForEach-Object{[string]$_}|Set-Content -LiteralPath $log -Encoding UTF8
$joined=$lines -join "`n"
if($sshExit -ne 0 -or $joined -notmatch 'DR16_DUAL_SQLITE_REAL_RESTIC_PASS' -or $joined -notmatch 'DR16_DISPOSABLE_CORE_EXIT:0') {throw 'DR16 disposable real-Restic certification failed; inspect private log'}
[pscustomobject]@{checkpoint='CP-DR16';status='synthetic_engine_pass';core_docker_exit=$sshExit;production_restore=$false;evidence=$log}|ConvertTo-Json -Compress
