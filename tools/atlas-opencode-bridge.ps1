#Requires -Version 5.1
<#
.SYNOPSIS
  Bridge Atlas <-> OpenCode por arquivos, dentro de cada projeto.
.EXAMPLE
  .\tools\atlas-opencode-bridge.ps1 -Mode send -ProjectPath "C:\Users\deral\DevEx-HomeLab" -Task "Revisar CP-AA0, sem deploy."
.EXAMPLE
  .\tools\atlas-opencode-bridge.ps1 -Mode run -ProjectPath "C:\Users\deral\DevEx-HomeLab" -TaskId "20261013T011500Z-a1b2c3d4"
.EXAMPLE
  .\tools\atlas-opencode-bridge.ps1 -Mode read -ProjectPath "C:\Users\deral\DevEx-HomeLab" -TaskId "20261013T011500Z-a1b2c3d4"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("send", "run", "read", "list", "reconcile")]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,

    [string]$Task,
    [string]$TaskId,
    [ValidateRange(30, 900)]
    [int]$TimeoutSeconds = 900,
    [string]$ServerUrl = '',
    [string]$Model = '',
    [ValidateSet("api", "cli")]
    [string]$Transport = "api"
)
$ErrorActionPreference = "Stop"
$utf8 = New-Object System.Text.UTF8Encoding($false)
$root = [System.IO.Path]::GetFullPath($ProjectPath).TrimEnd("\")
if (-not (Test-Path -LiteralPath $root -PathType Container)) {
    throw "Projeto inexistente: $root"
}
$base = Join-Path $root ".atlas\opencode"
$inbox = Join-Path $base "inbox"
$outbox = Join-Path $base "outbox"
$tmp = Join-Path $base "tmp"
foreach ($directory in @($base, $inbox, $outbox, $tmp)) {
    if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
        [void][System.IO.Directory]::CreateDirectory($directory)
    }
}

function Save-AtomicUtf8 {
    param([string]$TargetPath, [string]$Text)
    $partial = Join-Path $tmp ([System.IO.Path]::GetFileName($TargetPath) + "." + [guid]::NewGuid().ToString("N") + ".partial")
    [System.IO.File]::WriteAllText($partial, $Text, $utf8)
    try {
        [System.IO.File]::Move($partial, $TargetPath)
    } finally {
        if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
    }
}

function Require-TaskId {
    if ($TaskId -notmatch '^\d{8}T\d{6}Z-[a-f0-9]{8}$') {
        throw "TaskId invalido: esperado yyyyMMddTHHmmssZ-xxxxxxxx"
    }
}

if ($Mode -eq "send") {
    if ([string]::IsNullOrWhiteSpace($Task)) { throw "-Task obrigatorio em -Mode send" }
    if ($Task.Length -gt 12000) { throw "Mensagem excede limite de 12000 caracteres" }
    $id = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ") + "-" + [guid]::NewGuid().ToString("N").Substring(0,8)
    $requestFile = Join-Path $inbox ($id + ".md")
    $reportRel = ".atlas/opencode/outbox/" + $id + ".md"
    $request = @"
# Pedido Atlas -> OpenCode
Task-Id: $id
Criado (UTC): $((Get-Date).ToUniversalTime().ToString("o"))
Pasta raiz do projeto: $root
Relatorio obrigatorio: $reportRel

## Tarefa
$Task

## Contrato de execucao
- Leia este pedido por completo e respeite as regras existentes do projeto.
- Execute sempre a partir da raiz deste projeto (nao use pastas globais ou de outro projeto).
- Nao crie branch, worktree, push ou deploy; preserve os arquivos ja existentes e a live.
- Nao reinicie processos/servicos nem rode comandos destrutivos sem autorizacao expressa.
- Execute testes relevantes e relate somente o que realmente foi feito.
- Escreva o relatorio em UTF-8 no caminho $reportRel usando arquivo temporario e rename ao final, se possivel.
- Mesmo em caso de falha, escreva o relatorio registrando a causa, sem declarar sucesso.
- Estrutura do relatorio: # Task-Id, ## Resumo, ## Arquivos alterados, ## Testes, ## Bloqueios e riscos, ## Proximos passos.
- Nao inclua credenciais, tokens, variaveis secretas ou conteudos .env.
- O Atlas validara o relatorio e a implementacao. Relatorio nao equivale a autorizacao.
"@
    Save-AtomicUtf8 -TargetPath $requestFile -Text $request
    [pscustomobject]@{status="queued"; task_id=$id; project=$root; request=$requestFile; report=(Join-Path $outbox ($id + ".md"))} | ConvertTo-Json -Compress
    exit 0
}

if ($Mode -eq "list") {
    $items = Get-ChildItem -LiteralPath $inbox -Filter "*.md" -File | Sort-Object LastWriteTime -Descending | Select-Object -First 20
    foreach ($item in $items) {
        $id = $item.BaseName
        $rp = Join-Path $outbox ($id + ".md")
        $statusFile = Join-Path $outbox ($id + ".status.json")
        [pscustomobject]@{task_id=$id; report_exists=(Test-Path -LiteralPath $rp); status_exists=(Test-Path -LiteralPath $statusFile)}
    }
    exit 0
}

Require-TaskId
$requestFile = Join-Path $inbox ($TaskId + ".md")
$reportFile = Join-Path $outbox ($TaskId + ".md")
$statusFile = Join-Path $outbox ($TaskId + ".status.json")
if (-not (Test-Path -LiteralPath $requestFile -PathType Leaf)) {
    throw "Pedido nao encontrado para esse projeto e TaskId"
}

if ($Mode -eq "read") {
    if (Test-Path -LiteralPath $statusFile -PathType Leaf) {
        Get-Content -LiteralPath $statusFile -Encoding UTF8
    } else {
        Write-Output '{"status":"not_started"}'
    }
    if (Test-Path -LiteralPath $reportFile -PathType Leaf) {
        Write-Output "--- RELATORIO OPENCODE ---"
        Get-Content -LiteralPath $reportFile -Encoding UTF8 -TotalCount 300
        if ((Get-Item -LiteralPath $reportFile).Length -gt 131072) { Write-Output "[Relatorio longo: leitura parcial]" }
    } else {
        Write-Output "RELATORIO_AUSENTE"
    }
    exit 0
}

if ($Mode -notin @("run", "reconcile")) { throw "Modo invalido" }
if ($Mode -eq "reconcile" -or $Transport -eq "api") {
    $runner = Join-Path $PSScriptRoot "atlas_opencode_api.py"
    if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
        throw "API bridge Python nao encontrado"
    }
    $url = if ($ServerUrl) { $ServerUrl } else { "https://x99.tail2ffe44.ts.net" }
    $apiModel = if ($Model -match '^opencode/(.+)$') { $Matches[1] } else { $Model }
    $apiArguments = @($runner, "--project", $root, "--task-id", $TaskId, "--timeout-seconds", "$TimeoutSeconds", "--base-url", $url)
    if ($apiModel) { $apiArguments += @("--model", $apiModel) }
    if ($Mode -eq "reconcile") { $apiArguments += "--reconcile" }
    & py -3 @apiArguments
    exit $LASTEXITCODE
}
if (Test-Path -LiteralPath $statusFile) { throw "Task ja executada. Crie novo TaskId para uma nova tentativa." }
if (Test-Path -LiteralPath $reportFile) { throw "Relatorio existente; nao sobrescrever." }

# Exclusao mutua por PROJETO. Falha fechada em caso de lock, sem apagar lock antigo automaticamente.
$lockFile = Join-Path $tmp "active.lock"
$lock = $null
$started = (Get-Date).ToUniversalTime().ToString("o")
$state = "launcher_error"
$exitCode = $null
$process = $null
$stdout = Join-Path $tmp ($TaskId + ".stdout.log")
$stderr = Join-Path $tmp ($TaskId + ".stderr.log")
try {
    $lock = [System.IO.File]::Open($lockFile, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    $lockBytes = $utf8.GetBytes($TaskId)
    $lock.Write($lockBytes, 0, $lockBytes.Length)
    $lock.Flush()

    $exe = Join-Path $env:APPDATA "npm\node_modules\@opencode\cli\bin\opencode.exe"
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw "Executavel do OpenCode nao localizado"
    }
    $relativeRequest = ".atlas/opencode/inbox/" + $TaskId + ".md"
    $relativeReport = ".atlas/opencode/outbox/" + $TaskId + ".md"
    $prompt = "Read and execute the project-local task at $relativeRequest. Stay in the current project root, not another repo. ALWAYS write your factual Markdown report at $relativeReport before replying. Do not create branch/worktree, commit, push, deploy, restart services, or leak secrets. Report real tests and blockers. Follow existing project rules."
    $title = "Atlas task " + $TaskId
    $escapedPrompt = '"' + $prompt.Replace('"','\"') + '"'
    $argsLine = 'run --agent build --title "' + $title + '" ' + $escapedPrompt
    if ($ServerUrl) {
        # Acesso HTTPS apenas na VPN Tailscale, sem publicar a API na internet.
        if ($ServerUrl -ne 'https://x99.tail2ffe44.ts.net') {
            throw "Somente o endpoint HTTPS privado da VPN esta permitido"
        }
        $localConfig = Join-Path $env:USERPROFILE '.config\opencode\service.json'
        $authConfig = Get-Content -LiteralPath $localConfig -Raw | ConvertFrom-Json
        if ([string]::IsNullOrWhiteSpace([string]$authConfig.password)) {
            throw "A senha local do OpenCode nao esta configurada"
        }
        $env:OPENCODE_PASSWORD = [string]$authConfig.password
        $argsLine = 'run --server "' + $ServerUrl + '" --agent build --title "' + $title + '" ' + $escapedPrompt
    }

    if ($Model) {
        if ($Model -notmatch '^opencode/[a-zA-Z0-9.-]+-free$') { throw 'Somente modelos OpenCode free sao permitidos no teste.' }
        $argsLine = $argsLine.Replace('run --', 'run --model "' + $Model + '" --')
    }
    $process = Start-Process -FilePath $exe -ArgumentList $argsLine -WorkingDirectory $root -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    if ($ServerUrl) { Remove-Item Env:OPENCODE_PASSWORD -ErrorAction SilentlyContinue }
    $finished = $process.WaitForExit($TimeoutSeconds * 1000)
    if (-not $finished) {
        $state = "timeout"
        # Encerra apenas a arvore do CLI criado nesta tarefa; nao reinicia o servidor OpenCode compartilhado.
        & taskkill.exe /T /F /PID $process.Id 2>&1 | Out-Null
    } else {
        $process.Refresh()
        $exitCode = [int]$process.ExitCode
        if (Test-Path -LiteralPath $reportFile -PathType Leaf) {
            $state = if ($exitCode -eq 0) { "reported" } else { "reported_with_error" }
        } else {
            $state = if ($exitCode -eq 0) { "missing_report" } else { "failed_without_report" }
        }
    }
} catch {
    # Nao despejar exception / logs, que podem conter credenciais ou comandos sensiveis.
    $state = "launcher_error"
} finally {
    if ($ServerUrl) { Remove-Item Env:OPENCODE_PASSWORD -ErrorAction SilentlyContinue }
    if ($null -ne $lock) {
        $lock.Dispose()
        if (Test-Path -LiteralPath $lockFile) { Remove-Item -LiteralPath $lockFile -Force }
    }
    $status = [ordered]@{
        task_id = $TaskId
        state = $state
        exit_code = $exitCode
        report_exists = [bool](Test-Path -LiteralPath $reportFile -PathType Leaf)
        finished_at = (Get-Date).ToUniversalTime().ToString("o")
        started_at = $started
    }
    Save-AtomicUtf8 -TargetPath $statusFile -Text (($status | ConvertTo-Json -Depth 4) + "`n")
}
$status | ConvertTo-Json -Compress
if ($state -ne "reported") { exit 2 }
