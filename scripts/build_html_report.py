#!/usr/bin/env python3
"""Build a single self-contained HTML report summarizing every paper
table + figure that the reproduce.sh pipeline produces.

Inputs (all under outputs/):
  tcad_table1/paper_results/case{1,2,3}_{pirw,fastrw,fasterrw}_eps{0.4,0.5}.json
  tcad_table1/{fastrw,pirw}_case{1,2,3}/bootstrap_sweep_*.json
  tcad_table1/bootstrap_case{1,2,3}.png
  tcad_table_multi/case1_group_sweep.json
  tcad_table_tradeoff/case1_dof_sweep.json
  tcad_table_weakprior/case1_weakprior_summary.json
  tcad_table_time/case1_eps04_wallclock.json

Output:
  outputs/report.html       single file, PNGs base64-embedded
"""
from __future__ import annotations

import base64
import datetime as dt
import html
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"

CASES = [
    ("1", "Case 1 (power6, 500/100/500 um, h=8700)"),
    ("2", "Case 2 (4-core, 1000/100/1000 um, h=8700)"),
    ("3", "Case 3 (16-core, 500/100/1000 um, h=4900)"),
]
METHODS = ["pirw", "fastrw", "fasterrw"]
METHOD_LABELS = {"pirw": "PIRW", "fastrw": "FastRW", "fasterrw": "FasterRW"}
EPS_VALUES = [0.5, 0.4]


def load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    with path.open() as f:
        return json.load(f)


def mean_std(values: list[float]) -> tuple[float, float]:
    n = len(values)
    if n == 0:
        return (math.nan, math.nan)
    m = sum(values) / n
    if n < 2:
        return (m, 0.0)
    var = sum((v - m) ** 2 for v in values) / (n - 1)
    return (m, math.sqrt(var))


def git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return "unknown"


def embed_png(path: Path) -> str:
    if not path.is_file():
        return f'<em>missing: {html.escape(str(path.relative_to(ROOT)))}</em>'
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<img src="data:image/png;base64,{b64}" alt="{path.name}">'


# ---------------------------------------------------------------------------
# Table 1: main results (paper-locked N per (case, method, eps))
# ---------------------------------------------------------------------------
def build_table1() -> str:
    paper_results = OUT / "tcad_table1" / "paper_results"

    # mean_avg_steps per case, for speedup computation
    steps = {}
    for case_id, _ in CASES:
        sweep_fast = load_json(OUT / "tcad_table1" / f"fastrw_case{case_id}" / "bootstrap_sweep_fastrw.json")
        sweep_pirw = load_json(OUT / "tcad_table1" / f"pirw_case{case_id}" / "bootstrap_sweep_pirw.json")
        steps[case_id] = {
            "fast": sweep_fast.get("mean_avg_steps") if sweep_fast else None,
            "pirw": sweep_pirw.get("mean_avg_steps") if sweep_pirw else None,
        }

    rows_html = []
    for eps in EPS_VALUES:
        rows_html.append(f'<tr class="eps-header"><th colspan="7">eps = {eps} K</th></tr>')
        rows_html.append(
            '<tr><th>Case</th>'
            '<th>PIRW N</th><th>PIRW mean &plusmn; std (K)</th>'
            '<th>FastRW N</th><th>FastRW mean &plusmn; std (speedup)</th>'
            '<th>FasterRW N</th><th>FasterRW mean &plusmn; std (speedup)</th></tr>'
        )
        for case_id, _ in CASES:
            cells = {}
            for method in METHODS:
                fp = paper_results / f"case{case_id}_{method}_eps{eps}.json"
                data = load_json(fp)
                if data is None:
                    cells[method] = None
                    continue
                trials = [t["avg_abs"] for t in data.get("trials", [])]
                m, s = mean_std(trials)
                cells[method] = {"N": data.get("N"), "mean": m, "std": s}

            def fmt_with_speedup(method: str) -> str:
                cell = cells.get(method)
                if cell is None:
                    return "&mdash;"
                ps_pirw = (cells["pirw"]["N"] * steps[case_id]["pirw"]) if cells.get("pirw") and steps[case_id]["pirw"] else None
                if method == "pirw":
                    return f'{cell["mean"]:.3f} &plusmn; {cell["std"]:.3f}'
                ps_method = cell["N"] * steps[case_id]["fast"] if steps[case_id]["fast"] else None
                if ps_pirw and ps_method:
                    sp = ps_pirw / ps_method
                    return f'{cell["mean"]:.3f} &plusmn; {cell["std"]:.3f} ({sp:.1f}&times;)'
                return f'{cell["mean"]:.3f} &plusmn; {cell["std"]:.3f}'

            def fmt_N(method: str) -> str:
                c = cells.get(method)
                return f'{c["N"]}' if c else '&mdash;'

            rows_html.append(
                f'<tr><td>Case {case_id}</td>'
                f'<td>{fmt_N("pirw")}</td><td>{fmt_with_speedup("pirw")}</td>'
                f'<td>{fmt_N("fastrw")}</td><td>{fmt_with_speedup("fastrw")}</td>'
                f'<td>{fmt_N("fasterrw")}</td><td>{fmt_with_speedup("fasterrw")}</td></tr>'
            )

    return (
        '<h2>Table 1 &mdash; Paths-to-reach-&epsilon; per (case, method)</h2>'
        '<p class="note">N is the smallest path count where the bootstrap mean of '
        '|err| reaches &epsilon; (B=500, seed=42). Speedup compares total path-steps '
        '(N &times; mean_steps) against PIRW on the same case.</p>'
        '<table>' + "".join(rows_html) + '</table>'
    )


# ---------------------------------------------------------------------------
# Bootstrap figures (Case 1/2/3)
# ---------------------------------------------------------------------------
def build_bootstrap_figs() -> str:
    parts = ['<h2>Fig. bootstrap &mdash; |err| vs N (B=500 bootstrap subsamples)</h2>',
             '<div class="fig-row">']
    for case_id, label in CASES:
        png = OUT / "tcad_table1" / f"bootstrap_case{case_id}.png"
        parts.append(f'<figure>{embed_png(png)}<figcaption>{html.escape(label)}</figcaption></figure>')
    parts.append('</div>')
    return "".join(parts)


# ---------------------------------------------------------------------------
# tab:multi -- group size sweep
# ---------------------------------------------------------------------------
def build_table_multi() -> str:
    data = load_json(OUT / "tcad_table_multi" / "case1_group_sweep.json")
    if data is None:
        return '<h2>Table tab:multi</h2><p><em>missing case1_group_sweep.json</em></p>'

    rows = ['<tr><th>G</th>'
            '<th>FastRW per-query speedup (mean &plusmn; std)</th>'
            '<th>FasterRW per-query speedup (mean &plusmn; std)</th></tr>']
    for g in data.get("groups", []):
        G = g.get("G")
        fastrw = g.get("fastrw", {})
        fasterrw = g.get("fasterrw", {})
        fmean = fastrw.get("per_query_speedup_mean", math.nan)
        fstd  = fastrw.get("per_query_speedup_std",  math.nan)
        Fmean = fasterrw.get("per_query_speedup_mean", math.nan)
        Fstd  = fasterrw.get("per_query_speedup_std",  math.nan)
        rows.append(
            f'<tr><td>{G}</td>'
            f'<td>{fmean:.2f} &plusmn; {fstd:.2f}</td>'
            f'<td>{Fmean:.2f} &plusmn; {Fstd:.2f}</td></tr>'
        )
    return (
        '<h2>Table tab:multi &mdash; Group-size speedup (Case 1, N=1000, B=500)</h2>'
        '<p class="note">Speedup at query x_i is Var_single / Var_fused; reported as '
        'the mean &plusmn; std across the M=16 query points. G=1 is the FastRW baseline '
        '(FasterRW degenerates to identity).</p>'
        '<table>' + "".join(rows) + '</table>'
    )


# ---------------------------------------------------------------------------
# tab:tradeoff -- FEM-prior DoF tradeoff
# ---------------------------------------------------------------------------
def build_table_tradeoff() -> str:
    data = load_json(OUT / "tcad_table_tradeoff" / "case1_dof_sweep.json")
    if data is None:
        return '<h2>Table tab:tradeoff</h2><p><em>missing case1_dof_sweep.json</em></p>'

    rows = ['<tr><th>DoF</th><th>max err (K)</th><th>avg err (K)</th>'
            '<th>&Lambda;</th><th>mean steps (M)</th>'
            '<th>FEM warm (s)</th><th>RW per query (s)</th></tr>']
    for r in data.get("rows", []):
        rows.append(
            f'<tr><td>{r.get("dof")}</td>'
            f'<td>{r.get("max_err_K"):.2f}</td>'
            f'<td>{r.get("avg_err_K"):.2f}</td>'
            f'<td>{r.get("lambda"):.3f}</td>'
            f'<td>{r.get("mean_steps_M"):.2f}</td>'
            f'<td>{r.get("fem_warm_seconds"):.2f}</td>'
            f'<td>{r.get("rw_per_query_seconds"):.2f}</td></tr>'
        )
    return (
        '<h2>Table tab:tradeoff &mdash; Prior DoF vs RW truncation (Case 1, N=1000)</h2>'
        '<p class="note">Three FEM-prior accuracy levels; &Lambda; chosen so that '
        '&Lambda; &times; max-prior-error stays &le; ~0.05 K.</p>'
        '<table>' + "".join(rows) + '</table>'
    )


# ---------------------------------------------------------------------------
# tab:weakprior -- rule-of-thumb prior robustness
# ---------------------------------------------------------------------------
def build_table_weakprior() -> str:
    data = load_json(OUT / "tcad_table_weakprior" / "case1_weakprior_summary.json")
    if data is None:
        return '<h2>Table tab:weakprior</h2><p><em>missing case1_weakprior_summary.json</em></p>'

    notes = data.get("notes", {})
    parts = [
        '<h2>Table tab:weakprior &mdash; Rule-of-thumb (uniform) prior at &epsilon;=0.4 K (Case 1)</h2>'
    ]

    rot_max = notes.get("rule_of_thumb_max_prior_error_K")
    if rot_max is not None:
        parts.append(
            f'<p class="note">Uniform prior at T_amb=20 &deg;C; max prior error = {rot_max:.1f} K. '
            f'MC re-run at &Lambda;=1e-3, N<sub>max</sub>={notes.get("mc_nmax_rot")}.</p>'
        )

    def sweep_table(title: str, key: str) -> str:
        rows = ['<tr><th>N</th><th>mean of |err| (K)</th><th>std (K)</th></tr>']
        for row in notes.get(key, []):
            rows.append(
                f'<tr><td>{row.get("N")}</td>'
                f'<td>{row.get("mean_avg_abs"):.3f}</td>'
                f'<td>{row.get("std_avg_abs"):.3f}</td></tr>'
            )
        return (
            f'<h3>{title}</h3>'
            '<table>' + "".join(rows) + '</table>'
        )

    parts.append(sweep_table("FastRW (Alg. 1+2) under rule-of-thumb prior", "fastrw_sweep"))
    parts.append(sweep_table("FasterRW (Alg. 1+2+3) under rule-of-thumb prior", "fasterrw_sweep"))
    return "".join(parts)


# ---------------------------------------------------------------------------
# tab:time -- wallclock breakdown
# ---------------------------------------------------------------------------
def build_table_time() -> str:
    all_data = load_json(OUT / "tcad_table_time" / "all_cases_wallclock.json")
    if all_data is not None:
        rows = [
            '<tr><th>Case</th><th>&epsilon; (K)</th><th>PIRW (s/query)</th>'
            '<th>FastRW (s/query; speedup)</th>'
            '<th>FasterRW (s/query; speedup)</th></tr>'
        ]
        for cell in all_data.get("cells", []):
            stages = cell.get("stages_per_query_s", {})
            speedup = cell.get("wallclock_speedup_vs_PIRW_lower_bound", {})
            pirw_s = stages.get("PIRW", {}).get("Total", math.nan)
            fast_s = stages.get("FastRW", {}).get("Total_upper_bound", math.nan)
            faster_s = stages.get("FasterRW", {}).get("Total_upper_bound", math.nan)
            rows.append(
                f'<tr><td>{cell.get("case", "").replace("case", "Case ")}</td>'
                f'<td>{cell.get("eps_target_K", math.nan):.1f}</td>'
                f'<td>{pirw_s:.3f}</td>'
                f'<td>&le; {fast_s:.3f}; &ge; {speedup.get("FastRW", math.nan):.3f}&times;</td>'
                f'<td>&le; {faster_s:.3f}; &ge; {speedup.get("FasterRW", math.nan):.3f}&times;</td></tr>'
            )
        return (
            '<h2>Table tab:time &mdash; Windows wall-clock results for all Table 1 cells</h2>'
            f'<p class="note">Device: {all_data.get("device", "unknown")}. '
            'The Nmax CUDA runtimes are measured on Windows and scaled linearly to each '
            'paper-selected N, following the original report methodology. Post-processing '
            'is the median of three measured runs. The FastRW/FasterRW totals include the '
            'conservative FEM prior bound (&lt;1 s per 16-query batch), so their times are '
            'upper bounds and the corresponding wall-clock speedups are lower bounds. '
            'These are wall-clock results, not N &times; mean-steps work ratios.</p>'
            '<table>' + "".join(rows) + '</table>'
        )

    data = load_json(OUT / "tcad_table_time" / "case1_eps04_wallclock.json")
    if data is None:
        return '<h2>Table tab:time</h2><p><em>missing case1_eps04_wallclock.json</em></p>'

    n = data.get("N", {})
    fem_per = data.get("fem_prior_per_query_s")
    fem_is_upper = data.get("fem_prior_is_upper_bound", False)
    fem_log_s = data.get("fem_prior_log_seconds")
    mc_pirw_total = data.get("mc_runtime_full_pirw_s")
    mc_pirw_nmax = data.get("mc_runtime_full_pirw_Nmax")
    mc_fast_total = data.get("mc_runtime_full_fastrw_s")
    mc_fast_nmax = data.get("mc_runtime_full_fastrw_Nmax")
    M = data.get("M", 16)
    pp = data.get("postproc_wallclock_s", {})

    def rw_per_query(method: str) -> float:
        N = n.get(method)
        if method == "PIRW":
            total, nmax = mc_pirw_total, mc_pirw_nmax
        else:
            total, nmax = mc_fast_total, mc_fast_nmax
        if total is None or nmax is None or N is None:
            return math.nan
        return total * N / nmax / M

    def pp_median(key: str) -> float:
        v = pp.get(key, {}).get("median")
        return v if v is not None else math.nan

    # Per-query stages
    pirw_fem  = fem_per if fem_per is not None else math.nan
    pirw_rw   = rw_per_query("PIRW")

    fast_fem  = pirw_fem
    fast_rw   = rw_per_query("FastRW")
    fast_post = pp_median(f"fastrw_post_N{n.get('FastRW')}") / M if pp_median(f"fastrw_post_N{n.get('FastRW')}") else math.nan

    Fast_fem  = pirw_fem
    Fast_rw   = rw_per_query("FasterRW")
    Fast_fastpost = pp_median(f"fastrw_post_N{n.get('FasterRW')}") / M if pp_median(f"fastrw_post_N{n.get('FasterRW')}") else math.nan
    Fast_kr_total = pp_median(f"fasterrw_post_N{n.get('FasterRW')}")
    Fast_kr = (Fast_kr_total - (Fast_fastpost * M)) / M if (Fast_kr_total and not math.isnan(Fast_fastpost)) else math.nan

    if fem_is_upper:
        fem_fast_disp = f'&lt; {fast_fem:.2f}'
        fem_faster_disp = f'&lt; {Fast_fem:.2f}'
    else:
        fem_fast_disp = f'{fast_fem:.3f}'
        fem_faster_disp = f'{Fast_fem:.3f}'

    rows = [
        '<tr><th>Stage</th><th>PIRW (s/query)</th><th>FastRW (s/query)</th><th>FasterRW (s/query)</th></tr>',
        f'<tr><td>FEM prior (linear solve)</td><td>&mdash;</td><td>{fem_fast_disp}</td><td>{fem_faster_disp}</td></tr>',
        f'<tr><td>Random walk</td><td>{pirw_rw:.3f}</td><td>{fast_rw:.3f}</td><td>{Fast_rw:.3f}</td></tr>',
        f'<tr><td>Tail-reuse fusion</td><td>&mdash;</td><td>{fast_post:.5f}</td><td>{Fast_fastpost:.5f}</td></tr>',
        f'<tr><td>Kriging refinement</td><td>&mdash;</td><td>&mdash;</td><td>{Fast_kr:.5f}</td></tr>',
    ]
    fem_note = ''
    if fem_is_upper:
        fem_note = (
            f' The FEM prior cost is reported as the COMSOL MUMPS linear-solve'
            f' time amortized over M=16 queries. The cold comsol_batch.log for'
            f' the canonical DoF=1288 prior logs the linear-solve line as'
            f' &ldquo;{fem_log_s} s&rdquo;; COMSOL\'s batch log only resolves to'
            f' integer seconds, so under the conservative truncation interpretation'
            f' the actual solve is strictly less than {fem_log_s + 1} s, i.e.'
            f' &lt; {(fem_log_s + 1)/M:.2f} s per query.'
        )
    return (
        '<h2>Table tab:time &mdash; Per-query wallclock breakdown '
        '(Case 1, &epsilon;=0.4 K, M=16)</h2>'
        f'<p class="note">N values: PIRW={n.get("PIRW")}, FastRW={n.get("FastRW")}, '
        f'FasterRW={n.get("FasterRW")}. Random-walk time scales linearly in N. '
        f'Post-proc reported as median of 3 runs.{fem_note}</p>'
        '<table>' + "".join(rows) + '</table>'
    )


# ---------------------------------------------------------------------------
# Page assembly
# ---------------------------------------------------------------------------
CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       max-width: 1100px; margin: 2em auto; padding: 0 1em; line-height: 1.4; color: #222; }
h1 { border-bottom: 2px solid #333; padding-bottom: 0.3em; }
h2 { margin-top: 2em; border-left: 4px solid #4a73c4; padding-left: 0.5em; }
h3 { margin-top: 1.5em; color: #444; }
table { border-collapse: collapse; margin: 0.5em 0 1em 0; }
th, td { border: 1px solid #bbb; padding: 4px 10px; text-align: left; font-size: 0.92em; }
th { background: #eef2f8; }
.eps-header th { background: #d8e3f3; text-align: center; }
tr:nth-child(even) td { background: #fafafa; }
.note { color: #555; font-size: 0.9em; }
.fig-row { display: flex; gap: 0.6em; flex-wrap: wrap; margin: 1em 0; }
.fig-row figure { flex: 1 1 30%; min-width: 200px; margin: 0; }
.fig-row figure img { width: 100%; height: auto; border: 1px solid #ddd; }
figcaption { font-style: italic; color: #555; margin-bottom: 0.3em;
             font-size: 0.85em; text-align: center; }
header { background: #f4f6fb; padding: 0.8em 1em; border-radius: 4px;
         font-size: 0.85em; color: #444; margin-bottom: 1em; }
code { background: #f0f0f0; padding: 1px 4px; border-radius: 3px; }
"""


def main() -> int:
    out_path = OUT / "report.html"
    timestamp = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    sha = git_sha()

    body = "\n".join([
        f'<header>Generated {html.escape(timestamp)} &mdash; git <code>{html.escape(sha)}</code> &mdash; seed=42</header>',
        '<h1>FastRW &mdash; Reproduction report</h1>',
        '<p>Self-contained summary of every paper table + figure produced by '
        '<code>./reproduce.sh</code>. Tables are rendered from the JSONs under '
        '<code>outputs/</code>; figures are PNGs base64-embedded so this HTML is '
        'portable.</p>',
        build_table1(),
        build_bootstrap_figs(),
        build_table_multi(),
        build_table_tradeoff(),
        build_table_weakprior(),
        build_table_time(),
    ])

    html_doc = (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head><meta charset="utf-8"><title>FastRW reproduction report</title>'
        f'<style>{CSS}</style></head>\n'
        f'<body>\n{body}\n</body>\n</html>\n'
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_doc, encoding="utf-8")
    print(f"[build_html_report] wrote {out_path.relative_to(ROOT)} "
          f"({out_path.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
