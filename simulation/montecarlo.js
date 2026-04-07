#!/usr/bin/env node
'use strict';

const { execSync } = require('child_process');
const path = require('path');

// === CONFIG ===
const ROUNDS_PER_CONFIG = 500;       // rounds per evaluation
const NUM_CONFIGS = 150;             // total random configs to try
const TOP_N = 10;                    // top results to revalidate
const REVALIDATE_ROUNDS = 3000;      // rounds for top-N revalidation

// === PARAMETER RANGES (centered on current best) ===
const RANGES = {
    kp:              { min: 0.3,  max: 1.0,  best: 0.6  },
    searchPwm:       { min: 0.7,  max: 1.0,  best: 0.95 },
    trackPwm:        { min: 0.7,  max: 1.0,  best: 0.9  },
    chargePwm:       { min: 0.85, max: 1.0,  best: 1.0  },
    chargeThreshold: { min: 100,  max: 400,  best: 200  },
    evadeFrontTime:  { min: 0.25, max: 0.6,  best: 0.45 },
    evadeRearTime:   { min: 0.15, max: 0.45, best: 0.30 },
    evadeReverseRatio:{ min: 0.2, max: 0.6,  best: 0.45 },
    evadePwm:        { min: 0.5,  max: 1.0,  best: 0.85 },
    edgeSteer:       { min: 0.2,  max: 0.8,  best: 0.5  },
    laserAngle:      { min: 0.10, max: 0.40, best: 0.26 },
};

function randomInRange(r) {
    return +(r.min + Math.random() * (r.max - r.min)).toFixed(4);
}

function roundParam(key, val) {
    if (key === 'chargeThreshold') return Math.round(val);
    return +val.toFixed(3);
}

function generateConfig() {
    const cfg = {};
    for (const [key, range] of Object.entries(RANGES)) {
        cfg[key] = roundParam(key, randomInRange(range));
    }
    return cfg;
}

function buildArgs(cfg, rounds) {
    const parts = [`--rounds ${rounds}`];
    for (const [key, val] of Object.entries(cfg)) {
        parts.push(`--${key} ${val}`);
    }
    return parts.join(' ');
}

function evaluate(cfg, rounds) {
    const script = path.join(__dirname, 'headless.js');
    const args = buildArgs(cfg, rounds);
    try {
        const out = execSync(`node "${script}" ${args}`, { timeout: 60000, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] });
        return JSON.parse(out);
    } catch (e) {
        return null;
    }
}

// === MAIN ===
console.log(`Monte Carlo optimization: ${NUM_CONFIGS} configs x ${ROUNDS_PER_CONFIG} rounds`);
console.log('Parameter ranges:');
for (const [k, r] of Object.entries(RANGES)) {
    console.log(`  ${k}: [${r.min}, ${r.max}] (best: ${r.best})`);
}
console.log('');

// Phase 1: current best as config #0
const bestCfg = {};
for (const [key, range] of Object.entries(RANGES)) {
    bestCfg[key] = range.best;
}

const results = [];
const t0 = Date.now();

// Evaluate current best first
process.stdout.write(`[  0/${NUM_CONFIGS}] Evaluating current best... `);
const baseResult = evaluate(bestCfg, ROUNDS_PER_CONFIG);
if (baseResult) {
    results.push({ cfg: bestCfg, wr: baseResult.results.winRate, to: baseResult.results.timeouts / ROUNDS_PER_CONFIG, avgDur: baseResult.results.avgDuration });
    console.log(`WR=${baseResult.results.winRate.toFixed(3)} TO=${(baseResult.results.timeouts / ROUNDS_PER_CONFIG * 100).toFixed(1)}%`);
}

// Phase 1: random search
for (let i = 1; i <= NUM_CONFIGS; i++) {
    const cfg = generateConfig();
    process.stdout.write(`[${String(i).padStart(3)}/${NUM_CONFIGS}] `);
    const res = evaluate(cfg, ROUNDS_PER_CONFIG);
    if (res) {
        const wr = res.results.winRate;
        const to = res.results.timeouts / ROUNDS_PER_CONFIG;
        results.push({ cfg, wr, to, avgDur: res.results.avgDuration });
        // Show progress for promising results
        if (wr >= 0.95) {
            console.log(`WR=${wr.toFixed(3)} TO=${(to * 100).toFixed(1)}% ** PROMISING **`);
        } else {
            console.log(`WR=${wr.toFixed(3)} TO=${(to * 100).toFixed(1)}%`);
        }
    } else {
        console.log('FAILED');
    }
}

const phase1Time = ((Date.now() - t0) / 1000).toFixed(1);
console.log(`\nPhase 1 complete in ${phase1Time}s`);

// Sort by winRate, then by fewer timeouts
results.sort((a, b) => b.wr - a.wr || a.to - b.to);

console.log(`\n=== TOP ${TOP_N} CONFIGS (Phase 1, ${ROUNDS_PER_CONFIG} rounds) ===`);
for (let i = 0; i < Math.min(TOP_N, results.length); i++) {
    const r = results[i];
    console.log(`#${i + 1} WR=${r.wr.toFixed(3)} TO=${(r.to * 100).toFixed(1)}% avgDur=${r.avgDur}s`);
    for (const [k, v] of Object.entries(r.cfg)) {
        const best = RANGES[k].best;
        const diff = v !== best ? ` (was ${best})` : '';
        if (diff) console.log(`     ${k}=${v}${diff}`);
    }
}

// Phase 2: revalidate top-N at higher round count
console.log(`\n=== PHASE 2: Revalidating top ${TOP_N} at ${REVALIDATE_ROUNDS} rounds ===`);
const validated = [];
for (let i = 0; i < Math.min(TOP_N, results.length); i++) {
    const r = results[i];
    process.stdout.write(`[${i + 1}/${TOP_N}] Revalidating... `);
    const res = evaluate(r.cfg, REVALIDATE_ROUNDS);
    if (res) {
        const wr = res.results.winRate;
        const to = res.results.timeouts / REVALIDATE_ROUNDS;
        validated.push({ cfg: r.cfg, wr, to, avgDur: res.results.avgDuration });
        console.log(`WR=${wr.toFixed(4)} TO=${(to * 100).toFixed(1)}%`);
    }
}

validated.sort((a, b) => b.wr - a.wr || a.to - b.to);

console.log(`\n${'='.repeat(60)}`);
console.log('FINAL RESULTS (sorted by winRate)');
console.log('='.repeat(60));
for (let i = 0; i < validated.length; i++) {
    const r = validated[i];
    console.log(`\n#${i + 1} | WR=${(r.wr * 100).toFixed(2)}% | Timeouts=${(r.to * 100).toFixed(1)}% | AvgDur=${r.avgDur}s`);
    console.log('   CLI: node headless.js --rounds 500 ' + buildArgs(r.cfg, '').replace('--rounds  ', '').trim());
}

const totalTime = ((Date.now() - t0) / 1000).toFixed(1);
console.log(`\nTotal time: ${totalTime}s`);
