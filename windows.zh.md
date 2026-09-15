# Windows / NVIDIA CUDA 实验性安装与启动指南

[English version](windows.md)

**Windows 版本尚未经项目维护者严格测试，仅供参考。** 其数值精度、稳定性、性能和
不同 Windows/CUDA 环境下的兼容性尚未充分验证。程序能启动并完成运行，不代表其与
Metal 后端数值等价，也不代表已复现论文中的精度或加速比。

此后端基于社区贡献者
[Cai-Shengnan 的 PR #11](https://github.com/ShiningSord/FastRW/pull/11) 整理。

## 环境要求

- 64 位 Windows、NVIDIA GPU 及其驱动。
- 支持所用 GPU 和 MSVC 编译器的 CUDA Toolkit。
- Visual Studio C++ Build Tools，包含“使用 C++ 的桌面开发”工作负载及 Windows SDK。
- PowerShell 和 Conda。

Conda 环境提供 Python、CMake 以及可选的 Node.js/绘图工具；NVIDIA 驱动、CUDA
Toolkit 和 Visual Studio Build Tools 需要单独安装。启动脚本自动导入 MSVC 环境，
使用 CMake 和 NMake 编译。保留编译器兼容性检查：若 CUDA 拒绝当前 MSVC 版本，
应改用兼容的工具链，不能据此认为该组合已获支持。

## 创建环境和准备输入数据

在项目根目录的 PowerShell 中运行：

```powershell
conda env create -f .\environment-windows.yml
conda activate FastRW
.\scripts\fetch_artifacts.ps1
```

解压脚本会展开随仓库提供的 `resrw-artifacts-v1.zip`，包括参考 `data/` 和预计算的
`outputs/`，并覆盖同名文件。若所需输入数据已经存在，可跳过解压。压缩包中的输出
是参考实验产物，不是 CUDA 后端生成的结果。

## 小样本启动检查

```powershell
.\scripts\build_and_run_cuda.ps1 `
    -Config .\configs\tcad_table1\fastrw_case1.json `
    -NumSamples 2 `
    -ThreadsPerBlock 256 `
    -CudaArchitecture 86
```

`CudaArchitecture` 是去掉小数点的 CUDA 计算能力编号。默认值 `86` 面向兼容的 GPU，
例如贡献者使用的 RTX 3050 Ti；请根据自己的 GPU 和 CUDA Toolkit 选择双方支持的值。
这不表示其他 GPU 或工具链组合已经过测试。

脚本会显式打开默认关闭的 CMake 选项 `FASTRW_ENABLE_CUDA`，生成
`build-cuda\random_walker_cuda.exe`。CUDA 构建要求 CMake 3.18 或更新版本；
所附 Conda 环境要求 3.24 或更新版本。

完成运行时会打印设备名称和 `CUDA simulation complete`。每个查询点两个样本只用于
检查启动和输出流程，不能验证统计精度。

此配置的输出位置为：

```text
outputs\tcad_table1\fastrw_case1\cuda-experimental\
    direct.csv
    constraints.json
    last_random_walker_cuda.log
    summary.json
```

配置启用 diagnostics 时还会生成 `diagnostics.json`。`summary.json` 由 PowerShell
启动脚本写入。同一 Case 再次运行会覆盖其实验输出文件；现有论文复现报告不会读取
这些实验输出。

## 其他运行方式

```powershell
# 运行单个 FastRW 或 PIRW Case；以下是采样设置，不是已验证的结果。
.\scripts\run_fastrw_direct.ps1 -Case 1 -NumSamples 8192 -CudaArchitecture 86
.\scripts\run_pirw_direct.ps1 -Case 1 -NumSamples 4096 -CudaArchitecture 86

# 按选定参数依次运行三个 Case。
.\scripts\run_fastrw_direct.ps1 -Case all -CudaArchitecture 86
.\scripts\run_pirw_direct.ps1 -Case all -CudaArchitecture 86
```

`-ThreadsPerBlock -1` 表示每个 block 使用 256 个线程。两个批量运行脚本均支持
`-CudaArchitecture`、`-NumSamples` 和 `-ThreadsPerBlock`。

也可在项目根目录直接运行已编译的程序：

```powershell
.\build-cuda\random_walker_cuda.exe .\configs\tcad_table1\fastrw_case1.json 2 256
```

参数依次为配置文件、每个查询点的样本数、每个 block 的线程数。程序自身也会在配置
的输出目录后追加 `cuda-experimental`，因此直接启动使用相同的独立输出位置。

## Kernel 维护

CUDA 源码由参考 Metal kernel 和 CUDA 主机端适配代码生成。修改
`src/walker_metal.mm` 后，运行：

```powershell
python .\scripts\generate_cuda_port.py
```

CUDA 主机端适配代码应在生成脚本中修改。重新生成源码不能替代 Windows/NVIDIA
环境下的实际测试。
