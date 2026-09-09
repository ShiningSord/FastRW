[CmdletBinding()]
param(
    [ValidateSet('1','2','3','all')][string]$Case = 'all',
    [int]$ThreadsPerBlock = -1,
    [int]$NumSamples = 4096
)
$ErrorActionPreference = 'Stop'
$RootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$cases = if ($Case -eq 'all') { 1,2,3 } else { [int]$Case }
foreach ($caseId in $cases) {
    $config = Join-Path $RootDir "configs\tcad_table1\pirw_case$caseId.json"
    Write-Host "[run_pirw_direct] case$caseId N=$NumSamples (CUDA)"
    & (Join-Path $PSScriptRoot 'build_and_run_cuda.ps1') $config $NumSamples $ThreadsPerBlock
}
