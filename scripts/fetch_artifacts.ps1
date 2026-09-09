[CmdletBinding()]
param(
    [string]$Archive
)

$ErrorActionPreference = 'Stop'
$RootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $Archive) { $Archive = Join-Path $RootDir 'resrw-artifacts-v1.zip' }
$Archive = (Resolve-Path -LiteralPath $Archive).Path

Write-Host "[fetch_artifacts] Extracting $Archive into $RootDir"
Expand-Archive -LiteralPath $Archive -DestinationPath $RootDir -Force

$expected = @(
    'data\cases\case1_power6\power.bin',
    'data\cases\case2_4core_top1_bottom1\power.bin',
    'data\cases\case3_16core\power.bin'
)
foreach ($relativePath in $expected) {
    if (-not (Test-Path -LiteralPath (Join-Path $RootDir $relativePath))) {
        throw "Artifact archive is incomplete; missing $relativePath"
    }
}
Write-Host '[fetch_artifacts] Done.'
