# CP-SENTRY-P4: isolated Linux acceptance test, read-only w.r.t. live Atlas services.
# Requires authorized SSH/scp and Python+cryptography on target.
param(
    [string]$HostAlias = "pentium",
    [switch]$Cleanup
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tag = ([guid]::NewGuid().ToString('N')).Substring(0, 10)
$remote = "/tmp/atlas-sentry-p4-canary-$tag"
$sshOptions = @('-o','BatchMode=yes','-o','ConnectTimeout=5',
                '-o','StrictHostKeyChecking=yes')
$modules = @(
    'state_model.py','health_supervisor_model.py','health_supervisor.py',
    'failure_memory.py','sentry_receipt_v2.py','sentry_receipt_relay.py',
    'sentry_incident_manifest.py'
)
& ssh @sshOptions $HostAlias "mkdir -p -m 0700 $remote/infrastructure/pentium/atlas/tests"
if ($LASTEXITCODE -ne 0) { throw "P4_CANARY_SANDBOX_CREATE_FAILED" }
foreach ($file in $modules) {
    $from = Join-Path $repo "infrastructure\pentium\atlas\$file"
    & scp @sshOptions $from "${HostAlias}:$remote/infrastructure/pentium/atlas/$file"
    if ($LASTEXITCODE -ne 0) { throw "P4_CANARY_COPY_FAILED" }
}
foreach ($file in @('test_sentry_receipt_relay.py','test_sentry_incident_manifest.py')) {
    $from = Join-Path $repo "infrastructure\pentium\atlas\tests\$file"
    & scp @sshOptions $from "${HostAlias}:$remote/infrastructure/pentium/atlas/tests/$file"
    if ($LASTEXITCODE -ne 0) { throw "P4_CANARY_TEST_COPY_FAILED" }
}
& ssh @sshOptions $HostAlias "cd $remote && python3 -m unittest infrastructure.pentium.atlas.tests.test_sentry_receipt_relay infrastructure.pentium.atlas.tests.test_sentry_incident_manifest -v"
if ($LASTEXITCODE -ne 0) { throw "P4_CANARY_LINUX_TESTS_FAILED" }
Write-Output "P4_CANARY_GREEN isolated_path=$remote"
if ($Cleanup) {
    # Delete only the freshly created, UUID-scoped directory.
    & ssh @sshOptions $HostAlias "rm -rf -- $remote"
    if ($LASTEXITCODE -ne 0) { throw "P4_CANARY_SANDBOX_CLEANUP_FAILED" }
    Write-Output "P4_CANARY_SANDBOX_CLEANED"
}
