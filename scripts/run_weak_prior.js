#!/usr/bin/env node
// =====================================================================
// run_weak_prior.js
//
// Orchestrator for tab:weakprior (Case 1, M=16, eps=0.4 K).
//   1. (optional) Runs Metal MC at N_max=4096 with Lambda=1e-3 and the
//      rule-of-thumb uniform prior.
//   2. Calls scripts/run_fastrw_post.js and scripts/run_fasterrw_post.js
//      with B=500 over a sweep of N values and picks the smallest N
//      whose bootstrap mean_avg_abs <= 0.4 K. If no value in the sweep
//      satisfies the target, the largest tested N is reported with a
//      flag.
//   3. Looks up the canonical PIRW / FEM-prior FastRW / FEM-prior
//      FasterRW rows from outputs/tcad_table1/paper_results/.
//   4. Writes outputs/tcad_table_weakprior/case1_weakprior_summary.json
//      with all five rows including speedup vs PIRW.
//
// Usage
//   node scripts/run_weak_prior.js \
//        --config=<path> --run-dir=<dir> --nmax=<int> [--skip-mc=0|1]
//
// All numbers needed for the LaTeX table are in the summary JSON.
// =====================================================================
"use strict";

const fs = require("fs");
const path = require("path");
const { execFileSync, spawnSync } = require("child_process");

function parseArgs(argv) {
  const out = { skipMc: 0 };
  for (const a of argv.slice(2)) {
    const m = a.match(/^--([^=]+)=(.*)$/);
    if (!m) continue;
    const [, k, v] = m;
    if (k === "config") out.config = v;
    else if (k === "run-dir") out.runDir = v;
    else if (k === "nmax") out.nmax = parseInt(v, 10);
    else if (k === "skip-mc") out.skipMc = parseInt(v, 10);
  }
  if (!out.config || !out.runDir || !out.nmax) {
    process.stderr.write("Missing required --config/--run-dir/--nmax\n");
    process.exit(2);
  }
  return out;
}

function runShell(cmd, args, opts = {}) {
  process.stderr.write(`[run_weak_prior] $ ${cmd} ${args.join(" ")}\n`);
  const res = spawnSync(cmd, args, { stdio: "inherit", ...opts });
  if (res.status !== 0) {
    throw new Error(`${cmd} exited with status ${res.status}`);
  }
}

function loadJson(p) {
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

function bootstrap(postScript, runDir, config, N, outPath) {
  runShell(process.execPath, [
    postScript,
    runDir,
    config,
    `--N=${N}`,
    `--B=500`,
    `--seed=42`,
    `--output=${outPath}`,
  ]);
  return loadJson(outPath);
}

function bootstrapPirw(postScript, runDir, N, outPath) {
  runShell(process.execPath, [
    postScript,
    runDir,
    `--N=${N}`,
    `--B=500`,
    `--seed=42`,
    `--output=${outPath}`,
  ]);
  return loadJson(outPath);
}

function pickNstar(label, sweep, postScript, runDir, config, outDir, targetEps) {
  let best = null;
  const trials = [];
  for (const N of sweep) {
    const outPath = path.join(outDir, `${label}_N${N}.json`);
    const res = bootstrap(postScript, runDir, config, N, outPath);
    trials.push({ N, mean_avg_abs: res.mean_avg_abs, std_avg_abs: res.std_avg_abs, file: outPath });
    process.stderr.write(`[run_weak_prior] ${label} N=${N}  mean_avg_abs=${res.mean_avg_abs.toFixed(4)} +/- ${res.std_avg_abs.toFixed(4)} K\n`);
    if (res.mean_avg_abs <= targetEps && best === null) {
      best = { N, file: outPath, result: res };
    }
  }
  if (best === null) {
    // Use the largest N tried; flag it
    const last = trials[trials.length - 1];
    best = { N: last.N, file: last.file, result: loadJson(last.file), insufficient: true };
  }
  return { best, trials };
}

(async function main() {
  const args = parseArgs(process.argv);
  const rootDir = path.resolve(__dirname, "..");
  const outDir = path.dirname(args.runDir);

  // Step 1: Metal MC at N_max
  if (!args.skipMc) {
    runShell(path.join(rootDir, "scripts", "build_and_run_metal.sh"), [
      args.config,
      String(args.nmax),
    ], { env: { ...process.env, RUN_ONESTAGE: "0" } });
  } else {
    process.stderr.write("[run_weak_prior] --skip-mc set; reusing existing MC outputs.\n");
  }

  if (!fs.existsSync(path.join(args.runDir, "constraints.json"))) {
    throw new Error(`Missing constraints.json under ${args.runDir} — MC did not produce expected outputs.`);
  }

  // Sanity: load summary.json to capture runtime
  const summaryPath = path.join(args.runDir, "summary.json");
  const mcSummary = fs.existsSync(summaryPath) ? loadJson(summaryPath) : {};
  const runtimeSeconds = mcSummary.random_walk && mcSummary.random_walk.runtime_seconds;

  // Step 2: Bootstrap sweeps for FastRW and FasterRW
  const fastScript = path.join(rootDir, "scripts", "run_fastrw_post.js");
  const fasterScript = path.join(rootDir, "scripts", "run_fasterrw_post.js");
  const pirwScript = path.join(rootDir, "scripts", "run_pirw_post.js");
  const sweep = [256, 512, 1024, 2048, 4096];
  const targetEps = 0.4;

  const fast = pickNstar("fastrw_rot", sweep, fastScript, args.runDir, args.config, outDir, targetEps);
  const faster = pickNstar("fasterrw_rot", sweep, fasterScript, args.runDir, args.config, outDir, targetEps);

  // Step 3: Canonical reference rows
  const paperResultsDir = path.join(rootDir, "outputs", "tcad_table1", "paper_results");
  const pirwRef = loadJson(path.join(paperResultsDir, "case1_pirw_eps0.4.json"));
  const fastRefFem = loadJson(path.join(paperResultsDir, "case1_fastrw_eps0.4.json"));
  const fasterRefFem = loadJson(path.join(paperResultsDir, "case1_fasterrw_eps0.4.json"));

  const M = 16;

  function perQueryTime(runtimeSec, N, Nmax, M) {
    return runtimeSec * N / Nmax / M;
  }

  const pirwTimePerQuery = perQueryTime(pirwRef.runtime_seconds, pirwRef.N, pirwRef.Nmax, M);
  const fastFemTimePerQuery = perQueryTime(fastRefFem.runtime_seconds, fastRefFem.N, fastRefFem.Nmax, M);
  const fasterFemTimePerQuery = perQueryTime(fasterRefFem.runtime_seconds, fasterRefFem.N, fasterRefFem.Nmax, M);
  const fastRotTimePerQuery = perQueryTime(runtimeSeconds, fast.best.N, args.nmax, M);
  const fasterRotTimePerQuery = perQueryTime(runtimeSeconds, faster.best.N, args.nmax, M);

  function row(method, label, lambda, prior, N, meanAvgAbs, meanAvgSteps, timeSec, baseline) {
    return {
      method,
      label,
      prior,
      Lambda: lambda,
      paths_N: N,
      mean_avg_abs_K: meanAvgAbs,
      mean_avg_steps: meanAvgSteps,
      total_steps_10e6: (meanAvgSteps * N) / 1e6,
      time_per_query_seconds: timeSec,
      speedup_vs_pirw: baseline / timeSec,
    };
  }

  const summary = {
    script: "run_weak_prior.js",
    case: "case1_power6",
    M,
    target_eps_K: targetEps,
    notes: {
      rule_of_thumb_prior_value_C: 20.0,
      rule_of_thumb_max_prior_error_K: loadJson(
        path.join(rootDir, "data", "cases", "case1_power6", "rule_of_thumb", "metadata.json")
      ).prior_error_vs_reference_celsius.max_abs,
      time_per_query_definition: "MC wallclock * N / N_max / M (excludes prior-build cost; PIRW has none)",
      mc_nmax_rot: args.nmax,
      mc_runtime_seconds_rot: runtimeSeconds,
      fastrw_sweep: fast.trials,
      fasterrw_sweep: faster.trials,
      fastrw_target_satisfied: fast.best.insufficient !== true,
      fasterrw_target_satisfied: faster.best.insufficient !== true,
    },
    rows: [
      row("PIRW", "PIRW (no prior)", 1e-4, "none",
          pirwRef.N, pirwRef.mean_avg_abs, pirwRef.mean_avg_steps,
          pirwTimePerQuery, pirwTimePerQuery),
      row("FastRW", "Rule-of-thumb FastRW", 1e-3, "uniform ambient (rule-of-thumb)",
          fast.best.N, fast.best.result.mean_avg_abs, fast.best.result.mean_avg_steps,
          fastRotTimePerQuery, pirwTimePerQuery),
      row("FasterRW", "Rule-of-thumb FasterRW", 1e-3, "uniform ambient (rule-of-thumb)",
          faster.best.N, faster.best.result.mean_avg_abs, faster.best.result.mean_avg_steps,
          fasterRotTimePerQuery, pirwTimePerQuery),
      row("FastRW", "FEM prior FastRW", 0.030, "comso_1288",
          fastRefFem.N, fastRefFem.mean_avg_abs, fastRefFem.mean_avg_steps,
          fastFemTimePerQuery, pirwTimePerQuery),
      row("FasterRW", "FEM prior FasterRW", 0.030, "comso_1288",
          fasterRefFem.N, fasterRefFem.mean_avg_abs, fasterRefFem.mean_avg_steps,
          fasterFemTimePerQuery, pirwTimePerQuery),
    ],
  };

  const summaryOut = path.join(outDir, "case1_weakprior_summary.json");
  fs.writeFileSync(summaryOut, JSON.stringify(summary, null, 2) + "\n");
  process.stderr.write(`[run_weak_prior] wrote ${summaryOut}\n`);

  process.stderr.write("\n[run_weak_prior] === tab:weakprior rows ===\n");
  for (const r of summary.rows) {
    process.stderr.write(
      `  ${r.label.padEnd(28)} N=${String(r.paths_N).padStart(5)}  ` +
      `avg_abs=${r.mean_avg_abs_K.toFixed(3)} K  ` +
      `t/pt=${r.time_per_query_seconds.toFixed(3)} s  ` +
      `speedup=${r.speedup_vs_pirw.toFixed(2)}x\n`
    );
  }
})().catch((e) => {
  process.stderr.write(`[run_weak_prior] FATAL: ${e.stack || e}\n`);
  process.exit(1);
});
