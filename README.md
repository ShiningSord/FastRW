# FastRW / FasterRW

[中文](README.zh.md)

This repository contains the code and experiments for **FastRW (DATE 2026)**
and the **FasterRW preprint**, for steady-state thermal analysis using random
walks. FastRW uses an FEM temperature field to reduce the cost of random-walk
estimation; FasterRW adds Gaussian-process refinement. The solver is written
in C++17 with an Apple Metal backend.

<p>
  <img src="docs/figures/bootstrap_case1.png" width="32%">
  <img src="docs/figures/bootstrap_case2.png" width="32%">
  <img src="docs/figures/bootstrap_case3.png" width="32%">
</p>

## Reproduce the experiments

Use an Apple Silicon Mac for the Metal experiments. You will need Conda and,
if rerunning the solver, the Xcode Command Line Tools (`xcode-select --install`).
The Conda environment includes CMake, Node.js, Python, NumPy, and Matplotlib.

```bash
git clone https://github.com/ShiningSord/ResRW.git
cd ResRW
conda env create -f environment.yml
conda activate fastrw

./reproduce.sh
open outputs/report.html
```

The repository includes COMSOL temperature fields and precomputed Monte Carlo
results in `resrw-artifacts-v1.zip`. The script extracts them on first use,
reuses the Monte Carlo results, and runs the post-processing to generate the
tables, curves, and HTML report. **COMSOL is not required for this workflow.**

The report is saved to `outputs/report.html`; experiment data and figures are
under `outputs/`. Runtime depends on the machine and whether Monte Carlo
results are reused.

### Rerun the random walks

To recompute the main experiments instead of reusing their Monte Carlo results:

```bash
./reproduce.sh --force-phase1
```

This reruns the PIRW and FastRW random walks for the selected cases, then
regenerates the downstream results, including FasterRW. It does **not** rebuild
COMSOL fields or rerun the Monte Carlo simulations for the prior-resolution and
weak-prior experiments; those still use the supplied data.

Other useful options:

```bash
./reproduce.sh --cases=1       # Run case 1 only
./reproduce.sh --skip-phase3  # Skip the bootstrap sweep and additional experiments
./reproduce.sh --skip-report  # Run without generating the HTML report
./reproduce.sh --help
```

Options can be combined. The group-size, prior-resolution, weak-prior, and
timing experiments run only when case 1 is selected. Numerical results from a
fresh solver run can vary across GPUs and builds; timings depend on hardware.

## Working with the code

The solver is in `src/` and `include/`, experiment settings are in `configs/`,
and the scripts called by `reproduce.sh` are in `scripts/`. To run an individual
stage, use the corresponding command in `reproduce.sh`. To rebuild only the
report from existing results:

```bash
python3 scripts/build_html_report.py
```

If you want to rebuild the FEM priors, install COMSOL Multiphysics 6.2 and run:

```bash
./comsol.sh --dry-run  # Inspect the planned runs
./comsol.sh            # Rebuild priors using the saved mesh parameters
```

Set `COMSOL_BIN=/path/to/comsol` if COMSOL is installed outside the default
macOS location. This script does not rebuild the supplied reference temperature
fields.

The CPU runner, `scripts/build_and_run.sh`, is available for development but is
not maintained for the paper reproduction workflow. An experimental Windows /
NVIDIA CUDA backend is also available; it has not been rigorously tested by the
maintainers. See the [Windows guide](windows.md) for setup and limitations.

## Citation

For FastRW (DATE 2026):

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

## License

[MIT](LICENSE).
