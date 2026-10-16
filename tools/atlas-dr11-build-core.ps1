# Validates the backup Dockerfile inside core without starting backup services.
[CmdletBinding()]
param()
$ErrorActionPreference="Stop"
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ctx=Join-Path $root '.atlas\opencode\tmp\dr11-build-context.tar.gz'
$source=Join-Path $root 'infrastructure\backup'
New-Item -ItemType Directory -Force -Path (Split-Path $ctx) | Out-Null
& tar.exe -czf $ctx -C $source Dockerfile restic-backup.sh restic-verify.sh sqlite_snapshot.py verify_sqlite_restore.py github-sync.sh
if($LASTEXITCODE -ne 0){throw 'Unable to produce disposable build context'}
$b64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($ctx))
$ssh='C:\Program Files\Git\usr\bin\ssh.exe'
$remote=@'
set -euo pipefail
TAG=atlas-dr11-packaging-test:temporary
if docker image inspect "$TAG" >/dev/null 2>&1; then echo 'DENY: existing temporary tag' >&2; exit 8; fi
trap 'docker image rm "$TAG" >/dev/null 2>&1 || true' EXIT
printf '%s' '__TAR_B64__' | base64 -d | docker build --pull=false --network default --tag "$TAG" -
docker run --rm --pull=never --network none --read-only --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=32 --memory=128m --cpus=0.5 --entrypoint /bin/sh "$TAG" -c '
set -eu
command -v restic
command -v python3
command -v sqlite3
command -v curl
test -f /scripts/restic-backup.sh
test -f /scripts/restic-verify.sh
test -f /scripts/sqlite_snapshot.py
test -f /scripts/verify_sqlite_restore.py
test -f /scripts/github-sync.sh
echo RESTIC_BACKUP_PACKAGING_PASS
'
echo "DISPOSABLE_PACKAGING_EXIT:$?"
'@
$remote=$remote.Replace('__TAR_B64__',$b64).Replace([string][char]13,'')
$ErrorActionPreference='Continue'
$msgs=@($remote | & $ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes core-auto bash -s 2>&1)
$exit=$LASTEXITCODE
$ErrorActionPreference='Stop'
$log=Join-Path (Split-Path $ctx) 'cp-dr11-packaging-build.log'
$lines=@($msgs|ForEach-Object{[string]$_})
$lines | Set-Content -LiteralPath $log -Encoding utf8
$ok=$exit -eq 0 -and ($lines -match 'RESTIC_BACKUP_PACKAGING_PASS') -and ($lines -match 'DISPOSABLE_PACKAGING_EXIT:0')
[pscustomobject]@{status=$(if($ok){'validated'}else{'failed'});scope='disposable_packaging_smoke_only';ssh_exit=$exit;log=$log;production_deployed=$false}|ConvertTo-Json
if(!$ok){exit 2}
