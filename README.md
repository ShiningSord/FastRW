# FastRW

Feynman-Kac-based GPU random-walk solver and experiment harness for
steady-state thermal problems with mixed boundary conditions, featuring
the **FastRW / FasterRW** algorithms (NVIDIA CUDA on Windows, Apple Metal,
and portable C++17).

## Windows + NVIDIA CUDA quick start

For a complete clean-machine setup and reproduction walkthrough, see
[windows.md](windows.md).

The Windows backend requires an NVIDIA GPU, the CUDA Toolkit, and Visual
Studio 2019/2022 Build Tools with the **Desktop development with C++**
workload. CUDA 11.3 and compute capability 8.6 are suitable for an RTX 3050
Ti. From PowerShell:

```powershell
# Create the environment at E:\FastRW (only needed once).
conda env create --prefix E:\FastRW -f environment-windows.yml
conda activate E:\FastRW

# Extract the bundled data and run a small CUDA smoke test.
.\scripts\fetch_artifacts.ps1
.\scripts\build_and_run_cuda.ps1 `
  .\configs\tcad_table1\fastrw_case1.json 2 256

# Full Phase-1 CUDA runs (8192 FastRW or 4096 PIRW paths per point).
.\scripts\run_fastrw_direct.ps1 1
.\scripts\run_pirw_direct.ps1 1
```

`build_and_run_cuda.ps1` automatically imports the Visual Studio compiler
environment, configures CMake/NMake, builds `random_walker_cuda.exe`, runs it,
and writes the same CSV, constraints JSON, diagnostics JSON, log, and summary
formats as the Metal backend. The fourth executable argument is CUDA threads
per block (`-1` selects 256). To regenerate the CUDA translation after editing
the reference Metal kernel, run `python scripts/generate_cuda_port.py`.

[中文 README](README.zh.md)

<p>
  <img src="docs/figures/bootstrap_case1.png" width="32%">
  <img src="docs/figures/bootstrap_case2.png" width="32%">
  <img src="docs/figures/bootstrap_case3.png" width="32%">
</p>

`FastRW` (Alg. 1 + 2) couples an FEM prior with a residual random walk
that reuses correlated path tails for inverse-variance fusion. `FasterRW`
(Alg. 1 + 2 + 3) adds a universal-kriging Gaussian-process refinement in
prior-error coordinates. This repository reproduces every table and
figure in the accompanying TCAD paper from precomputed COMSOL priors and
a single one-key driver.

---

## Contents

- [Quick start](#quick-start)
- [Expected results](#expected-results)
- [Layout](#layout)
- [Reproduction flow](#reproduction-flow)
- [Manual per-phase invocation](#manual-per-phase-invocation)
- [Configuration](#configuration)
- [Re-generating COMSOL priors](#re-generating-comsol-priors)
- [Hardware and platform notes](#hardware-and-platform-notes)
- [License](#license)
- [Citation](#citation)

---

## Quick start

The full reproduction (Table 1 + Tables tab:{multi,tradeoff,weakprior,time} +
Fig. bootstrap + HTML summary) runs in **about 1 minute on Apple M-series**
when the shipped Phase-1 long-MC artifacts are used, or **~12 minutes**
if you re-run Phase 1 from scratch.

```bash
# 1. Clone and set up the conda env (env name: fastrw)
git clone https://github.com/ShiningSord/ResRW.git
cd ResRW
conda env create -f environment.yml
conda activate fastrw

# 2. One-key reproduction (auto-extracts the in-repo artifact zip on first run)
./reproduce.sh
```

Open `outputs/report.html` in any browser — it is a single self-contained
HTML file with every table rendered and every bootstrap figure embedded.

If you want to extract the artifact zip manually (e.g. inspect the
`data/` and `outputs/` payload before running anything):

```bash
./scripts/fetch_artifacts.sh
```

---

## Expected results

`reproduce.sh` reproduces every table and figure in the paper bit-for-bit
(on Apple-Silicon Metal) from the shipped Phase-1 MC. The headline
numbers in `outputs/report.html` should be:

**Table 1 — iso-accuracy speedup (N·steps over PIRW)**

|   | ε = 0.4 K | ε = 0.5 K |
| - | --------- | --------- |
| Case 1 FastRW   | 5.2× | 5.2× |
| Case 1 FasterRW | **8.7×**  | **10.5×** |
| Case 2 FastRW   | 5.2× | 5.2× |
| Case 2 FasterRW | **10.5×** | **8.7×** |
| Case 3 FastRW   | 3.7× | 4.2× |
| Case 3 FasterRW | **24.5×** | **28.0×** |

**tab:time (Case 1, ε = 0.4 K, wallclock breakdown)** — FasterRW >
**7.61×** end-to-end over PIRW (FastRW > 4.88×). Random-walk stage is
the dominant cost: PIRW 5.79 s vs FastRW 1.11 s vs FasterRW 0.66 s
per query; FEM-prior amortized cost is < 0.06 s/query.

**tab:multi (Case 1, N = 1000)** — FasterRW per-query equivalent
path-count grows from 1.00× (G=1) to **3.79× ± 0.90** (G=16); FastRW
from 1.00× to 1.85× ± 0.25.

**tab:tradeoff (Case 1)** — RW per-query wallclock drops from 2.14 s
(DoF=699, ε_max=8.71 K, Λ=0.013) to **1.19 s** (DoF=10254, ε_max=1.26 K,
Λ=0.090) as the prior improves.

**tab:weakprior (Case 1, ε = 0.4 K)** — Even with a deliberately crude
uniform-at-ambient prior (ε_max = 43.7 K), FastRW still gets
1.66× and FasterRW 3.32× wallclock speedup over PIRW.

**Fig. bootstrap** — three monotone-decreasing avg|err| curves per
case (PIRW > FastRW > FasterRW), with markers at the chosen
operating point of Table 1.

Any deviation in `outputs/report.html` from these numbers is a regression.

---

## Layout

```
ResRW/
├── README.md, README.zh.md, LICENSE, CMakeLists.txt, environment.yml
├── reproduce.sh                  one-key Phase 1 -> 2 -> 3 -> 4 driver
├── comsol.sh                     one-key COMSOL prior re-generation (needs COMSOL)
├── resrw-artifacts-v1.zip        precomputed priors + Phase-1 MC (58 MB)
│
├── src/                          C++17 random-walk core
│   ├── main.cpp, main_metal.cpp  CPU and Metal entrypoints
│   ├── walker.cpp, walker_metal.mm
│   ├── geometry.cpp, simulation_config.cpp
├── include/                      headers
├── third_party/nlohmann/         vendored JSON
│
├── scripts/                      curated one-key flow + helpers
│   ├── build_and_run_metal.sh    GPU MC executor (called by run_*_direct.sh)
│   ├── build_and_run.sh          CPU fallback (portable; Linux-compatible)
│   ├── run_pirw_direct.sh        Phase 1: PIRW Monte Carlo (N_max=4096)
│   ├── run_fastrw_direct.sh      Phase 1: FastRW Monte Carlo (N_max=8192)
│   ├── run_pirw_post.{sh,js}     Phase 2: PIRW bootstrap at paper-locked N
│   ├── run_fastrw_post.{sh,js}   Phase 2: FastRW bootstrap (Alg. 1+2)
│   ├── run_fasterrw_post.{sh,js} Phase 2: FasterRW bootstrap (Alg. 1+2+3)
│   ├── run_bootstrap_sweep.{sh,js}  Phase 3: dense N-grid sweep + Fig. bootstrap
│   ├── plot_bootstrap_curves.py     Phase 3: bootstrap_case{1,2,3}.{png,pdf}
│   ├── run_group_size_sweep.{sh,js} Phase 3: tab:multi
│   ├── run_prior_dof_sweep.{sh,js}  Phase 3: tab:tradeoff
│   ├── run_weak_prior.{sh,js}       Phase 3: tab:weakprior
│   ├── run_wallclock_breakdown.{sh,js} Phase 3: tab:time
│   ├── build_table1_bootstrap.js    Phase 3: markdown Table 1 from sweep
│   ├── build_html_report.py         Phase 4: self-contained outputs/report.html
│   ├── fetch_artifacts.sh           extract artifact zip in place
│   ├── run_comsol_case3_rebuild.sh  invoke COMSOL solve for one (case, mesh)
│   ├── comsol_case3_rebuild.java    COMSOL Java model used by the above
│   └── _lib.js                      shared JS helpers
│
├── configs/
│   ├── tcad_table1/                 canonical 3-case configs (Phase 1, 2)
│   │   ├── pirw_case{1,2,3}.json    PIRW (no tail correction)
│   │   └── fastrw_case{1,2,3}.json  FastRW (tail correction on)
│   ├── tcad_table_tradeoff/         3 DoF levels for tab:tradeoff
│   └── tcad_table_weakprior/        rule-of-thumb prior for tab:weakprior
│
├── docs/figures/                    committed PNGs of Fig. bootstrap
├── data/                            populated by reproduce.sh from the artifact zip
└── outputs/                         populated by reproduce.sh
```

---

## Reproduction flow

```
                     reproduce.sh
                            |
                  (auto-extracts resrw-artifacts-v1.zip on first run)
                            |
                            v
            +---------------+---------------+
            |   data/cases/case{1,2,3}/      |
            |   outputs/tcad_table1/...      |
            +---------------+---------------+
                            |
                            v
        ===================== Phase 1 =====================
                            |  (auto-skipped if shipped MC outputs present)
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
              --skip-fem --skip-mc          (uses shipped Phase-3 MC + timing files)
            run_weak_prior.sh              case1_weakprior_summary.json (tab:weakprior)
              --skip-mc                     (uses shipped Lambda=1e-3 MC)
            run_wallclock_breakdown.sh     case1_eps04_wallclock.json (tab:time)
                            |
        ===================== Phase 4 =====================
                            |
            build_html_report.py  --> outputs/report.html
```

`reproduce.sh` flags:

| Flag | Effect |
| ---- | ------ |
| `--cases=1,2,3` | Restrict to a subset of cases (Phases 1 + 2). |
| `--force-phase1` | Re-run Phase 1 even if shipped MC outputs are present. |
| `--skip-phase3` | Skip the four sub-experiments and the bootstrap-sweep figure. |
| `--skip-report` | Skip the `outputs/report.html` build at the end. |

---

## Manual per-phase invocation

Every helper accepts `--help` (or `-h`) for its full contract. Typical
recipes follow.

### Phase 1 — Metal Monte Carlo

```bash
./scripts/run_pirw_direct.sh        # all three cases, N=4096 paths
./scripts/run_pirw_direct.sh 2      # case 2 only
./scripts/run_fastrw_direct.sh      # all three cases, N=8192 paths
```

Each case writes `direct.csv`, `constraints.json` (the per-path state
stream consumed by post-processing), `summary.json`, and a `last_*.log`.

### Phase 2 — paper-locked-N bootstrap

```bash
./scripts/run_pirw_post.sh          # all cases, both eps
./scripts/run_fastrw_post.sh        # Alg. 1+2
./scripts/run_fasterrw_post.sh      # Alg. 1+2+3
```

Each `(case, method, eps)` cell is computed with **B=500** bootstrap
trials. Outputs land at
`outputs/tcad_table1/paper_results/case{1,2,3}_{pirw,fastrw,fasterrw}_eps{0.4,0.5}.json`.

### Phase 3 — sub-experiments

```bash
./scripts/run_bootstrap_sweep.sh                 # dense N grid + Fig. bootstrap
./scripts/run_group_size_sweep.sh                # tab:multi  (Case 1)
./scripts/run_prior_dof_sweep.sh --skip-fem --skip-mc   # tab:tradeoff (no COMSOL)
./scripts/run_weak_prior.sh --skip-mc            # tab:weakprior
./scripts/run_wallclock_breakdown.sh             # tab:time
```

### Phase 4 — HTML report

```bash
python3 scripts/build_html_report.py
open outputs/report.html
```

---

## Configuration

Every config under `configs/` has the same schema. Temperature inputs
are split by role:

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

- `prior_temperature_path` is the FEM-prior temperature field used by
  FastRW's tail correction; PIRW configs set
  `walker.use_tail_correction: false` and ignore the prior.
- `reference_temperature_path` is the ground-truth field used **only**
  for metric reporting (`GT_Temperature` in `direct.csv`).

`run.seed = 42` everywhere. The Metal kernel is deterministic given
the same seed, threadgroup count, and binary.

### Temperature units

`temp.bin` files in `data/cases/*/comsol/*/` and `rule_of_thumb/` are
stored **in Celsius**. The C++ kernel handles ambient subtraction
internally; `temperature_offset` in the config is an additive K offset
applied after the walk.

---

## Re-generating COMSOL priors

The artifact zip ships every COMSOL prior the reproduction flow needs,
so a COMSOL license is **not** required to reproduce the paper. If you
do have COMSOL Multiphysics 6.2 installed and want to regenerate the
FEM-prior temperature fields from scratch, run:

```bash
./comsol.sh                 # rebuild every (case, dof) we have mesh params for
./comsol.sh --cases=1       # restrict to case 1
./comsol.sh --dry-run       # print planned COMSOL invocations and exit
COMSOL_BIN=/path/to/comsol ./comsol.sh
```

`comsol.sh` iterates over each shipped `data/cases/case{1,2,3}/comsol/comso_<dof>/`
directory, reads the mesh parameters from its `metadata.json`, and replays
them via `scripts/run_comsol_case3_rebuild.sh`. After each solve the
COMSOL output `heat_layer_cell_center_temperatures.bin` is aliased back
to `temp.bin`. `comso_full/` is skipped — it is an externally-supplied
ground-truth field, not produced by this pipeline.

The default COMSOL CLI path is
`/Applications/COMSOL62/Multiphysics/bin/comsol`; override with
`COMSOL_BIN`.

---

## Hardware and platform notes

- **Recommended:** Apple Silicon Mac (M1 or later). The Metal kernel
  was developed and benchmarked on **Apple M5 Pro**.
- **Linux / non-Apple:** `scripts/build_and_run.sh` builds the CPU
  `random_walker` target on any POSIX system with C++17 + threads, but
  the runs are roughly **30–60×** slower than Metal. The CPU target is
  unmaintained for paper-locked configs; use it only for development
  smoke tests.
- **Node.js:** all post-processing is pure stdlib Node (`>= 18`).
  There is **no** `npm install` step.
- **Python:** only `numpy` and `matplotlib` are required (in
  `environment.yml`).
- **COMSOL:** the reproduction flow **does not require a COMSOL
  license**. The artifact archive ships every prior temperature field
  the pipeline consumes. See [Re-generating COMSOL priors](#re-generating-comsol-priors)
  if you want to rebuild them.

### Bit-level reproducibility caveats

- The Metal kernel is deterministic on a given GPU + Metal binary, but
  cross-GPU outputs may differ by a few ULPs.
- Post-processing is fully deterministic (pure Node, no FP atomics).
- Bootstrap seeds derive deterministically from `(seed_base, B, trial)`.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Citation

If you use or cite this repository, please cite the FastRW paper:

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
