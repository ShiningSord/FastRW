# FastRW: Windows + NVIDIA CUDA Reproduction Guide

[中文版](windows.zh.md)

This guide explains how to configure the FastRW CUDA environment on Windows, run the three official test cases, and reproduce the main results in Table 1 of the paper.

## 1. Supported Scope

The Windows CUDA backend supports:

- PIRW, the baseline random-walk solver;
- FastRW, including the FEM prior, residual random walk, and path-tail reuse;
- FasterRW post-processing in Node.js;
- Case 1, Case 2, and Case 3;
- the same CSV, JSON, log, and summary formats as the Apple Metal backend.

CUDA and Metal use different GPU math implementations, so bit-for-bit equality is not expected. A successful reproduction means that temperatures agree within Monte Carlo uncertainty and that the paper speedups agree after rounding.

## 2. Hardware and Software Requirements

The following components are required:

1. 64-bit Windows 10 or Windows 11;
2. an NVIDIA GPU;
3. an NVIDIA display driver;
4. the CUDA Toolkit;
5. Visual Studio 2019/2022 Build Tools;
6. Miniconda or Anaconda;
7. PowerShell.

When installing Visual Studio Build Tools, select **Desktop development with C++** and install the MSVC x64 toolchain and a Windows SDK.

The following configuration has been tested:

| Component | Tested version |
|---|---|
| GPU | NVIDIA GeForce RTX 3050 Ti Laptop GPU |
| Compute Capability | 8.6 |
| CUDA Toolkit | 11.3 |
| Visual Studio Build Tools | 2022 |
| MSVC | 19.44 |
| Python | 3.11 |
| CMake | 4.3.4 |
| Node.js | 26.5 |

> `environment-windows.yml` installs user-level dependencies such as Python, CMake, and Node.js. It does not install the NVIDIA driver, CUDA Toolkit, or Visual Studio compiler.

## 3. Selecting the CUDA Architecture

The project defaults to `CudaArchitecture=86`, which is suitable for RTX 30-series GPUs.

| GPU | CUDA Architecture |
|---|---:|
| GTX 10 series | 61 |
| RTX 20 series | 75 |
| RTX 30 series | 86 |
| RTX 40 series | 89 |

For RTX 40-series GPUs, use a newer CUDA Toolkit that supports architecture 89.

## 4. Create the Conda Environment

Open PowerShell in the project root and run:

```powershell
conda env create -f .\environment-windows.yml
conda activate FastRW
```

For later sessions, activate the environment before running the project:

```powershell
conda activate FastRW
```

## 5. Run a CUDA Smoke Test

Start with two samples to verify the compiler, CUDA setup, and input data:

```powershell
.\scripts\build_and_run_cuda.ps1 `
    -Config .\configs\tcad_table1\fastrw_case1.json `
    -NumSamples 2 `
    -ThreadsPerBlock 256 `
    -CudaArchitecture 86
```

For a different GPU generation, change `CudaArchitecture` according to Section 3.

A successful run prints messages similar to:

```text
CUDA device: NVIDIA ...
CUDA simulation complete in ... seconds
```

It also creates:

```text
build-cuda\random_walker_cuda.exe
outputs\tcad_table1\fastrw_case1\direct.csv
outputs\tcad_table1\fastrw_case1\summary.json
```

The smoke test only verifies that the program runs. Its sample count is too small for comparison with the paper.

## 6. Run All Three PIRW Cases

The paper configuration uses 4096 paths per query point for PIRW:

```powershell
.\scripts\run_pirw_direct.ps1 `
    -Case all `
    -NumSamples 4096 `
    -ThreadsPerBlock -1
```

`-1` selects the default value of 256 threads per block.

Results are written to:

```text
outputs\tcad_table1\pirw_case1
outputs\tcad_table1\pirw_case2
outputs\tcad_table1\pirw_case3
```

## 7. Run All Three FastRW Cases

The paper configuration uses 8192 paths per query point for FastRW:

```powershell
.\scripts\run_fastrw_direct.ps1 `
    -Case all `
    -NumSamples 8192 `
    -ThreadsPerBlock -1
```

Results are written to:

```text
outputs\tcad_table1\fastrw_case1
outputs\tcad_table1\fastrw_case2
outputs\tcad_table1\fastrw_case3
```

The six production cases take approximately 90 minutes in total on an RTX 3050 Ti Laptop GPU. Actual runtime depends on GPU performance, power limits, and cooling.

## 8. Run the Table 1 Post-Processing

The following command runs the 18 paper-locked bootstrap cells covering three cases, two error thresholds, and three methods:

```powershell
.\scripts\run_table1_post.ps1 `
    -BootstrapTrials 500 `
    -Seed 42
```

Results are written to:

```text
outputs\tcad_table1\paper_results
```

The Table 1 speedup is the reduction in random-walk work required to
reach the same temperature error:

```text
work = sample count N × average steps per path
speedup = PIRW work / current-method work
```

Both inputs come from the Windows reproduction: `N` is selected by the
bootstrap post-processing of the Windows CUDA temperature samples, and
the average step count is read from the Windows CUDA `direct.csv` files.
Once those measured inputs exist, the arithmetic itself is independent
of wall-clock performance.

For the separate hardware-dependent wall-clock analysis, run:

```powershell
node .\scripts\run_wallclock_all.js
```

## 9. Expected Results

The headline Windows CUDA results in `outputs/report.html` should be:

**Table 1 — iso-accuracy speedup (N·steps over PIRW)**

|   | ε = 0.4 K | ε = 0.5 K |
| - | --------- | --------- |
| Case 1 FastRW   | 5.2× | 5.2× |
| Case 1 FasterRW | **8.7×** | **10.5×** |
| Case 2 FastRW   | 5.2× | 5.2× |
| Case 2 FasterRW | **10.5×** | **8.7×** |
| Case 3 FastRW   | 3.7× | 4.2× |
| Case 3 FasterRW | **24.5×** | **28.0×** |

These values use the `N` selected from the Windows bootstrap results and
the average step counts measured by the Windows CUDA runs. Unrounded
results and the Metal comparison are documented in `ios_vs_windows.md`.

**tab:time (Case 1, ε = 0.4 K, wall-clock breakdown)** — FasterRW is
**≥ 7.991×** end-to-end over PIRW (FastRW ≥ 4.994×). The random-walk
stage remains the dominant cost: PIRW 16.146 s vs FastRW 3.140 s vs
FasterRW 1.884 s per query; FEM-prior amortized cost is < 0.063 s/query.

**tab:multi (Case 1, N = 1000)** — FasterRW per-query equivalent
path count grows from 1.00× (G=1) to **3.73× ± 0.84** (G=16); FastRW
grows from 1.00× to 1.83× ± 0.24.

**tab:tradeoff (Case 1)** — CUDA random-walk time per query drops from
6.39 s (DoF=699, ε_max=8.71 K) to 3.55 s (DoF=10254,
ε_max=1.26 K).

**tab:weakprior (Case 1, ε = 0.4 K)** — With the uniform ambient prior,
FastRW reaches 0.324 K mean error at N=1024 and FasterRW reaches
0.390 K at N=512; their CUDA random-walk speedups over PIRW are
1.56× and 3.12×, respectively.

**Bootstrap figures** — all 18 bootstrap cells cover three cases, two
error thresholds, and three methods. FastRW and FasterRW reach each
target error using fewer paths than PIRW.

Small timing differences are expected across GPUs, driver versions,
power limits, and cooling conditions. The exact per-stage measurements
are stored in `outputs\tcad_table_time\all_cases_wallclock.json`.

## 10. Generate the HTML Report

After generating the post-processing data, run:

```powershell
python .\scripts\build_html_report.py
```

The final report is written to:

```text
outputs\report.html
```

Open this file in a web browser.
