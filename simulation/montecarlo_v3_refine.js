#!/usr/bin/env node
'use strict';

/**
 * Monte Carlo v3 Refine — Narrow search around best config from v3.
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

const NUM_CONFIGS = ARGS.configs ?? 100;
const ROUNDS_PER = ARGS.rounds ?? 250;
const TOP_N = ARGS.topN ?? 10;
const REVAL_ROUNDS = ARGS.revalidate ?? 1500;

// Best config from v3 Phase 2 winner
const BEST = {
    kp: 0.688, searchPwm: 0.971, trackPwm: 0.989, chargePwm: 0.999,
    chargeThreshold: 394, evadePwm: 0.95, edgeSteer: 0.492, centerFill: 146,
    laserAngle: 0.426, flankAngle: 0.592, flankThreshold: 589, flankPwm: 0.658,
    flankEnabled: 1, counterThresh: 23.124, counterDodgeTime: 0.203,
    counterPwm: 0.955, tiltEscapeSpin: 0.289,
};

// Narrow ranges: ±20% around best (clamped to physical limits)
function narrowRange(val, pct, lo, hi) {
    const d = Math.abs(val) * pct;
    return { min: Math.max(lo, val - d), max: Math.min(hi, val + d), best: val };
}

const RANGES = {
    kp:              narrowRange(BEST.kp, 0.25, 0.3, 1.5),
    searchPwm:       narrowRange(BEST.searchPwm, 0.10, 0.6, 1.0),
    trackPwm:        narrowRange(BEST.trackPwm, 0.10, 0.7, 1.0),
    chargePwm:       narrowRange(BEST.chargePwm, 0.05, 0.9, 1.0),
    chargeThreshold: narrowRange(BEST.chargeThreshold, 0.25, 100, 600),
    evadePwm:        narrowRange(BEST.evadePwm, 0.15, 0.5, 1.0),
    edgeSteer:       narrowRange(BEST.edgeSteer, 0.30, 0.1, 0.7),
    centerFill:      narrowRange(BEST.centerFill, 0.30, 50, 350),
    laserAngle:      narrowRange(BEST.laserAngle, 0.25, 0.1, 0.55),
    flankAngle:      narrowRange(BEST.flankAngle, 0.30, 0.1, 0.8),
    flankThreshold:  narrowRange(BEST.flankThreshold, 0.20, 200, 700),
    flankPwm:        narrowRange(BEST.flankPwm, 0.25, 0.4, 1.0),
    flankEnabled:    { min: 1, max: 1, best: 1 },  // keep enabled (was winning config)
    counterThresh:   narrowRange(BEST.counterThresh, 0.30, 8, 45),
    counterDodgeTime:narrowRange(BEST.counterDodgeTime, 0.30, 0.06, 0.35),
    counterPwm:      narrowRange(BEST.counterPwm, 0.15, 0.6, 1.0),
    tiltEscapeSpin:  narrowRange(BEST.tiltEscapeSpin, 0.40, 0.0, 0.7),
};

const FIXED = '--evadeFrontTime 0.45 --evadeRearTime 0.30 --evadeReverseRatio 0.45 --centerReturnTime 0.35';

const ENEMY_PROFILES = [
    { r: 0.035, m: 0.3, s: 0.7, w: 0.05, smart: false, label: 'S-light-slow' },
    { r: 0.035, m: 0.3, s: 1.3, w: 0.05, smart: false, label: 'S-light-fast' },
    { r: 0.055, m: 0.5, s: 1.0, w: 0.10, smart: false, label: 'Standard' },
    { r: 0.055, m: 0.7, s: 1.0, w: 0.05, smart: false, label: 'M-heavy' },
    { r: 0.075, m: 0.8, s: 0.7, w: 0.05, smart: false, label: 'XL-heavy-slow' },
    { r: 0.075, m: 0.8, s: 1.3, w: 0.05, smart: false, label: 'XL-heavy-fast' },
    { r: 0.040, m: 0.7, s: 1.2, w: 0.05, smart: false, label: 'S-heavy-fast' },
    { r: 0.070, m: 0.4, s: 1.3, w: 0.05, smart: false, label: 'L-light-fast' },
    { r: 0.055, m: 0.5, s: 1.0, w: 0.20, smart: true, label: 'Smart-std' },
    { r: 0.055, m: 0.7, s: 1.2, w: 0.15, smart: true, label: 'Smart-heavy-fast' },
    { r: 0.040, m: 0.4, s: 1.3, w: 0.10, smart: true, label: 'Smart-light-fast' },
    { r: 0.075, m: 0.8, s: 0.8, w: 0.10, smart: true, label: 'Smart-XL-slow' },
];

function randomInRange(r) { return +(r.min + Math.random() * (r.max - r.min)).toFixed(4); }
function roundParam(key, val) {
    if (['chargeThreshold', 'centerFill', 'flankThreshold'].includes(key)) return Math.round(val);
    if (key === 'flankEnabled') return val >= 0.5 ? 1 : 0;
    return +val.toFixed(3);
}
function generateConfig() {
    const cfg = {};
    for (const [key, range] of Object.entries(RANGES)) cfg[key] = roundParam(key, randomInRange(range));
    return cfg;
}
function buildArgs(cfg) { return Object.entries(cfg).map(([k, v]) => `--${k} ${v}`).join(' '); }

function evaluate(cfg, rounds) {
    const script = path.join(__dirname, 'headless.js');
    const args = `${FIXED} ${buildArgs(cfg)}`;
    let totalWR = 0, profileResults = [];
    for (const ep of ENEMY_PROFILES) {
        const smartFlag = ep.smart ? '--smart' : '';
        const cmd = `node "${script}" --rounds ${rounds} ${args} --enemyColRadius ${ep.r} --enemyMass ${ep.m} --enemySpdFactor ${ep.s} ${smartFlag}`;
        try {
            const out = execSync(cmd, { timeout: 120000, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] });
            const d = JSON.parse(out);
            totalWR += d.results.winRate * ep.w;
            profileResults.push({ label: ep.label, wr: d.results.winRate, to: d.results.timeouts / rounds, smart: ep.smart });
        } catch (e) { return null; }
    }
    return { weightedWR: +totalWR.toFixed(4), profiles: profileResults };
}

// === MAIN ===
console.log(`Refine: ${NUM_CONFIGS} configs x ${ROUNDS_PER} rounds x ${ENEMY_PROFILES.length} profiles`);
console.log('Narrow ranges around v3 winner:');
for (const [k, r] of Object.entries(RANGES)) {
    if (r.min === r.max) continue;
    console.log(`  ${k}: [${r.min.toFixed(3)}, ${r.max.toFixed(3)}] (center: ${r.best})`);
}
console.log('');

const bestCfg = {};
for (const [key, range] of Object.entries(RANGES)) bestCfg[key] = range.best;

const results = [];
const t0 = Date.now();

process.stdout.write(`[  0/${NUM_CONFIGS}] Baseline... `);
const baseResult = evaluate(bestCfg, ROUNDS_PER);
if (baseResult) {
    results.push({ cfg: bestCfg, ...baseResult });
    const smartWR = baseResult.profiles.filter(p => p.smart).reduce((s, p) => s + p.wr, 0) / baseResult.profiles.filter(p => p.smart).length;
    console.log(`WR=${(baseResult.weightedWR * 100).toFixed(1)}% smart=${(smartWR * 100).toFixed(1)}%`);
}

for (let i = 1; i <= NUM_CONFIGS; i++) {
    const cfg = generateConfig();
    process.stdout.write(`[${String(i).padStart(3)}/${NUM_CONFIGS}] `);
    const res = evaluate(cfg, ROUNDS_PER);
    if (res) {
        results.push({ cfg, ...res });
        const tag = res.weightedWR >= (baseResult ? baseResult.weightedWR : 0.88) ? ' ** BETTER **' : '';
        console.log(`WR=${(res.weightedWR * 100).toFixed(1)}%${tag}`);
    } else { console.log('FAILED'); }
}

console.log(`\nPhase 1 done in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
results.sort((a, b) => b.weightedWR - a.weightedWR);

console.log(`\n=== TOP ${TOP_N} ===`);
for (let i = 0; i < Math.min(TOP_N, results.length); i++) {
    const r = results[i];
    const smartWR = r.profiles.filter(p => p.smart).reduce((s, p) => s + p.wr, 0) / r.profiles.filter(p => p.smart).length;
    console.log(`#${i + 1} WR=${(r.weightedWR * 100).toFixed(1)}% smart=${(smartWR * 100).toFixed(1)}%`);
}

console.log(`\n=== PHASE 2: Revalidating top ${TOP_N} at ${REVAL_ROUNDS} rounds ===`);
const validated = [];
for (let i = 0; i < Math.min(TOP_N, results.length); i++) {
    process.stdout.write(`[${i + 1}/${TOP_N}] `);
    const res = evaluate(results[i].cfg, REVAL_ROUNDS);
    if (res) {
        validated.push({ cfg: results[i].cfg, ...res });
        const smartWR = res.profiles.filter(p => p.smart).reduce((s, p) => s + p.wr, 0) / res.profiles.filter(p => p.smart).length;
        console.log(`WR=${(res.weightedWR * 100).toFixed(1)}% smart=${(smartWR * 100).toFixed(1)}%`);
    }
}
validated.sort((a, b) => b.weightedWR - a.weightedWR);

console.log(`\n${'='.repeat(70)}`);
console.log('FINAL REFINED RESULTS');
console.log('='.repeat(70));
for (let i = 0; i < Math.min(3, validated.length); i++) {
    const r = validated[i];
    const smartWR = r.profiles.filter(p => p.smart).reduce((s, p) => s + p.wr, 0) / r.profiles.filter(p => p.smart).length;
    const basicWR = r.profiles.filter(p => !p.smart).reduce((s, p) => s + p.wr, 0) / r.profiles.filter(p => !p.smart).length;
    console.log(`\n#${i + 1} | WR=${(r.weightedWR * 100).toFixed(2)}% | Smart=${(smartWR * 100).toFixed(1)}% | Basic=${(basicWR * 100).toFixed(1)}%`);
    for (const p of r.profiles) console.log(`     ${p.label}: ${(p.wr * 100).toFixed(1)}%`);
    console.log('   Params: ' + JSON.stringify(r.cfg));
    console.log('   CLI: node headless.js --rounds 1000 ' + FIXED + ' ' + buildArgs(r.cfg));
}
console.log(`\nTotal: ${((Date.now() - t0) / 1000).toFixed(1)}s`);
