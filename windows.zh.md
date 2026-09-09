# FastRW：Windows + NVIDIA CUDA 复现指南

[English version](windows.md)

本文档说明如何在 Windows 上配置 FastRW CUDA 环境、运行三个正式测试 Case，并复现论文 Table 1 的主要结果。

## 1. 支持范围

Windows CUDA 后端支持：

- PIRW（基准随机游走）；
- FastRW（FEM 先验 + 残差随机游走 + 路径尾部复用）；
- FasterRW 的 Node.js 后处理；
- Case 1、Case 2、Case 3；
- 与 Apple Metal 后端相同格式的 CSV、JSON、日志和汇总文件。

CUDA 和 Metal 使用不同的 GPU 数学实现，因此不要求逐位相同。正确的复现标准是温度结果在蒙特卡洛统计误差内一致，论文加速比四舍五入后一致。

## 2. 硬件和软件要求

必须具备：

1. Windows 10/11 64 位；
2. NVIDIA GPU；
3. NVIDIA 显卡驱动；
4. CUDA Toolkit；
5. Visual Studio 2019/2022 Build Tools；
6. Miniconda 或 Anaconda；
7. PowerShell。

安装 Visual Studio Build Tools 时必须选择 **Desktop development with C++（使用 C++ 的桌面开发）**，并安装 MSVC x64 工具链和 Windows SDK。

已验证的环境为：

| 组件 | 已验证版本 |
|---|---|
| GPU | NVIDIA GeForce RTX 3050 Ti Laptop GPU |
| Compute Capability | 8.6 |
| CUDA Toolkit | 11.3 |
| Visual Studio Build Tools | 2022 |
| MSVC | 19.44 |
| Python | 3.11 |
| CMake | 4.3.4 |
| Node.js | 26.5 |

> `environment-windows.yml` 只安装 Python、CMake、Node.js 等环境依赖，不会安装 NVIDIA 驱动、CUDA Toolkit 或 Visual Studio 编译器。

## 3. CUDA 架构选择

项目默认使用 `CudaArchitecture=86`，适合 RTX 30 系列。

| GPU | CUDA Architecture |
|---|---:|
| GTX 10 系列 | 61 |
| RTX 20 系列 | 75 |
| RTX 30 系列 | 86 |
| RTX 40 系列 | 89 |

RTX 40 系列建议使用支持架构 89 的较新 CUDA Toolkit。

## 4. 创建 Conda 环境

在项目根目录打开 PowerShell，运行：

```powershell
conda env create -f .\environment-windows.yml
conda activate FastRW
```

以后每次运行项目前，只需激活环境：

```powershell
conda activate FastRW
```

## 5. CUDA 冒烟测试

先使用两个样本验证编译器、CUDA 和数据是否可以正常工作：

```powershell
.\scripts\build_and_run_cuda.ps1 `
    -Config .\configs\tcad_table1\fastrw_case1.json `
    -NumSamples 2 `
    -ThreadsPerBlock 256 `
    -CudaArchitecture 86
```

其他型号 GPU 请按第 3 节修改 `CudaArchitecture`。

成功时应看到类似输出：

```text
CUDA device: NVIDIA ...
CUDA simulation complete in ... seconds
```

并生成：

```text
build-cuda\random_walker_cuda.exe
outputs\tcad_table1\fastrw_case1\direct.csv
outputs\tcad_table1\fastrw_case1\summary.json
```

冒烟测试只用于检查程序能否运行，不能用于论文数据比较。

## 6. 完整运行三个 PIRW Case

PIRW 的论文设置是每个查询点 4096 条路径：

```powershell
.\scripts\run_pirw_direct.ps1 `
    -Case all `
    -NumSamples 4096 `
    -ThreadsPerBlock -1
```

`-1` 表示使用默认的 256 threads/block。

输出目录为：

```text
outputs\tcad_table1\pirw_case1
outputs\tcad_table1\pirw_case2
outputs\tcad_table1\pirw_case3
```

## 7. 完整运行三个 FastRW Case

FastRW 的论文设置是每个查询点 8192 条路径：

```powershell
.\scripts\run_fastrw_direct.ps1 `
    -Case all `
    -NumSamples 8192 `
    -ThreadsPerBlock -1
```

输出目录为：

```text
outputs\tcad_table1\fastrw_case1
outputs\tcad_table1\fastrw_case2
outputs\tcad_table1\fastrw_case3
```

RTX 3050 Ti Laptop 上，六个正式 Case 合计约需 90 分钟。实际时间取决于 GPU 性能、功耗和散热状态。

## 8. 运行 Table 1 后处理

下面的命令会执行三个 Case、两个误差阈值和三种算法，共 18 个论文锁定的 bootstrap 单元：

```powershell
.\scripts\run_table1_post.ps1 `
    -BootstrapTrials 500 `
    -Seed 42
```

输出位于：

```text
outputs\tcad_table1\paper_results
```

Table 1 的加速比表示达到相同温度误差时减少的随机游走工作量：

```text
工作量 = 样本数 N × 每条路径的平均步数
加速比 = PIRW 工作量 / 当前方法工作量
```

两个输入都来自 Windows 复现实验：`N` 由 Windows CUDA 温度样本的
bootstrap 后处理选出，平均步数从 Windows CUDA 生成的 `direct.csv`
读取。得到这些实测输入后，该指标的算术计算不再依赖墙钟时间。

如需另外生成与硬件相关的墙钟时间分析，可以运行：

```powershell
node .\scripts\run_wallclock_all.js
```

## 9. 预期结果

`outputs/report.html` 中主要的 Windows CUDA 结果应为：

**Table 1 — 等精度工作量加速比（N·steps，相对 PIRW）**

|   | ε = 0.4 K | ε = 0.5 K |
| - | --------- | --------- |
| Case 1 FastRW   | 5.2× | 5.2× |
| Case 1 FasterRW | **8.7×** | **10.5×** |
| Case 2 FastRW   | 5.2× | 5.2× |
| Case 2 FasterRW | **10.5×** | **8.7×** |
| Case 3 FastRW   | 3.7× | 4.2× |
| Case 3 FasterRW | **24.5×** | **28.0×** |

这些数值使用 Windows bootstrap 选出的 `N` 和 Windows CUDA 实测的
平均步数计算。未取整的结果及其与 Metal 的对比见 `ios_vs_windows.md`。

**tab:time（Case 1，ε = 0.4 K，墙钟时间分解）** — FasterRW 相对 PIRW
的端到端加速至少为 **7.991×**，FastRW 至少为 4.994×。随机游走仍是
主要耗时：PIRW、FastRW 和 FasterRW 分别为 16.146、3.140 和 1.884
秒/查询；FEM 先验的摊销成本小于 0.063 秒/查询。

**tab:multi（Case 1，N = 1000）** — FasterRW 的每查询等效路径数加速
从 G=1 时的 1.00× 增长到 G=16 时的 **3.73× ± 0.84**；FastRW
从 1.00× 增长到 1.83× ± 0.24。

**tab:tradeoff（Case 1）** — CUDA 随机游走时间从 DoF=699、
ε_max=8.71 K 时的 6.39 秒/查询，下降到 DoF=10254、
ε_max=1.26 K 时的 3.55 秒/查询。

**tab:weakprior（Case 1，ε = 0.4 K）** — 使用环境温度均匀先验时，
FastRW 在 N=1024 时达到 0.324 K 平均误差，FasterRW 在 N=512 时
达到 0.390 K；两者相对 PIRW 的 CUDA 随机游走加速比分别为
1.56× 和 3.12×。

**Bootstrap 图** — 18 个 bootstrap 单元覆盖三个 Case、两个误差阈值
和三种方法。FastRW 和 FasterRW 均使用比 PIRW 更少的路径达到目标误差。

不同 GPU、驱动版本、功耗限制和散热条件会造成小幅计时差异。各阶段的
精确测量值保存在 `outputs\tcad_table_time\all_cases_wallclock.json`。

## 10. 生成 HTML 报告

在后处理数据生成后运行：

```powershell
python .\scripts\build_html_report.py
```

最终报告为：

```text
outputs\report.html
```

可以直接使用浏览器打开。
