#Requires -Version 5.1
<#
CP-DR14: read-only physical host inventory. Sends Python source over SSH stdin,
no agent install, host file writes, elevated commands, secrets or service changes.
Reports are written ONLY under the current x99 project's .atlas temp directory.
#>
[CmdletBinding()]
param(
    [ValidateSet('all','core','pentium')][string]$Node='all'
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$source=Join-Path $root 'infrastructure\backup\dr14_preflight.py'
$ssh='C:\Program Files\Git\usr\bin\ssh.exe'
if (!(Test-Path -LiteralPath $source -PathType Leaf)) {throw 'Preflight script missing'}
if (!(Test-Path -LiteralPath $ssh -PathType Leaf)) {throw 'SSH client missing'}
$script64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($source))
$targetDir=Join-Path $root '.atlas\opencode\tmp'
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
$nodes=@(
    @{Name='core';Target='core-auto';Key=$null},
    @{Name='pentium';Target='deraldinho@100.107.230.78';Key=(Join-Path $env:USERPROFILE '.ssh\id_ed25519')}
)
foreach($hostSpec in $nodes) {
    if($Node -ne 'all' -and $Node -ne $hostSpec.Name){continue}
    $name=$hostSpec.Name
    $argsList=@('-o','BatchMode=yes','-o','ConnectTimeout=8',
               '-o','ConnectionAttempts=1','-o','StrictHostKeyChecking=yes')
    if($hostSpec.Key) {
        if (!(Test-Path -LiteralPath $hostSpec.Key -PathType Leaf)) {throw 'Authorized SSH key absent'}
        $argsList+=@('-o','IdentitiesOnly=yes','-i',$hostSpec.Key)
    }
    $argsList+=@($hostSpec.Target,('export PATH="$HOME/.local/bin:$PATH"; base64 -d | python3 - --node '+$name))
    $ErrorActionPreference='Continue'
    $lines=@($script64 | & $ssh @argsList 2>&1)
    $sshExit=$LASTEXITCODE
    $ErrorActionPreference='Stop'
    $payload=($lines | ForEach-Object{[string]$_}) -join "`n"
    # Exit 2 is the expected 'blocked' readiness result, not SSH failure.
    try {
        $report=ConvertFrom-Json -InputObject $payload -ErrorAction Stop
        if ($report.checkpoint -ne 'CP-DR14' -or $report.node -ne $name -or !$report.read_only) {
            throw 'Untrusted inventory response'
        }
        $file=Join-Path $targetDir ("cp-dr14-"+$name+"-preflight.json")
        $payload | Set-Content -LiteralPath $file -Encoding UTF8
        [pscustomobject]@{
            node=$name; status=$report.status; blockers=@($report.blockers)
            ssh_exit=$sshExit; evidence=$file; physical_restore_certified=$false
        } | ConvertTo-Json -Depth 5 -Compress
    } catch {
        [pscustomobject]@{
            node=$name; status='INVENTORY_UNAVAILABLE'; ssh_exit=$sshExit
            physical_restore_certified=$false
        } | ConvertTo-Json -Compress
    }
}
