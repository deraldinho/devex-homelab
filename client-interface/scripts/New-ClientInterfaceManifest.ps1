[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
    [string]$SystemPath,

    [Parameter(Mandatory = $false)]
    [string]$OutputPath = ".\client-interface-manifest.json",

    [Parameter(Mandatory = $false)]
    [string]$ProfileId = "interlude-746-l2jtoren"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$trackedFiles = @(
    "Interface.xdat",
    "Interface.u",
    "Interface.int",
    "Interface.dll",
    "NWindow.dll",
    "Engine.dll",
    "Core.dll",
    "Fire.dll",
    "dsetup.dll",
    "L2.exe",
    "l2.ini"
)

function Get-PeMetadata {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    try {
        $reader = [System.IO.BinaryReader]::new($stream)
        if ($stream.Length -lt 64) {
            return $null
        }

        if ($reader.ReadUInt16() -ne 0x5A4D) {
            return $null
        }

        $stream.Position = 0x3C
        $peOffset = $reader.ReadUInt32()
        if ($peOffset + 24 -gt $stream.Length) {
            return $null
        }

        $stream.Position = $peOffset
        if ($reader.ReadUInt32() -ne 0x00004550) {
            return $null
        }

        $machine = $reader.ReadUInt16()
        $numberOfSections = $reader.ReadUInt16()
        $timeDateStamp = $reader.ReadUInt32()
        $stream.Position += 8
        $sizeOfOptionalHeader = $reader.ReadUInt16()
        $characteristics = $reader.ReadUInt16()

        $optionalHeaderStart = $stream.Position
        if ($sizeOfOptionalHeader -lt 60 -or ($optionalHeaderStart + $sizeOfOptionalHeader) -gt $stream.Length) {
            return $null
        }

        $magic = $reader.ReadUInt16()
        if ($magic -ne 0x10B -and $magic -ne 0x20B) {
            return $null
        }

        $stream.Position = $optionalHeaderStart + 56
        $sizeOfImage = $reader.ReadUInt32()

        return [ordered]@{
            machine = ('0x{0:X4}' -f $machine)
            numberOfSections = [int]$numberOfSections
            timeDateStamp = [uint32]$timeDateStamp
            timeDateStampUtc = [DateTimeOffset]::FromUnixTimeSeconds($timeDateStamp).UtcDateTime.ToString("o")
            sizeOfImage = [uint32]$sizeOfImage
            optionalHeaderMagic = ('0x{0:X4}' -f $magic)
            characteristics = ('0x{0:X4}' -f $characteristics)
        }
    }
    finally {
        $stream.Dispose()
    }
}

$resolvedSystemPath = (Resolve-Path -LiteralPath $SystemPath).Path
$files = foreach ($fileName in $trackedFiles) {
    $fullPath = Join-Path $resolvedSystemPath $fileName
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        continue
    }

    $item = Get-Item -LiteralPath $fullPath
    $hash = Get-FileHash -LiteralPath $fullPath -Algorithm SHA256
    $signature = Get-AuthenticodeSignature -LiteralPath $fullPath
    $pe = Get-PeMetadata -Path $fullPath

    [ordered]@{
        fileName = $item.Name
        relativePath = $item.Name
        sizeBytes = [int64]$item.Length
        sha256 = $hash.Hash.ToLowerInvariant()
        lastWriteUtc = $item.LastWriteTimeUtc.ToString("o")
        authenticode = [ordered]@{
            status = $signature.Status.ToString()
            signer = if ($null -ne $signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { $null }
        }
        pe = $pe
    }
}

if ($files.Count -eq 0) {
    throw "Nenhum arquivo rastreado foi encontrado em '$resolvedSystemPath'."
}

$manifest = [ordered]@{
    schemaVersion = 1
    profileId = $ProfileId
    generatedAtUtc = [DateTime]::UtcNow.ToString("o")
    source = [ordered]@{
        systemPathLeaf = (Split-Path -Leaf $resolvedSystemPath)
        absolutePathStored = $false
    }
    files = @($files)
}

$outputDirectory = Split-Path -Parent $OutputPath
if ($outputDirectory -and -not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Host "Manifesto criado: $OutputPath"
Write-Host "Arquivos registrados: $($files.Count)"
