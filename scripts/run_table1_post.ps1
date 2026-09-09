[CmdletBinding()]
param(
    [ValidateRange(1, 1000000)][int]$BootstrapTrials = 500,
    [int]$Seed = 42,
    [string]$InputRoot,
    [string]$OutputDir
)

$ErrorActionPreference = 'Stop'
$RootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$InputRoot = if ($InputRoot) {
    (Resolve-Path $InputRoot).Path
} else {
    Join-Path $RootDir 'outputs\tcad_table1'
}
$OutDir = if ($OutputDir) {
    [System.IO.Path]::GetFullPath($OutputDir)
} else {
    Join-Path $InputRoot 'paper_results'
}
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

$nodeCandidates = @(
    $(if ($env:CONDA_PREFIX) { Join-Path $env:CONDA_PREFIX 'node.exe' }),
    'E:\FastRW\node.exe'
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

if (@($nodeCandidates).Count -gt 0) {
    $NodeExe = @($nodeCandidates)[0]
} else {
    $NodeExe = (Get-Command node.exe -ErrorAction Stop).Source
}

function Invoke-PostProcessor {
    param(
        [Parameter(Mandatory)][string]$Script,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    & $NodeExe $Script @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Post-processing failed with exit code ${LASTEXITCODE}: $Script"
    }
}

$paperN = @{
    1 = @{
        pirw     = @{ '0.5' = 768;  '0.4' = 1280 }
        fastrw   = @{ '0.5' = 384;  '0.4' = 640 }
        fasterrw = @{ '0.5' = 192;  '0.4' = 384 }
    }
    2 = @{
        pirw     = @{ '0.5' = 1280; '0.4' = 2560 }
        fastrw   = @{ '0.5' = 640;  '0.4' = 1280 }
        fasterrw = @{ '0.5' = 384;  '0.4' = 640 }
    }
    3 = @{
        pirw     = @{ '0.5' = 1024; '0.4' = 1792 }
        fastrw   = @{ '0.5' = 640;  '0.4' = 1280 }
        fasterrw = @{ '0.5' = 96;   '0.4' = 192 }
    }
}

foreach ($caseId in 1..3) {
    $pirwRun = Join-Path $InputRoot "pirw_case$caseId"
    $fastrwRun = Join-Path $InputRoot "fastrw_case$caseId"
    $config = Join-Path $RootDir "configs\tcad_table1\fastrw_case$caseId.json"

    foreach ($epsilon in '0.5', '0.4') {
        $n = $paperN[$caseId].pirw[$epsilon]
        Write-Host "[table1-post] case$caseId PIRW eps=$epsilon N=$n B=$BootstrapTrials"
        Invoke-PostProcessor `
            -Script (Join-Path $PSScriptRoot 'run_pirw_post.js') `
            -Arguments @(
                $pirwRun,
                "--N=$n", "--B=$BootstrapTrials", "--seed=$Seed",
                "--output=$(Join-Path $OutDir "case${caseId}_pirw_eps$epsilon.json")"
            )

        $n = $paperN[$caseId].fastrw[$epsilon]
        Write-Host "[table1-post] case$caseId FastRW eps=$epsilon N=$n B=$BootstrapTrials"
        Invoke-PostProcessor `
            -Script (Join-Path $PSScriptRoot 'run_fastrw_post.js') `
            -Arguments @(
                $fastrwRun, $config,
                "--N=$n", "--B=$BootstrapTrials", "--seed=$Seed",
                "--output=$(Join-Path $OutDir "case${caseId}_fastrw_eps$epsilon.json")"
            )

        $n = $paperN[$caseId].fasterrw[$epsilon]
        Write-Host "[table1-post] case$caseId FasterRW eps=$epsilon N=$n B=$BootstrapTrials"
        Invoke-PostProcessor `
            -Script (Join-Path $PSScriptRoot 'run_fasterrw_post.js') `
            -Arguments @(
                $fastrwRun, $config,
                "--N=$n", "--B=$BootstrapTrials", "--seed=$Seed",
                "--output=$(Join-Path $OutDir "case${caseId}_fasterrw_eps$epsilon.json")"
            )
    }
}

Write-Host "[table1-post] Done. Results: $OutDir"
