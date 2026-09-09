#!/usr/bin/env node
// Build wall-clock estimates for every Table 1 case/epsilon cell.
// CUDA Nmax runtimes are measured values from each summary.json. Runtime at
// the paper-selected N follows the report's existing linear-in-N convention.
// Post-processing is timed three times and the median is used.
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const { performance } = require('perf_hooks');

const ROOT = path.resolve(__dirname, '..');
const TABLE1 = path.join(ROOT, 'outputs', 'tcad_table1');
const OUTPUT = path.join(ROOT, 'outputs', 'tcad_table_time', 'all_cases_wallclock.json');
const B = 500;
const SEED = 42;
const REPEATS = 3;

const FASTRW_POST = path.join(ROOT, 'scripts', 'run_fastrw_post.js');
const FASTERRW_POST = path.join(ROOT, 'scripts', 'run_fasterrw_post.js');

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function median(values) {
  const sorted = values.slice().sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function scratch(name) {
  const dir = path.join(os.tmpdir(), 'fastrw_wallclock_all');
  fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, name);
}

function timedNode(args, label) {
  const samples = [];
  for (let i = 0; i < REPEATS; i += 1) {
    const start = performance.now();
    // Inherit stdio: piped spawnSync can deadlock with these Node post-processors
    // on Windows when their bootstrap output is sufficiently large.
    const result = spawnSync(process.execPath, args, { stdio: 'inherit' });
    const seconds = (performance.now() - start) / 1000;
    if (result.status !== 0) {
      throw new Error(`${label} failed with status ${result.status}`);
    }
    samples.push(seconds);
    process.stdout.write(`[wallclock] ${label} ${i + 1}/${REPEATS}: ${seconds.toFixed(3)} s\n`);
  }
  return { median: median(samples), samples };
}

function paperN(caseNumber, method, eps) {
  const file = path.join(
    TABLE1,
    'paper_results',
    `case${caseNumber}_${method}_eps${eps.toFixed(1)}.json`
  );
  return Number(readJson(file).N);
}

function buildCell(caseNumber, eps) {
  const caseName = `case${caseNumber}`;
  const pirwDir = path.join(TABLE1, `pirw_${caseName}`);
  const fastrwDir = path.join(TABLE1, `fastrw_${caseName}`);
  const config = path.join(ROOT, 'configs', 'tcad_table1', `fastrw_${caseName}.json`);

  const pirwSummary = readJson(path.join(pirwDir, 'summary.json')).random_walk;
  const fastrwSummary = readJson(path.join(fastrwDir, 'summary.json')).random_walk;
  const M = Number(readJson(path.join(fastrwDir, 'constraints.json')).M || 16);
  const n = {
    PIRW: paperN(caseNumber, 'pirw', eps),
    FastRW: paperN(caseNumber, 'fastrw', eps),
    FasterRW: paperN(caseNumber, 'fasterrw', eps),
  };

  const tag = `${caseName}_eps${String(eps).replace('.', '')}`;
  const fastFusion = timedNode([
    FASTRW_POST, fastrwDir, config,
    `--N=${n.FastRW}`, `--B=${B}`, `--seed=${SEED}`,
    `--output=${scratch(`${tag}_fastrw_N${n.FastRW}.json`)}`,
  ], `${tag} FastRW post N=${n.FastRW}`);
  const fasterFusion = timedNode([
    FASTRW_POST, fastrwDir, config,
    `--N=${n.FasterRW}`, `--B=${B}`, `--seed=${SEED}`,
    `--output=${scratch(`${tag}_fusion_N${n.FasterRW}.json`)}`,
  ], `${tag} fusion N=${n.FasterRW}`);
  const fasterCombined = timedNode([
    FASTERRW_POST, fastrwDir, config,
    `--N=${n.FasterRW}`, `--B=${B}`, `--seed=${SEED}`,
    `--output=${scratch(`${tag}_fasterrw_N${n.FasterRW}.json`)}`,
  ], `${tag} FasterRW post N=${n.FasterRW}`);

  const pirwMc = Number(pirwSummary.runtime_seconds) * n.PIRW /
    Number(pirwSummary.num_samples) / M;
  const fastMc = Number(fastrwSummary.runtime_seconds) * n.FastRW /
    Number(fastrwSummary.num_samples) / M;
  const fasterMc = Number(fastrwSummary.runtime_seconds) * n.FasterRW /
    Number(fastrwSummary.num_samples) / M;

  // The canonical COMSOL logs have integer-second resolution and record a
  // zero-second linear solve. Charge the report's conservative <1 s total
  // upper bound, amortized over the 16 queries.
  const femPerQueryUpperBound = 1 / M;
  const fastFusionPerQuery = fastFusion.median / M;
  const fasterFusionPerQuery = fasterFusion.median / M;
  const gpPerQuery = Math.max(
    (fasterCombined.median - fasterFusion.median) / M,
    0
  );

  const pirwTotal = pirwMc;
  const fastTotal = femPerQueryUpperBound + fastMc + fastFusionPerQuery;
  const fasterTotal = femPerQueryUpperBound + fasterMc +
    fasterFusionPerQuery + gpPerQuery;

  return {
    case: caseName,
    eps_target_K: eps,
    M,
    N: n,
    measured_cuda_nmax: {
      PIRW: {
        runtime_seconds: Number(pirwSummary.runtime_seconds),
        num_samples: Number(pirwSummary.num_samples),
      },
      FastRW_shared: {
        runtime_seconds: Number(fastrwSummary.runtime_seconds),
        num_samples: Number(fastrwSummary.num_samples),
      },
    },
    stages_per_query_s: {
      PIRW: { MC: pirwMc, Total: pirwTotal },
      FastRW: {
        FEM_upper_bound: femPerQueryUpperBound,
        MC: fastMc,
        Fusion: fastFusionPerQuery,
        Total_upper_bound: fastTotal,
      },
      FasterRW: {
        FEM_upper_bound: femPerQueryUpperBound,
        MC: fasterMc,
        Fusion: fasterFusionPerQuery,
        GP: gpPerQuery,
        Total_upper_bound: fasterTotal,
      },
    },
    wallclock_speedup_vs_PIRW_lower_bound: {
      FastRW: pirwTotal / fastTotal,
      FasterRW: pirwTotal / fasterTotal,
    },
    postprocess_measurements_s: {
      FastRW: fastFusion,
      FasterRW_fusion: fasterFusion,
      FasterRW_fusion_plus_GP: fasterCombined,
    },
  };
}

function main() {
  const cells = [];
  for (const eps of [0.4, 0.5]) {
    for (const caseNumber of [1, 2, 3]) {
      process.stdout.write(`\n[wallclock] Case ${caseNumber}, eps=${eps}\n`);
      cells.push(buildCell(caseNumber, eps));
    }
  }

  const firstSummary = readJson(path.join(TABLE1, 'fastrw_case1', 'summary.json'));
  const output = {
    methodology: {
      cuda_time: 'Measured Nmax CUDA runtime, scaled linearly to the paper-selected N and divided by M queries.',
      postprocess_time: `Measured wall clock; median of ${REPEATS} runs.`,
      fem_time: 'Conservative upper bound of <1 second per 16-query prior solve, from the canonical COMSOL log integer-second resolution.',
      totals: 'FastRW/FasterRW totals are upper bounds; their reported speedups are corresponding lower bounds.',
    },
    device: firstSummary.random_walk.device,
    backend: firstSummary.random_walk.backend,
    B,
    seed_base: SEED,
    repeats_per_stage: REPEATS,
    cells,
    generated_at: new Date().toISOString(),
  };
  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
  fs.writeFileSync(OUTPUT, JSON.stringify(output, null, 2) + '\n');
  process.stdout.write(`\n[wallclock] wrote ${OUTPUT}\n`);
}

main();
