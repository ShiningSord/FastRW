# FastRW / FasterRW

[English](README.md)

这里是 **FastRW（DATE 2026）** 和 **FasterRW 预印本**的代码与实验。
两个方法都用于稳态热分析：FastRW 利用 FEM 温度场降低随机游走的计算开销，
FasterRW 在此基础上加入高斯过程修正。求解器使用 C++17 和 Apple Metal 实现。

<p>
  <img src="docs/figures/bootstrap_case1.png" width="32%">
  <img src="docs/figures/bootstrap_case2.png" width="32%">
  <img src="docs/figures/bootstrap_case3.png" width="32%">
</p>

## 一键复现

Metal 实验需要 Apple Silicon Mac。请先安装 Conda；如果要重新运行求解器，
还需要 Xcode Command Line Tools（`xcode-select --install`）。
Conda 环境已包含 CMake、Node.js、Python、NumPy 和 Matplotlib。

```bash
git clone https://github.com/ShiningSord/ResRW.git
cd ResRW
conda env create -f environment.yml
conda activate fastrw

./reproduce.sh
open outputs/report.html
```

仓库中的 `resrw-artifacts-v1.zip` 包含 COMSOL 温度场和预计算的蒙特卡洛结果。
脚本首次运行时会自动解压，默认复用这些蒙特卡洛结果，再运行后处理，生成表格、
曲线和 HTML 报告。**这个流程不需要安装 COMSOL。**

报告保存在 `outputs/report.html`，实验数据和图片在 `outputs/` 下。
运行时间取决于机器配置，以及是否复用已有的蒙特卡洛结果。

### 重新运行随机游走

如果要重新计算主实验，而不是复用它们的蒙特卡洛结果：

```bash
./reproduce.sh --force-phase1
```

这会重新运行所选 case 的 PIRW 和 FastRW 随机游走，随后重新生成包括 FasterRW
在内的后处理结果。它不会重建 COMSOL 温度场，也不会重跑先验网格精度和弱先验
实验的蒙特卡洛模拟；这两项实验仍使用随仓库提供的数据。

其他常用选项：

```bash
./reproduce.sh --cases=1       # 只运行 case 1
./reproduce.sh --skip-phase3  # 跳过 bootstrap 扫描和附加实验
./reproduce.sh --skip-report  # 不生成 HTML 报告
./reproduce.sh --help
```

这些选项可以组合使用。分组大小、先验网格精度、弱先验和耗时实验只在选中 case 1
时运行。重新运行求解器时，不同 GPU 和编译环境可能带来数值差异，耗时也随硬件变化。

## 修改与单独运行

求解器代码在 `src/` 和 `include/`，实验配置在 `configs/`，
`reproduce.sh` 调用的脚本在 `scripts/`。如果只想运行某个阶段，
可以使用 `reproduce.sh` 中对应的命令。仅根据已有结果重新生成报告：

```bash
python3 scripts/build_html_report.py
```

如需重建 FEM 先验，请安装 COMSOL Multiphysics 6.2，然后运行：

```bash
./comsol.sh --dry-run  # 查看将要运行的任务
./comsol.sh            # 按保存的网格参数重建先验
```

如果 COMSOL 不在默认的 macOS 安装位置，可通过 `COMSOL_BIN=/path/to/comsol`
指定路径。这个脚本不会重建随仓库提供的参考温度场。

CPU 入口 `scripts/build_and_run.sh` 可用于开发，但未针对论文复现流程持续维护。
仓库也提供实验性的 Windows / NVIDIA CUDA 后端，尚未经维护者严格测试，
安装方法和使用限制见 [Windows 指南](windows.zh.md)。

## 引用

FastRW（DATE 2026）的引用信息：

```bibtex
@inproceedings{wang2026fastrw,
  title = {{FastRW}: An Efficient Random Walk Method for Steady-State Thermal Analysis},
  author = {Wang, Zixiao and Hou, Tianshu and Wang, Chenghan and Zhuang, Zhen and Ho, Tsung-Yi and Farnia, Farzan and Yu, Bei},
  booktitle = {Proceedings of the Design, Automation and Test in Europe Conference (DATE)},
  address = {Verona, Italy},
  month = apr,
  year = {2026}
}
```

## 许可证

[MIT](LICENSE)。
