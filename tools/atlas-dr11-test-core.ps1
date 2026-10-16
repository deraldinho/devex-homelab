# Offline DR verifier contract tests in disposable core Linux container.
# Does not access any real Restic repositories, backup keys or host mounts.
[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$scriptFile = Join-Path $root "infrastructure\backup\restic-verify.sh"
$testFile = Join-Path $root "infrastructure\backup\tests\test_restic_verify_safe.py"
$restoreHelper = Join-Path $root "infrastructure\backup\verify_sqlite_restore.py"
$sqliteHelper = Join-Path $root "infrastructure\backup\sqlite_snapshot.py"
$ssh = "C:\Program Files\Git\usr\bin\ssh.exe"
foreach ($p in @($ssh, $scriptFile, $testFile, $restoreHelper, $sqliteHelper)) {
  if (!(Test-Path -LiteralPath $p -PathType Leaf)) { throw "Missing required file" }
}
$script64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($scriptFile))
$test64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($testFile))
$helper64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($restoreHelper))
$sqlite64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($sqliteHelper))
$remote = @'
set -eu
docker run --rm -i --pull=never --network none --read-only --tmpfs /tmp:rw,exec,nosuid,size=128m --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=64 --memory=256m --cpus=1 --user 65534:65534 --entrypoint /bin/bash devex/core-homelab-runner:2.337.0 -s <<'INNER_DR11'
set -eu
mkdir -p /tmp/work/infrastructure/backup/tests
printf '%s' '__VERIFY_B64__' | base64 -d > /tmp/work/infrastructure/backup/restic-verify.sh
printf '%s' '__HELPER_B64__' | base64 -d > /tmp/work/infrastructure/backup/verify_sqlite_restore.py
printf '%s' '__SQLITE_B64__' | base64 -d > /tmp/work/infrastructure/backup/sqlite_snapshot.py
printf '%s' '__TEST_B64__' | base64 -d > /tmp/work/infrastructure/backup/tests/test_restic_verify_safe.py
cd /tmp/work
/bin/sh -n infrastructure/backup/restic-verify.sh
python3 -m unittest discover -s infrastructure/backup/tests -p test_restic_verify_safe.py -v
echo DR11_ISOLATED_TESTS_PASS
INNER_DR11
echo "DISPOSABLE_DR11_CONTAINER_EXIT:$?"
'@
$remote = $remote.Replace("__VERIFY_B64__", $script64).Replace("__TEST_B64__", $test64).Replace("__HELPER_B64__", $helper64).Replace("__SQLITE_B64__", $sqlite64)
$ErrorActionPreference = "Continue"
$lines = @($remote | & $ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes core-auto bash -s 2>&1)
$exitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
$out = Join-Path $root ".atlas\opencode\tmp"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$log = Join-Path $out "cp-dr11-verifier-tests.log"
$lines | ForEach-Object { [string]$_ } | Set-Content -LiteralPath $log -Encoding UTF8
$ok = $exitCode -eq 0 -and ($lines -match "DR11_ISOLATED_TESTS_PASS") -and ($lines -match "DISPOSABLE_DR11_CONTAINER_EXIT:0")
[pscustomobject]@{ scope="synthetic_disposable_core_only"; status=$(if($ok){"validated"}else{"failed"}); ssh_exit=$exitCode; log=$log; real_backup_restored=$false } | ConvertTo-Json
if (!$ok) { exit 2 }
