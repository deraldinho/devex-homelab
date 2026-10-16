# Actual Restic engine on synthetic data inside disposable, no-mount core container.
# NOT a backup of the user's Atlas/Pentium/Core production state.
[CmdletBinding()]
param()
$ErrorActionPreference="Stop"
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$file=Join-Path $root 'infrastructure\backup\restic-verify.sh'
$ssh='C:\Program Files\Git\usr\bin\ssh.exe'
$verifyB64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($file))
$remote=@'
set -euo pipefail
TAG=atlas-dr11-real-engine-test:temporary
if docker image inspect "$TAG" >/dev/null 2>&1; then
  echo 'DENY: testing image tag already exists' >&2
  exit 8
fi
trap 'docker image rm "$TAG" >/dev/null 2>&1 || true' EXIT
docker build --quiet --pull=false --network none --tag "$TAG" - <<'DOCKERFILE'
FROM devex/core-homelab-runner:2.337.0
COPY --from=restic/restic:0.17.3 /usr/bin/restic /usr/local/bin/restic
DOCKERFILE
docker run --rm --pull=never --network none --read-only --tmpfs /tmp:rw,exec,nosuid,size=256m --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=64 --memory=384m --cpus=1 --user 65534:65534 -e HOME=/tmp -e XDG_CACHE_HOME=/tmp/cache -i --entrypoint /bin/bash "$TAG" -s <<'INNER'
set -euo pipefail
mkdir -p /tmp/source /tmp/repo /tmp/restore-parent /tmp/bin
python3 - <<'PY'
import os,secrets,sqlite3
with open('/tmp/key','w',encoding='utf-8') as f: f.write(secrets.token_hex(32))
with open('/tmp/source/sample.txt','w',encoding='utf-8') as f: f.write('synthetic Atlas DR fixture')
with sqlite3.connect('/tmp/source/atlas.sqlite') as db:
    db.execute('create table events (id integer primary key, state text)')
    db.execute('insert into events(state) values (?)',('TEST_ONLY',))
    db.commit()
PY
cat > /tmp/bin/sqlite3 <<'SQLITE_CLI'
#!/usr/bin/env python3
import sqlite3,sys
with sqlite3.connect(sys.argv[1]) as db:
    print(db.execute('PRAGMA integrity_check').fetchone()[0])
SQLITE_CLI
chmod +x /tmp/bin/sqlite3
export PATH="/tmp/bin:$PATH"
export RESTIC_REPOSITORY=/tmp/repo RESTIC_PASSWORD_FILE=/tmp/key HOMELAB_NODE=pentium
restic init >/dev/null
restic backup --tag node:pentium /tmp/source >/dev/null
printf '%s' '__VERIFY_B64__' | base64 -d > /tmp/restic-verify.sh
echo PRESERVE_ME > /tmp/restore-parent/sentinel.txt
/bin/sh /tmp/restic-verify.sh /tmp/restore-parent
test "$(cat /tmp/restore-parent/sentinel.txt)" = PRESERVE_ME
test "$(find /tmp/restore-parent -mindepth 1 -maxdepth 1 | wc -l)" -eq 1
echo REAL_RESTIC_ENGINE_RESTORE_PASS
INNER
echo "DISPOSABLE_REAL_RESTIC_EXIT:$?"
'@
$remote=$remote.Replace('__VERIFY_B64__',$verifyB64).Replace("`r",'')
$ErrorActionPreference='Continue'
$messages=@($remote | & $ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes core-auto bash -s 2>&1)
$sshExit=$LASTEXITCODE
$ErrorActionPreference='Stop'
$target=Join-Path $root '.atlas\opencode\tmp'
New-Item -ItemType Directory -Force -Path $target | Out-Null
$log=Join-Path $target 'cp-dr11-real-restic-engine.log'
$lines=@($messages | ForEach-Object {[string]$_})
$lines | Set-Content -LiteralPath $log -Encoding utf8
$ok=$sshExit -eq 0 -and ($lines -match 'REAL_RESTIC_ENGINE_RESTORE_PASS') -and ($lines -match 'DISPOSABLE_REAL_RESTIC_EXIT:0')
[pscustomobject]@{scope='real_restic_engine_synthetic_data_only';status=$(if($ok){'validated'}else{'failed'});ssh_exit=$sshExit;log=$log;production_backup_restored=$false} | ConvertTo-Json
if (!$ok) {exit 2}
