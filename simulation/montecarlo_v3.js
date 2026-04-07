#!/usr/bin/env node
'use strict';

/**
 * Monte Carlo v3 — Optimizes flanking + counter-dodge + tilt-escape strategies
 * against variable enemy profiles (size, mass, speed) including smart enemy.
 *
 * Usage: node montecarlo_v3.js [--configs 80] [--rounds 200] [--topN 8] [--revalidate 800]
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

const NUM_CONFIGS = ARGS.configs ?? 80;
const ROUNDS_PER = ARGS.rounds ?? 200;
const TOP_N = ARGS.topN ?? 8;
const REVAL_ROUNDS = ARGS.revalidate ?? 800;

// Enemy profiles: radius, mass, speed, weight, label, smart flag
const ENEMY_PROFILES = [
    // Basic AI enemies (varied size/mass/speed)
    { r: 0.035, m: 0.3, s: 0.7, w: 0.05, smart: false, label: 'S-light-slow' },
    { r: 0.035, m: 0.3, s: 1.3, w: 0.05, smart: false, label: 'S-light-fast' },
    { r: 0.055, m: 0.5, s: 1.0, w: 0.10, smart: false, label: 'Standard' },
    { r: 0.055, m: 0.7, s: 1.0, w: 0.05, smart: false, label: 'M-heavy' },
    { r: 0.075, m: 0.8, s: 0.7, w: 0.05, smart: false, label: 'XL-heavy-slow' },
    { r: 0.075, m: 0.8, s: 1.3, w: 0.05, smart: false, label: 'XL-heavy-fast' },
    { r: 0.040, m: 0.7, s: 1.2, w: 0.05, smart: false, label: 'S-heavy-fast' },
    { r: 0.070, m: 0.4, s: 1.3, w: 0.05, smart: false, label: 'L-light-fast' },
    // Smart enemies (highest weights — this is where we need improvement)
    { r: 0.055, m: 0.5, s: 1.0, w: 0.20, smart: true, label: 'Smart-std' },
    { r: 0.055, m: 0.7, s: 1.2, w: 0.15, smart: true, label: 'Smart-heavy-fast' },
    { r: 0.040, m: 0.4, s: 1.3, w: 0.10, smart: true, label: 'Smart-light-fast' },
    { r: 0.075, m: 0.8, s: 0.8, w: 0.10, smart: true, label: 'Smart-XL-slow' },
];

// Parameters to optimize (focusing on new flanking + counter + tilt params)
const RANGES = {
    kp:              { min: 0.4,  max: 1.5,  best: 0.8  },
    searchPwm:       { min: 0.6,  max: 1.0,  best: 0.75 },
    trackPwm:        { min: 0.7,  max: 1.0,  best: 0.8  },
    chargePwm:       { min: 0.85, max: 1.0,  best: 1.0  },
    chargeThreshold: { min: 100,  max: 400,  best: 200  },
    evadePwm:        { min: 0.5,  max: 1.0,  best: 0.7  },
    edgeSteer:       { min: 0.1,  max: 0.7,  best: 0.5  },
    centerFill:      { min: 80,   max: 300,  best: 150  },
    laserAngle:      { min: 0.10, max: 0.50, best: 0.26 },
    // New flanking params
    flankAngle:      { min: 0.1,  max: 0.8,  best: 0.4  },
    flankThreshold:  { min: 200,  max: 600,  best: 400  },
    flankPwm:        { min: 0.6,  max: 1.0,  best: 0.85 },
    flankEnabled:    { min: 0,    max: 1,    best: 1    },
    // Counter-dodge params
    counterThresh:   { min: 10,   max: 40,   best: 20   },
    counterDodgeTime:{ min: 0.08, max: 0.30, best: 0.18 },
    counterPwm:      { min: 0.6,  max: 1.0,  best: 0.9  },
    // Tilt escape params
    tiltEscapeSpin:  { min: 0.0,  max: 0.8,  best: 0.5  },
};

// Fixed params
const FIXED = '--evadeFrontTime 0.45 --evadeRearTime 0.30 --evadeReverseRatio 0.45 --centerReturnTime 0.35';

function randomInRange(r) {
    return +(r.min + Math.random() * (r.max - r.min)).toFixed(4);
}

function roundParam(key, val) {
    if (['chargeThreshold', 'centerFill', 'flankThreshold'].includes(key)) return Math.round(val);
    if (key === 'flankEnabled') return val >= 0.5 ? 1 : 0;
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
    let totalWR = 0, profileResults = [];

    for (const ep of ENEMY_PROFILES) {
        const smartFlag = ep.smart ? '--smart' : '';
        const cmd = `node "${script}" --rounds ${rounds} ${args} --enemyColRadius ${ep.r} --enemyMass ${ep.m} --enemySpdFactor ${ep.s} ${smartFlag}`;
        try {
            const out = execSync(cmd, { timeout: 120000, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] });
            const d = JSON.parse(out);
            const wr = d.results.winRate;
            const to = d.results.timeouts / rounds;
            totalWR += wr * ep.w;
            profileResults.push({ label: ep.label, wr, to, smart: ep.smart });
        } catch (e) {
            return null;
        }
    }
    return { weightedWR: +totalWR.toFixed(4), profiles: profileResults };
}

// === MAIN ===
console.log(`Monte Carlo v3: ${NUM_CONFIGS} configs x ${ROUNDS_PER} rounds x ${ENEMY_PROFILES.length} profiles`);
console.log(`Profiles: ${ENEMY_PROFILES.map(p => `${p.label}(w=${p.w}${p.smart?',smart':''})`).join(', ')}`);
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
const baseResult = evaluate(bestCfg, ROUNDS_PER);
if (baseResult) {
    results.push({ cfg: bestCfg, ...baseResult });
    const smartWR = baseResult.profiles.filter(p => p.smart).reduce((s, p) => s + p.wr, 0) / baseResult.profiles.filter(p => p.smart).length;
    const basicWR = baseResult.profiles.filter(p => !p.smart).reduce((s, p) => s + p.wr, 0) / baseResult.profiles.filter(p => !p.smart).length;
    console.log(`WR=${(baseResult.weightedWR * 100).toFixed(1)}% smart=${(smartWR * 100).toFixed(1)}% basic=${(basicWR * 100).toFixed(1)}%`);
}

// Phase 1: Random search
for (let i = 1; i <= NUM_CONFIGS; i++) {
    const cfg = generateConfig();
    process.stdout.write(`[${String(i).padStart(3)}/${NUM_CONFIGS}] `);
    const res = evaluate(cfg, ROUNDS_PER);
    if (res) {
        results.push({ cfg, ...res });
        const tag = res.weightedWR >= (baseResult ? baseResult.weightedWR : 0.85) ? ' ** BETTER **' :
                    res.weightedWR >= 0.80 ? ' *' : '';
        console.log(`WR=${(res.weightedWR * 100).toFixed(1)}%${tag}`);
    } else {
        console.log('FAILED');
    }
}

const phase1Time = ((Date.now() - t0) / 1000).toFixed(1);
console.log(`\nPhase 1 complete in ${phase1Time}s`);

// Sort by weighted WR
results.sort((a, b) => b.weightedWR - a.weightedWR);

console.log(`\n=== TOP ${TOP_N} (Phase 1, ${ROUNDS_PER} rounds/profile) ===`);
for (let i = 0; i < Math.min(TOP_N, results.length); i++) {
    const r = results[i];
    const smartWR = r.profiles.filter(p => p.smart).reduce((s, p) => s + p.wr, 0) / r.profiles.filter(p => p.smart).length;
    const basicWR = r.profiles.filter(p => !p.smart).reduce((s, p) => s + p.wr, 0) / r.profiles.filter(p => !p.smart).length;
    console.log(`#${i + 1} WR=${(r.weightedWR * 100).toFixed(1)}% smart=${(smartWR * 100).toFixed(1)}% basic=${(basicWR * 100).toFixed(1)}%`);
    for (const [k, v] of Object.entries(r.cfg)) {
        const best = RANGES[k].best;
        if (v !== best) console.log(`     ${k}=${v} (was ${best})`);
    }
}

// Phase 2: Revalidate top-N with more rounds
console.log(`\n=== PHASE 2: Revalidating top ${TOP_N} at ${REVAL_ROUNDS} rounds/profile ===`);
const validated = [];
for (let i = 0; i < Math.min(TOP_N, results.length); i++) {
    const r = results[i];
    process.stdout.write(`[${i + 1}/${TOP_N}] Revalidating... `);
    const res = evaluate(r.cfg, REVAL_ROUNDS);
    if (res) {
        validated.push({ cfg: r.cfg, ...res });
        const smartWR = res.profiles.filter(p => p.smart).reduce((s, p) => s + p.wr, 0) / res.profiles.filter(p => p.smart).length;
        console.log(`WR=${(res.weightedWR * 100).toFixed(1)}% smart=${(smartWR * 100).toFixed(1)}%`);
    }
}

validated.sort((a, b) => b.weightedWR - a.weightedWR);

console.log(`\n${'='.repeat(70)}`);
console.log('FINAL RESULTS');
console.log('='.repeat(70));
for (let i = 0; i < validated.length; i++) {
    const r = validated[i];
    const smartProfiles = r.profiles.filter(p => p.smart);
    const basicProfiles = r.profiles.filter(p => !p.smart);
    const smartWR = smartProfiles.reduce((s, p) => s + p.wr, 0) / smartProfiles.length;
    const basicWR = basicProfiles.reduce((s, p) => s + p.wr, 0) / basicProfiles.length;
    console.log(`\n#${i + 1} | WeightedWR=${(r.weightedWR * 100).toFixed(2)}% | Smart=${(smartWR * 100).toFixed(1)}% | Basic=${(basicWR * 100).toFixed(1)}%`);
    console.log('   Per-profile:');
    for (const p of r.profiles) {
        console.log(`     ${p.label}: WR=${(p.wr * 100).toFixed(1)}% TO=${(p.to * 100).toFixed(1)}%`);
    }
    console.log('   Changed params:');
    for (const [k, v] of Object.entries(r.cfg)) {
        if (v !== RANGES[k].best) console.log(`     ${k}=${v} (default: ${RANGES[k].best})`);
    }
    console.log('   CLI: node headless.js --rounds 500 ' + FIXED + ' ' + buildArgs(r.cfg));
}

const totalTime = ((Date.now() - t0) / 1000).toFixed(1);
console.log(`\nTotal time: ${totalTime}s`);
