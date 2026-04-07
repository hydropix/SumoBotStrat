#!/usr/bin/env node
'use strict';

/**
 * Monte Carlo v2 — Optimizes center-laser config against variable enemy sizes.
 * Usage: node montecarlo_v2.js [--configs 100] [--rounds 300] [--topN 8] [--revalidate 1000]
 */

const { execSync } = require('child_process');
const path = require('path');

const ARGS = (() => {
    const a = {};
    const v = process.argv.slice(2);
    for (let i = 0; i < v.length; i++) {
        if (v[i].startsWith('--')) {
            const k = v[i].slice(2);
            const val = v[i + 1];
            if (val !== undefined && !val.startsWith('--')) { a[k] = isNaN(val) ? val : parseFloat(val); i++; }
            else a[k] = true;
        }
    }
    return a;
})();

const NUM_CONFIGS = ARGS.configs ?? 120;
const ROUNDS_PER_SIZE = ARGS.rounds ?? 300;
const TOP_N = ARGS.topN ?? 8;
const REVAL_ROUNDS = ARGS.revalidate ?? 1000;

// Enemy profiles: size × mass × speed (emphasize realistic, cover extremes)
const ENEMY_SIZES = [
    { r: 0.035, m: 0.3, s: 1.0, w: 0.10, label: 'S-light' },
    { r: 0.055, m: 0.5, s: 1.0, w: 0.25, label: 'Standard' },
    { r: 0.075, m: 0.8, s: 1.3, w: 0.15, label: 'XL-heavy-fast' },
    { r: 0.040, m: 0.7, s: 1.2, w: 0.15, label: 'S-heavy-fast' },
    { r: 0.075, m: 0.8, s: 0.7, w: 0.10, label: 'XL-heavy-slow' },
    { r: 0.055, m: 0.7, s: 1.0, w: 0.10, label: 'M-heavy' },
    { r: 0.070, m: 0.4, s: 1.3, w: 0.10, label: 'L-light-fast' },
    { r: 0.035, m: 0.3, s: 1.3, w: 0.05, label: 'S-light-fast' },
];

// Parameters to optimize (center-laser focused)
const RANGES = {
    kp:              { min: 0.5,  max: 1.5,  best: 1.0  },
    laserAngle:      { min: 0.30, max: 0.55, best: 0.47 },
    centerFill:      { min: 80,   max: 350,  best: 165  },
    searchPwm:       { min: 0.85, max: 1.0,  best: 0.954 },
    trackPwm:        { min: 0.85, max: 1.0,  best: 1.0  },
    chargeThreshold: { min: 150,  max: 500,  best: 300  },
    evadePwm:        { min: 0.7,  max: 1.0,  best: 1.0  },
    edgeSteer:       { min: 0.1,  max: 0.6,  best: 0.245 },
};

// Fixed params (already optimized, not searching these)
const FIXED = '--chargePwm 1.0 --evadeFrontTime 0.45 --evadeRearTime 0.30 --evadeReverseRatio 0.45 --centerReturnTime 0.35';

function randomInRange(r) {
    return +(r.min + Math.random() * (r.max - r.min)).toFixed(4);
}

function roundParam(key, val) {
    if (key === 'centerFill') return Math.round(val);
    return +val.toFixed(3);
}

function generateConfig() {
    const cfg = {};
    for (const [key, range] of Object.entries(RANGES)) {
        cfg[key] = roundParam(key, randomInRange(range));
    }
    return cfg;
}

function buildArgs(cfg) {
    return Object.entries(cfg).map(([k, v]) => `--${k} ${v}`).join(' ');
}

function evaluate(cfg, rounds) {
    const script = path.join(__dirname, 'headless.js');
    const args = `${FIXED} ${buildArgs(cfg)}`;
    let totalWR = 0, sizeResults = [];

    for (const sz of ENEMY_SIZES) {
        const cmd = `node "${script}" --rounds ${rounds} ${args} --enemyColRadius ${sz.r} --enemyMass ${sz.m || 0.5} --enemySpdFactor ${sz.s || 1.0}`;
        try {
            const out = execSync(cmd, { timeout: 60000, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] });
            const d = JSON.parse(out);
            const wr = d.results.winRate;
            const to = d.results.timeouts / rounds;
            totalWR += wr * sz.w;
            sizeResults.push({ size: sz.label, wr, to });
        } catch (e) {
            return null;
        }
    }
    return { weightedWR: +totalWR.toFixed(4), sizes: sizeResults };
}

// === MAIN ===
console.log(`Monte Carlo v2: ${NUM_CONFIGS} configs × ${ROUNDS_PER_SIZE} rounds × ${ENEMY_SIZES.length} sizes`);
console.log(`Enemy sizes: ${ENEMY_SIZES.map(s => `${s.label}(w=${s.w})`).join(', ')}`);
console.log('Parameter ranges:');
for (const [k, r] of Object.entries(RANGES)) {
    console.log(`  ${k}: [${r.min}, ${r.max}] (best: ${r.best})`);
}
console.log('');

// Current best as config #0
const bestCfg = {};
for (const [key, range] of Object.entries(RANGES)) bestCfg[key] = range.best;

const results = [];
const t0 = Date.now();

process.stdout.write(`[  0/${NUM_CONFIGS}] Current best... `);
const baseResult = evaluate(bestCfg, ROUNDS_PER_SIZE);
if (baseResult) {
    results.push({ cfg: bestCfg, ...baseResult });
    const sizeStr = baseResult.sizes.map(s => `${s.size}=${(s.wr * 100).toFixed(1)}%`).join(' ');
    console.log(`WR=${(baseResult.weightedWR * 100).toFixed(1)}% [${sizeStr}]`);
}

// Phase 1: Random search
for (let i = 1; i <= NUM_CONFIGS; i++) {
    const cfg = generateConfig();
    process.stdout.write(`[${String(i).padStart(3)}/${NUM_CONFIGS}] `);
    const res = evaluate(cfg, ROUNDS_PER_SIZE);
    if (res) {
        results.push({ cfg, ...res });
        const tag = res.weightedWR >= 0.94 ? ' ** TOP **' : res.weightedWR >= 0.92 ? ' *' : '';
        console.log(`WR=${(res.weightedWR * 100).toFixed(1)}%${tag}`);
    } else {
        console.log('FAILED');
    }
}

const phase1Time = ((Date.now() - t0) / 1000).toFixed(1);
console.log(`\nPhase 1 complete in ${phase1Time}s`);

// Sort by weighted WR
results.sort((a, b) => b.weightedWR - a.weightedWR);

console.log(`\n=== TOP ${TOP_N} (Phase 1, ${ROUNDS_PER_SIZE} rounds/size) ===`);
for (let i = 0; i < Math.min(TOP_N, results.length); i++) {
    const r = results[i];
    const sizeStr = r.sizes.map(s => `${s.size}=${(s.wr * 100).toFixed(1)}%`).join(' ');
    console.log(`#${i + 1} WR=${(r.weightedWR * 100).toFixed(1)}% [${sizeStr}]`);
    for (const [k, v] of Object.entries(r.cfg)) {
        const best = RANGES[k].best;
        if (v !== best) console.log(`     ${k}=${v} (was ${best})`);
    }
}

// Phase 2: Revalidate top-N
console.log(`\n=== PHASE 2: Revalidating top ${TOP_N} at ${REVAL_ROUNDS} rounds/size ===`);
const validated = [];
for (let i = 0; i < Math.min(TOP_N, results.length); i++) {
    const r = results[i];
    process.stdout.write(`[${i + 1}/${TOP_N}] Revalidating... `);
    const res = evaluate(r.cfg, REVAL_ROUNDS);
    if (res) {
        validated.push({ cfg: r.cfg, ...res });
        const sizeStr = res.sizes.map(s => `${s.size}=${(s.wr * 100).toFixed(1)}%`).join(' ');
        console.log(`WR=${(res.weightedWR * 100).toFixed(1)}% [${sizeStr}]`);
    }
}

validated.sort((a, b) => b.weightedWR - a.weightedWR);

console.log(`\n${'='.repeat(70)}`);
console.log('FINAL RESULTS');
console.log('='.repeat(70));
for (let i = 0; i < validated.length; i++) {
    const r = validated[i];
    const sizeStr = r.sizes.map(s => `${s.size}=${(s.wr * 100).toFixed(1)}%`).join(' ');
    console.log(`\n#${i + 1} | WeightedWR=${(r.weightedWR * 100).toFixed(2)}% | [${sizeStr}]`);
    console.log('   Params: ' + Object.entries(r.cfg).map(([k, v]) => `${k}=${v}`).join(' '));
    console.log('   CLI: node headless.js --rounds 500 ' + buildArgs(r.cfg));
}

const totalTime = ((Date.now() - t0) / 1000).toFixed(1);
console.log(`\nTotal time: ${totalTime}s`);
