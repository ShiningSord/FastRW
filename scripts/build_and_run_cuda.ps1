[CmdletBinding()]
param(
    [string]$Config = '',
    [int]$NumSamples = 2,
    [int]$ThreadsPerBlock = -1,
    [int]$CudaArchitecture = 86
)

$ErrorActionPreference = 'Stop'
$RootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $Config) {
    $Config = Join-Path $RootDir 'configs\tcad_table1\fastrw_case1.json'
}
$Config = (Resolve-Path -LiteralPath $Config).Path
$BuildDir = Join-Path $RootDir 'build-cuda'

function Import-MsvcEnvironment {
    if (Get-Command cl.exe -ErrorAction SilentlyContinue) { return }
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere)) {
        throw 'MSVC was not found. Install Visual Studio 2019/2022 Build Tools with Desktop development with C++.'
    }
    $installation = & $vswhere -latest -products * `
        -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
        -property installationPath
    if (-not $installation) {
        throw 'Visual Studio C++ Build Tools were not found. Add the Desktop development with C++ workload.'
    }
    $vcvars = Join-Path $installation 'VC\Auxiliary\Build\vcvars64.bat'
    # CALL is required here: without it, cmd can keep an interactive child
    # open when a quoted batch path contains spaces.
    cmd.exe /d /c "call `"$vcvars`" >nul && set" | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') { Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2] }
    }
}

Import-MsvcEnvironment
$Nvcc = if ($env:CUDA_PATH) { Join-Path $env:CUDA_PATH 'bin\nvcc.exe' } else { $null }
if (-not $Nvcc -or -not (Test-Path -LiteralPath $Nvcc)) {
    $foundNvcc = Get-Command nvcc.exe -ErrorAction SilentlyContinue
    if ($foundNvcc) { $Nvcc = $foundNvcc.Source }
}
if (-not $Nvcc -or -not (Test-Path -LiteralPath $Nvcc)) {
    throw 'nvcc.exe was not found. Install the NVIDIA CUDA Toolkit or set CUDA_PATH.'
}
# NMake avoids a Ninja/MSVC dependency-scan hang on localized Windows hosts.
cmake -S $RootDir -B $BuildDir -G "NMake Makefiles" `
    -DCMAKE_BUILD_TYPE=Release `
    -DFASTRW_ENABLE_CUDA=ON `
    "-DCMAKE_CUDA_COMPILER=$Nvcc" `
    "-DCMAKE_CUDA_FLAGS=-allow-unsupported-compiler -D_ALLOW_COMPILER_AND_STL_VERSION_MISMATCH" `
    "-DCUDAToolkit_ROOT=$env:CUDA_PATH" `
    "-DCMAKE_CUDA_ARCHITECTURES=$CudaArchitecture"
if ($LASTEXITCODE -ne 0) { throw 'CMake configuration failed.' }
cmake --build $BuildDir --target random_walker_cuda
if ($LASTEXITCODE -ne 0) { throw 'CUDA build failed.' }

$configJson = Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
$configDir = Split-Path -Parent $Config
$outputSetting = if ($configJson.output.directory) { $configJson.output.directory } else { '..\outputs' }
$RunDir = [IO.Path]::GetFullPath((Join-Path $configDir $outputSetting))
New-Item -ItemType Directory -Path $RunDir -Force | Out-Null
$Log = Join-Path $RunDir 'last_random_walker_cuda.log'
$Exe = Join-Path $BuildDir 'random_walker_cuda.exe'

Push-Location $RootDir
try {
    & $Exe $Config $NumSamples $ThreadsPerBlock 2>&1 | Tee-Object -FilePath $Log
    if ($LASTEXITCODE -ne 0) { throw "random_walker_cuda exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
}

$text = Get-Content -LiteralPath $Log -Raw
$matches = [regex]::Matches($text, 'CUDA simulation complete in\s+([0-9eE+.-]+)\s+seconds')
if ($matches.Count -gt 0) {
    $gpu = (& nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Select-Object -First 1).Trim()
    $summaryPath = Join-Path $RunDir 'summary.json'
    $summary = if (Test-Path $summaryPath) {
        Get-Content $summaryPath -Raw | ConvertFrom-Json
    } else { [pscustomobject]@{} }
    $randomWalk = [pscustomobject]@{
        backend = 'cuda'
        device = $gpu
        runtime_seconds = [double]$matches[$matches.Count - 1].Groups[1].Value
        runtime_source = 'simulate_temperature_multi log line'
        config = $Config
        num_samples = $NumSamples
        log = $Log
    }
    $summary | Add-Member -MemberType NoteProperty -Name random_walk -Value $randomWalk -Force
    $json = $summary | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText($summaryPath, $json + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
}
