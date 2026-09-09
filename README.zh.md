# FastRW（中文）

[English README](README.md)

基于 Feynman-Kac 公式的 GPU 随机游走求解器，用于带混合边界条件的
稳态热问题，并提供 **FastRW / FasterRW** 算法的复现实验框架
（Windows NVIDIA CUDA、Apple Metal + C++17）。

## Windows + NVIDIA CUDA 快速开始

完整的新机器环境安装、正式实验和结果核对步骤请参见
[windows.zh.md](windows.zh.md)。

Windows CUDA 后端需要 NVIDIA GPU、CUDA Toolkit，以及安装了“使用 C++ 的桌面开发”
工作负载的 Visual Studio 2019/2022 Build Tools。RTX 3050 Ti 可使用 CUDA 11.3 和
计算能力 8.6。请在 PowerShell 中运行：

```powershell
# 首次运行：在 E 盘创建名为 FastRW 的独立环境。
conda env create --prefix E:\FastRW -f environment-windows.yml
conda activate E:\FastRW

# 解压随仓库提供的数据，并进行两条路径的 CUDA 冒烟测试。
.\scripts\fetch_artifacts.ps1
.\scripts\build_and_run_cuda.ps1 `
  .\configs\tcad_table1\fastrw_case1.json 2 256

# Phase 1 正式运行（FastRW 每点 8192 条路径，PIRW 每点 4096 条路径）。
.\scripts\run_fastrw_direct.ps1 1
.\scripts\run_pirw_direct.ps1 1
```

`build_and_run_cuda.ps1` 会自动导入 Visual Studio 编译环境、用 CMake/NMake
构建 `random_walker_cuda.exe` 并运行。CUDA 后端保持与 Metal 后端相同的 CSV、
constraints JSON、diagnostics JSON、日志和 summary 输出格式。第四个程序参数是
CUDA 每个 block 的线程数，传入 `-1` 时默认使用 256。修改参考 Metal kernel 后，
运行 `python scripts/generate_cuda_port.py` 可同步重新生成 CUDA 实现。

<p>
  <img src="docs/figures/bootstrap_case1.png" width="32%">
  <img src="docs/figures/bootstrap_case2.png" width="32%">
  <img src="docs/figures/bootstrap_case3.png" width="32%">
</p>

`FastRW`（算法 1 + 2）结合 FEM 先验与残差随机游走，通过路径尾段复用做
逆方差融合。`FasterRW`（算法 1 + 2 + 3）在此基础上加入先验误差坐标下的
通用克里金高斯过程精修。本仓库可基于预计算的 COMSOL 先验 + 一键脚本，
完整复现 TCAD 论文中的所有表格与图。

---

## 目录

- [快速开始](#快速开始)
- [预期结果](#预期结果)
- [仓库结构](#仓库结构)
- [复现流程](#复现流程)
- [分阶段手动调用](#分阶段手动调用)
- [配置说明](#配置说明)
- [重新生成 COMSOL 先验](#重新生成-comsol-先验)
- [硬件与平台说明](#硬件与平台说明)
- [许可证](#许可证)
- [引用](#引用)

---

## 快速开始

完整复现（Table 1 + Tables tab:{multi,tradeoff,weakprior,time} +
Fig. bootstrap + HTML 报告）在 Apple M 系列上使用随附 Phase-1 长 MC
artifacts 时**约 1 分钟**；如从头跑 Phase 1 约 **12 分钟**。

```bash
# 1. 克隆仓库 + 创建 conda 环境（环境名: fastrw）
git clone https://github.com/ShiningSord/ResRW.git
cd ResRW
conda env create -f environment.yml
conda activate fastrw

# 2. 一键复现（首次运行会自动解压 repo 中的 artifact zip）
./reproduce.sh
```

复现完成后在浏览器中打开 `outputs/report.html` —— 这是一个自包含的
HTML 文件，所有表格已渲染、所有 bootstrap 图已 base64 内嵌。

如果你想手动解压 artifact zip（例如在跑任何东西之前查看
`data/` / `outputs/` 内容）：

```bash
./scripts/fetch_artifacts.sh
```

---

## 预期结果

`reproduce.sh` 在 Apple Silicon Metal 上可逐比特复现论文中的所有表格
和图。`outputs/report.html` 中的关键指标应当与下面一致：

**Table 1 —— 等精度下相对 PIRW 的工作量（N·steps）加速比**

|   | ε = 0.4 K | ε = 0.5 K |
| - | --------- | --------- |
| Case 1 FastRW   | 5.2× | 5.2× |
| Case 1 FasterRW | **8.7×**  | **10.5×** |
| Case 2 FastRW   | 5.2× | 5.2× |
| Case 2 FasterRW | **10.5×** | **8.7×** |
| Case 3 FastRW   | 3.7× | 4.2× |
| Case 3 FasterRW | **24.5×** | **28.0×** |

**tab:time（Case 1，ε = 0.4 K，墙钟分解）** —— FasterRW 端到端
**> 7.61×** PIRW（FastRW > 4.88×）。随机游走阶段是主要成本：
PIRW 5.79 s vs FastRW 1.11 s vs FasterRW 0.66 s per query；
FEM 先验摊销成本 < 0.06 s/query。

**tab:multi（Case 1，N = 1000）** —— FasterRW 的每点等效路径数加速比
从 1.00×（G=1）增长到 **3.79× ± 0.90**（G=16）；FastRW 从 1.00×
增长到 1.85× ± 0.25。

**tab:tradeoff（Case 1）** —— 随着先验改善，随机游走的每点墙钟时间
从 2.14 s（DoF=699，ε_max=8.71 K，Λ=0.013）下降到 **1.19 s**
（DoF=10254，ε_max=1.26 K，Λ=0.090）。

**tab:weakprior（Case 1，ε = 0.4 K）** —— 即便使用刻意粗糙的
"环境温度均匀场" 先验（ε_max = 43.7 K），FastRW 仍能取得 1.66×
墙钟加速、FasterRW 取得 3.32× 墙钟加速。

**Fig. bootstrap** —— 每个 case 三条单调下降的 avg|err| 曲线
（PIRW > FastRW > FasterRW），在 Table 1 所选工作点处标有标记。

`outputs/report.html` 中的数字如与上表不一致，即视为回归。

---

## 仓库结构

```
ResRW/
├── README.md, README.zh.md, LICENSE, CMakeLists.txt, environment.yml
├── reproduce.sh                  一键 Phase 1 -> 2 -> 3 -> 4 驱动脚本
├── comsol.sh                     一键重新生成 COMSOL 先验（需要 COMSOL）
├── resrw-artifacts-v1.zip        预计算先验 + Phase-1 MC（58 MB）
│
├── src/                          C++17 随机游走核心
│   ├── main.cpp, main_metal.cpp  CPU 与 Metal 入口
│   ├── walker.cpp, walker_metal.mm
│   ├── geometry.cpp, simulation_config.cpp
├── include/                      头文件
├── third_party/nlohmann/         vendored JSON
│
├── scripts/                      已整理的一键流程脚本与辅助工具
│   ├── build_and_run_metal.sh    GPU MC 执行器（由 run_*_direct.sh 调用）
│   ├── build_and_run.sh          CPU 备选（Linux 可用，便携）
│   ├── run_pirw_direct.sh        Phase 1: PIRW 蒙特卡洛（N_max=4096）
│   ├── run_fastrw_direct.sh      Phase 1: FastRW 蒙特卡洛（N_max=8192）
│   ├── run_pirw_post.{sh,js}     Phase 2: PIRW bootstrap（论文锁定 N）
│   ├── run_fastrw_post.{sh,js}   Phase 2: FastRW bootstrap（算法 1+2）
│   ├── run_fasterrw_post.{sh,js} Phase 2: FasterRW bootstrap（算法 1+2+3）
│   ├── run_bootstrap_sweep.{sh,js}  Phase 3: 密集 N 扫 + Fig. bootstrap
│   ├── plot_bootstrap_curves.py     Phase 3: bootstrap_case{1,2,3}.{png,pdf}
│   ├── run_group_size_sweep.{sh,js} Phase 3: tab:multi
│   ├── run_prior_dof_sweep.{sh,js}  Phase 3: tab:tradeoff
│   ├── run_weak_prior.{sh,js}       Phase 3: tab:weakprior
│   ├── run_wallclock_breakdown.{sh,js} Phase 3: tab:time
│   ├── build_table1_bootstrap.js    Phase 3: 从 sweep 生成 Markdown Table 1
│   ├── build_html_report.py         Phase 4: 自包含的 outputs/report.html
│   ├── fetch_artifacts.sh           原地解压 artifact 压缩包
│   ├── run_comsol_case3_rebuild.sh  单次 (case, mesh) 的 COMSOL 求解器
│   ├── comsol_case3_rebuild.java    上面脚本使用的 COMSOL Java 模型
│   └── _lib.js                      共享 JS 工具函数
│
├── configs/
│   ├── tcad_table1/                 三个 case 的标准配置（Phase 1、2）
│   │   ├── pirw_case{1,2,3}.json    PIRW（无尾段修正）
│   │   └── fastrw_case{1,2,3}.json  FastRW（开启尾段修正）
│   ├── tcad_table_tradeoff/         tab:tradeoff 三种 DoF 配置
│   └── tcad_table_weakprior/        tab:weakprior 弱先验配置
│
├── docs/figures/                    入库的 Fig. bootstrap PNG
├── data/                            由 reproduce.sh 从 artifact zip 解压填充
└── outputs/                         由 reproduce.sh 填充
```

---

## 复现流程

```
                     reproduce.sh
                            |
                  (首次运行自动解压 resrw-artifacts-v1.zip)
                            |
                            v
            +---------------+---------------+
            |   data/cases/case{1,2,3}/      |
            |   outputs/tcad_table1/...      |
            +---------------+---------------+
                            |
                            v
        ===================== Phase 1 =====================
                            |  (如已就绪则自动跳过)
            run_pirw_direct.sh    --> outputs/tcad_table1/pirw_case{1,2,3}/
            run_fastrw_direct.sh  --> outputs/tcad_table1/fastrw_case{1,2,3}/
                            |
        ===================== Phase 2 =====================
                            |
            run_pirw_post.sh      \
            run_fastrw_post.sh     >  outputs/tcad_table1/paper_results/
            run_fasterrw_post.sh  /          case*_*_eps{0.4,0.5}.json
                            |
        ===================== Phase 3 =====================
                            |
            run_bootstrap_sweep.sh         bootstrap_sweep_*.json + Fig. bootstrap
            run_group_size_sweep.sh        case1_group_sweep.json     (tab:multi)
            run_prior_dof_sweep.sh         case1_dof_sweep.json       (tab:tradeoff)
              --skip-fem --skip-mc          (使用随包发布的 Phase-3 MC + 计时文件)
            run_weak_prior.sh              case1_weakprior_summary.json (tab:weakprior)
              --skip-mc                     (使用随包发布的 Λ=1e-3 MC)
            run_wallclock_breakdown.sh     case1_eps04_wallclock.json (tab:time)
                            |
        ===================== Phase 4 =====================
                            |
            build_html_report.py  --> outputs/report.html
```

`reproduce.sh` 命令行参数：

| 参数 | 作用 |
| ---- | ---- |
| `--cases=1,2,3` | 限定 case 子集（仅作用于 Phase 1 + 2）。 |
| `--force-phase1` | 即使已有 MC 产物也强制重跑 Phase 1。 |
| `--skip-phase3` | 跳过四个子实验和 bootstrap 扫频图。 |
| `--skip-report` | 跳过最后的 `outputs/report.html` 构建。 |

---

## 分阶段手动调用

每个辅助脚本都支持 `--help`（或 `-h`）查看完整契约。常用配方如下。

### Phase 1 —— Metal 蒙特卡洛

```bash
./scripts/run_pirw_direct.sh        # 三个 case，N=4096 条路径
./scripts/run_pirw_direct.sh 2      # 只跑 case 2
./scripts/run_fastrw_direct.sh      # 三个 case，N=8192 条路径
```

每个 case 输出 `direct.csv`、`constraints.json`（被后处理消费的逐路径
状态流）、`summary.json` 以及 `last_*.log`。

### Phase 2 —— 论文锁定 N 的 bootstrap

```bash
./scripts/run_pirw_post.sh          # 所有 case 和 eps
./scripts/run_fastrw_post.sh        # 算法 1+2
./scripts/run_fasterrw_post.sh      # 算法 1+2+3
```

每个 `(case, method, eps)` 单元用 **B=500** 次 bootstrap 评估，结果存于
`outputs/tcad_table1/paper_results/case{1,2,3}_{pirw,fastrw,fasterrw}_eps{0.4,0.5}.json`。

### Phase 3 —— 子实验

```bash
./scripts/run_bootstrap_sweep.sh                 # 密集 N 扫频 + Fig. bootstrap
./scripts/run_group_size_sweep.sh                # tab:multi  (Case 1)
./scripts/run_prior_dof_sweep.sh --skip-fem --skip-mc   # tab:tradeoff (无需 COMSOL)
./scripts/run_weak_prior.sh --skip-mc            # tab:weakprior
./scripts/run_wallclock_breakdown.sh             # tab:time
```

### Phase 4 —— HTML 报告

```bash
python3 scripts/build_html_report.py
open outputs/report.html
```

---

## 配置说明

`configs/` 下所有配置共享同一 schema。温度输入按用途拆分：

```json
{
  "data": {
    "power_density_path":        "../../data/cases/<case>/power.bin",
    "prior_temperature_path":    "../../data/cases/<case>/comsol/comso_<dof>/temp.bin",
    "reference_temperature_path":"../../data/cases/<case>/comsol/comso_full/temp.bin",
    "temperature_offset": 0
  }
}
```

- `prior_temperature_path`：FastRW 尾段修正使用的 FEM 先验温度场；
  PIRW 配置中 `walker.use_tail_correction: false`，会忽略该字段。
- `reference_temperature_path`：仅用于报告误差的金标准
  （在 `direct.csv` 中作为 `GT_Temperature` 列）。

`run.seed = 42` 全局一致。给定相同 seed、相同 threadgroup 数、相同二进制，
Metal kernel 输出可复现。

### 温度单位

`data/cases/*/comsol/*/` 和 `rule_of_thumb/` 下的 `temp.bin` **以摄氏度
存储**。C++ kernel 内部已处理环境温度扣减；配置中的 `temperature_offset`
是在游走结束后叠加的开尔文偏移。

---

## 重新生成 COMSOL 先验

Artifact 压缩包中已包含复现流程消费的所有 COMSOL 先验，**无需 COMSOL
授权**就能复现论文。如果你装有 COMSOL Multiphysics 6.2 并希望从零
重建 FEM 先验温度场，运行：

```bash
./comsol.sh                 # 重建所有 (case, dof) 先验（含已保存 mesh 参数的）
./comsol.sh --cases=1       # 仅 case 1
./comsol.sh --dry-run       # 打印要调用的 COMSOL 命令但不执行
COMSOL_BIN=/path/to/comsol ./comsol.sh
```

`comsol.sh` 遍历每个 `data/cases/case{1,2,3}/comsol/comso_<dof>/` 目录，
从其 `metadata.json` 读取 mesh 参数，通过
`scripts/run_comsol_case3_rebuild.sh` 重新求解。每次求解结束后，
COMSOL 输出的 `heat_layer_cell_center_temperatures.bin` 会被复制为
`temp.bin`。`comso_full/` 会被跳过 —— 它是外部提供的金标准温度场，
不由本流程生成。

默认 COMSOL CLI 路径为
`/Applications/COMSOL62/Multiphysics/bin/comsol`；可用 `COMSOL_BIN`
环境变量覆盖。

---

## 硬件与平台说明

- **推荐：** Apple Silicon Mac（M1 或更高）。Metal kernel 在
  **Apple M5 Pro** 上开发和基准测试。
- **Linux / 非 Apple：** `scripts/build_and_run.sh` 可在任何支持
  C++17 + threads 的 POSIX 平台上构建 CPU 版 `random_walker`，但
  速度比 Metal 慢约 **30–60 倍**。CPU 目标不再针对论文锁定配置维护，
  仅适用于开发期烟雾测试。
- **Node.js：** 所有后处理用纯 stdlib Node（`>= 18`）。**无需** 运行
  `npm install`。
- **Python：** 仅依赖 `numpy` 与 `matplotlib`（已写入
  `environment.yml`）。
- **COMSOL：** 复现流程**无需 COMSOL 授权**。artifact 压缩包中已包含
  流程消费的所有先验温度场。如需从零重建见
  [重新生成 COMSOL 先验](#重新生成-comsol-先验)。

### Bit-level 可复现性注意事项

- Metal kernel 在给定 GPU + Metal 二进制下是确定性的，但不同 GPU
  之间可能存在几个 ULP 的差异。
- 后处理完全确定（纯 Node，无浮点原子操作）。
- Bootstrap 种子由 `(seed_base, B, trial)` 决定性派生。

---

## 许可证

MIT —— 详见 [LICENSE](LICENSE)。

---

## 引用

如果你使用或引用本项目，请引用 FastRW 论文：

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
