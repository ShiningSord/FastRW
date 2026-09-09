# Apple Metal 与 Windows CUDA 复现数据对比

> 文件名按项目约定保留为 `ios_vs_windows.md`。原作者实际运行环境是
> **macOS + Apple Silicon Metal**，不是 iOS；本文中的“Apple/Metal”均指
> 原作者的 macOS 环境。

## 1. 对比结论

Windows 的 Table 1 不是直接复制 README 中的结果。其两个输入均来自
Windows CUDA 运行：

- `N`：使用 Windows CUDA 生成的温度样本，以 `B=500`、`seed=42` 进行
  bootstrap，选出达到目标误差 ε 的最小路径数。
- 平均步数：由 Windows CUDA 可执行程序写入各 Case 的 `direct.csv`，
  再对 16 个查询点的 `Avg_Steps` 取平均。

Windows 与 Metal 最终选出的 18 个 `N` 完全相同；三个 Case 的平均步数
相对差异不超过约 0.055%。因此六组工作量加速比在保留一位小数时全部
与原作者 README 一致。

## 2. Bootstrap 选出的 N

每个单元格格式为 `Metal N / Windows CUDA N`：

| Case | ε (K) | PIRW | FastRW | FasterRW |
|---|---:|---:|---:|---:|
| 1 | 0.4 | 1280 / 1280 | 640 / 640 | 384 / 384 |
| 1 | 0.5 | 768 / 768 | 384 / 384 | 192 / 192 |
| 2 | 0.4 | 2560 / 2560 | 1280 / 1280 | 640 / 640 |
| 2 | 0.5 | 1280 / 1280 | 640 / 640 | 384 / 384 |
| 3 | 0.4 | 1792 / 1792 | 1280 / 1280 | 192 / 192 |
| 3 | 0.5 | 1024 / 1024 | 640 / 640 | 96 / 96 |

这些值来自 Windows 的
[`outputs/tcad_table1/paper_results`](outputs/tcad_table1/paper_results)
和保存的 Metal 对照数据
[`outputs/validation_cuda_vs_mac/mac_paper_results`](outputs/validation_cuda_vs_mac/mac_paper_results)。

## 3. 实际运行产生的平均步数

| Case | 方法 | Metal 平均步数 | Windows CUDA 平均步数 | Windows 相对差异 |
|---|---|---:|---:|---:|
| 1 | PIRW | 5,985,061.875 | 5,986,454.375 | +0.0233% |
| 1 | FastRW | 2,283,796.250 | 2,283,858.750 | +0.0027% |
| 2 | PIRW | 5,996,831.250 | 5,998,207.500 | +0.0230% |
| 2 | FastRW | 2,292,669.375 | 2,292,720.000 | +0.0022% |
| 3 | PIRW | 10,581,731.250 | 10,575,943.750 | −0.0547% |
| 3 | FastRW | 4,031,889.375 | 4,033,429.375 | +0.0382% |

Windows 原始数据分别位于：

- [`pirw_case1/direct.csv`](outputs/tcad_table1/pirw_case1/direct.csv)、
  [`pirw_case2/direct.csv`](outputs/tcad_table1/pirw_case2/direct.csv)、
  [`pirw_case3/direct.csv`](outputs/tcad_table1/pirw_case3/direct.csv)
- [`fastrw_case1/direct.csv`](outputs/tcad_table1/fastrw_case1/direct.csv)、
  [`fastrw_case2/direct.csv`](outputs/tcad_table1/fastrw_case2/direct.csv)、
  [`fastrw_case3/direct.csv`](outputs/tcad_table1/fastrw_case3/direct.csv)

FasterRW 复用 FastRW 的随机游走路径，并通过后处理进一步融合结果，所以
同一个 Case 中 FasterRW 与 FastRW 使用相同的平均步数，但选用不同的 `N`。

## 4. 等精度工作量加速比

计算公式为：

\[
S=\frac{N_{\mathrm{PIRW}}\,\overline{Steps}_{\mathrm{PIRW}}}
        {N_{\mathrm{method}}\,\overline{Steps}_{\mathrm{FastRW}}}
\]

| Case | ε (K) | FastRW Metal | FastRW CUDA | FasterRW Metal | FasterRW CUDA |
|---|---:|---:|---:|---:|---:|
| 1 | 0.4 | 5.241× | 5.242× | 8.736× | 8.737× |
| 1 | 0.5 | 5.241× | 5.242× | 10.483× | 10.485× |
| 2 | 0.4 | 5.231× | 5.232× | 10.463× | 10.465× |
| 2 | 0.5 | 5.231× | 5.232× | 8.719× | 8.721× |
| 3 | 0.4 | 3.674× | 3.671× | 24.495× | 24.473× |
| 3 | 0.5 | 4.199× | 4.195× | 27.995× | 27.969× |

按 README 的一位小数显示，两边均得到：

|   | ε = 0.4 K | ε = 0.5 K |
| - | --------- | --------- |
| Case 1 FastRW   | 5.2× | 5.2× |
| Case 1 FasterRW | **8.7×** | **10.5×** |
| Case 2 FastRW   | 5.2× | 5.2× |
| Case 2 FasterRW | **10.5×** | **8.7×** |
| Case 3 FastRW   | 3.7× | 4.2× |
| Case 3 FasterRW | **24.5×** | **28.0×** |

例如 Case 1、ε=0.4 的 Windows FastRW 结果为：

\[
\frac{1280\times5{,}986{,}454.375}
     {640\times2{,}283{,}858.750}=5.242
\]

这一步算术本身与硬件无关；但其中的 `N` 和平均步数是 Windows 实验产生
的。任何人使用完全相同的这两个输入都会得到相同结果，独立重新运行时则
可能因随机采样和浮点顺序出现很小的统计差异。

## 5. 绝对运行时间

工作量加速比不等于运行时间。下面是完整 `Nmax` CUDA/Metal 主模拟的
实测总时间：

| Case | 方法 | Nmax | Metal (s) | Windows CUDA (s) | Windows / Metal |
|---|---|---:|---:|---:|---:|
| 1 | PIRW | 4096 | 296.290 | 826.650 | 2.79× |
| 1 | FastRW | 8192 | 226.710 | 643.135 | 2.84× |
| 2 | PIRW | 4096 | 297.343 | 801.037 | 2.69× |
| 2 | FastRW | 8192 | 228.764 | 654.853 | 2.86× |
| 3 | PIRW | 4096 | 524.444 | 1426.450 | 2.72× |
| 3 | FastRW | 8192 | 400.274 | 1108.260 | 2.77× |

Windows 测试设备是 NVIDIA GeForce RTX 3050 Ti Laptop GPU。绝对时间
受 GPU 型号、功耗、散热、驱动和后端实现影响，因此不能要求它与 Apple
M5 Pro 相同。这里的关键复现结论是 `N`、平均步数、误差统计和工作量
加速比一致，而不是两台不同硬件的秒数相同。

## 6. 最终判断

- Windows 的 `N` 确实由 Windows CUDA 样本重新进行 bootstrap 后确定。
- Windows 的平均步数确实由 Windows CUDA 主程序实际运行产生。
- 六组 `N` 与 Metal 完全一致。
- Case 级平均步数最大相对差异约为 0.055%。
- 未取整工作量加速比最大相对差异约为 0.093%。
- 所有结果取一位小数后与原作者 README 完全一致。

因此 Windows CUDA 已经复现了作者 Table 1 所定义的等精度工作量结果。
