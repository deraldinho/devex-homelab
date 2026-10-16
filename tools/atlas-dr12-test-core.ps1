# CP-DR12: entirely synthetic POSIX backup tests in a disposable core container.
# Does NOT mount production data, keys, runtime sockets, or repositories.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$dir = Join-Path $root 'infrastructure\backup'
$ssh = 'C:\Program Files\Git\usr\bin\ssh.exe'
$paths = @(
  (Join-Path $dir 'restic-backup.sh'),
  (Join-Path $dir 'sqlite_snapshot.py'),
  (Join-Path $dir 'tests\test_restic_backup_safe.py'),
  (Join-Path $dir 'tests\test_sqlite_snapshot.py')
)
foreach ($f in @($ssh) + $paths) {
  if (!(Test-Path -LiteralPath $f -PathType Leaf)) { throw 'Missing CP-DR12 fixture or SSH executable' }
}
$payload = @($paths | ForEach-Object {
  [Convert]::ToBase64String([IO.File]::ReadAllBytes($_))
})
$remote = @'
set -eu
docker run --rm -i --pull=never --network none --read-only \
  --tmpfs /tmp:rw,exec,nosuid,nodev,size=256m --cap-drop=ALL \
  --security-opt=no-new-privileges --pids-limit=64 --memory=384m \
  --cpus=1 --user 65534:65534 --entrypoint /bin/sh \
  devex/core-homelab-runner:2.337.0 -s <<'INNER_CPDR12'
set -eu
mkdir -p /tmp/work/infrastructure/backup/tests
printf '%s' '__BACKUP_B64__' | base64 -d > /tmp/work/infrastructure/backup/restic-backup.sh
printf '%s' '__SQLITE_B64__' | base64 -d > /tmp/work/infrastructure/backup/sqlite_snapshot.py
printf '%s' '__POSIX_TEST_B64__' | base64 -d > /tmp/work/infrastructure/backup/tests/test_restic_backup_safe.py
printf '%s' '__PY_TEST_B64__' | base64 -d > /tmp/work/infrastructure/backup/tests/test_sqlite_snapshot.py
cd /tmp/work
/bin/sh -n infrastructure/backup/restic-backup.sh
python3 -m unittest discover -s infrastructure/backup/tests -p 'test_restic_backup_safe.py' -v
python3 -m unittest discover -s infrastructure/backup/tests -p 'test_sqlite_snapshot.py' -v
echo CP_DR12_DISPOSABLE_TESTS_PASS
INNER_CPDR12
echo "CP_DR12_CONTAINER_EXIT:$?"
'@
$remote = $remote.Replace('__BACKUP_B64__',$payload[0]).Replace('__SQLITE_B64__',$payload[1]).Replace('__POSIX_TEST_B64__',$payload[2]).Replace('__PY_TEST_B64__',$payload[3]).Replace("`r",'')
$ErrorActionPreference = 'Continue'
$lines = @($remote | & $ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes core-auto bash -s 2>&1)
$sshExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
$target = Join-Path $root '.atlas\opencode\tmp'
New-Item -ItemType Directory -Force -Path $target | Out-Null
$log = Join-Path $target 'cp-dr12-disposable-tests.log'
$lines | ForEach-Object { [string]$_ } | Set-Content -LiteralPath $log -Encoding UTF8
$ok = $sshExit -eq 0 -and ($lines -match 'CP_DR12_DISPOSABLE_TESTS_PASS') -and ($lines -match 'CP_DR12_CONTAINER_EXIT:0')
[pscustomobject]@{
    scope='synthetic_disposable_core_only';
    status=$(if($ok){'validated'}else{'failed'});
    ssh_exit=$sshExit;log=$log;production_backup_restored=$false
} | ConvertTo-Json
if (!$ok) { exit 2 }
