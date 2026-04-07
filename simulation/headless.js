#!/usr/bin/env node
'use strict';

// =============================================
// SUMOBOT HEADLESS SIMULATOR
// Usage: node headless.js --rounds 500 --kp 0.5 --searchPwm 0.5
// =============================================

// === CLI ARGS ===
const ARGS = (() => {
    const a = {};
    const v = process.argv.slice(2);
    for (let i = 0; i < v.length; i++) {
        if (v[i].startsWith('--')) {
            const k = v[i].slice(2);
            const val = v[i + 1];
            if (val !== undefined && !val.startsWith('--')) {
                a[k] = isNaN(val) ? val : parseFloat(val);
                i++;
            } else { a[k] = true; }
        }
    }
    return a;
})();

// === STRATEGY PARAMS (overridable via CLI) ===
const S = {
    kp:                 ARGS.kp             ?? 0.582,
    searchPwm:          ARGS.searchPwm      ?? 0.899,  // fraction of maxPwm
    trackPwm:           ARGS.trackPwm       ?? 0.99,
    chargePwm:          ARGS.chargePwm      ?? 0.976,
    chargeThreshold:    ARGS.chargeThreshold ?? 372,   // mm
    evadeFrontTime:     ARGS.evadeFrontTime  ?? 0.45,  // s
    evadeRearTime:      ARGS.evadeRearTime   ?? 0.30,
    evadeReverseRatio:  ARGS.evadeReverseRatio ?? 0.45, // fraction of evade spent reversing
    evadePwm:           ARGS.evadePwm        ?? 0.964,
    edgeSteer:          ARGS.edgeSteer       ?? 0.453,   // steering correction when single front sensor on line during charge
    centerReturnTime:   ARGS.centerReturnTime ?? 0.35, // seconds driving toward center after EVADE
    centerFill:         ARGS.centerFill      ?? 145,   // mm offset added to d0 when substituting for missing side laser
    searchDir:          ARGS.searchDir       ?? 1,     // 1=CW, -1=CCW
    pwmScale:           ARGS.pwmScale        ?? 1.0,   // global PWM multiplier
    // Flanking strategy params
    flankAngle:         ARGS.flankAngle      ?? 0.51,  // radians arc offset when approaching
    flankThreshold:     ARGS.flankThreshold  ?? 636,   // mm: start flanking above this distance
    flankPwm:           ARGS.flankPwm        ?? 0.658, // PWM during flanking approach
    flankEnabled:       ARGS.flankEnabled    ?? 1,     // 0=disabled, 1=enabled
    // Counter-charge params (IMU-based frontal dodge)
    counterThresh:      ARGS.counterThresh   ?? 18.824, // IMU forward decel threshold (m/s²)
    counterDodgeTime:   ARGS.counterDodgeTime ?? 0.212, // dodge duration (s)
    counterPwm:         ARGS.counterPwm      ?? 0.94,   // dodge PWM
    // Tilt escape enhancement
    tiltEscapeSpin:     ARGS.tiltEscapeSpin  ?? 0.275,  // spin component during tilt escape (0=pure reverse, 1=full spin)
};

const ROUNDS    = ARGS.rounds   ?? 200;
const MAX_TIME  = ARGS.maxTime  ?? 20;  // max seconds per round
const VERBOSE   = ARGS.verbose  ?? false;
const SMART_ENEMY = !!(ARGS.smart || ARGS.smartEnemy);
const ENEMY_COL_RADIUS = ARGS.enemyColRadius ?? 0.055;
const ENEMY_MASS = ARGS.enemyMass ?? 0.5;
const ENEMY_SPD_FACTOR = ARGS.enemySpdFactor ?? 1.0;
const USE_IMU = !!(ARGS.useIMU ?? true);  // IMU enabled by default
const USE_TILT = !!(ARGS.useTilt ?? true); // tilt physics enabled by default

// === PHYSICS CONFIG (SI — identical to visual sim) ===
const P = {
    mass: 0.5, robotL: 0.10, robotW: 0.10,
    wheelBase: 0.08, wheelRadius: 0.015, colRadius: 0.055,
    stallTorque: 0.0245, noLoadOmega: 32.7,
    mu: 0.6, latDamping: 30, rollDamping: 0.3, angDamping: 0.003,
    restitution: 0.15,
    arenaR: 0.385, arenaBorder: 0.022, g: 9.81,
    laserRange: 0.80, laserOffY: 0.025, laserAngle: ARGS.laserAngle ?? 0.526,  // radians, outward splay per sensor
    lineFX: 0.047, lineFY: 0.045, lineRX: -0.047,
};
P.inertia = P.mass * (P.robotL ** 2 + P.robotW ** 2) / 12;
P.noLoadSpeed = P.noLoadOmega * P.wheelRadius;
P.stallForce = P.stallTorque / P.wheelRadius;
P.tractionMax = P.mu * P.mass * P.g / 2;

// === MATH ===
const { cos, sin, atan2, hypot, abs, max, min, PI, sqrt, random, sign } = Math;
const TAU = PI * 2;
const DT = 1 / 240;

function angD(a, b) { return ((b - a) % TAU + 3 * PI) % TAU - PI; }
function clamp(v, lo, hi) { return max(lo, min(hi, v)); }
function l2w(r, lx, ly) {
    const c = cos(r.a), s = sin(r.a);
    return { x: r.x + lx * c - ly * s, y: r.y + lx * s + ly * c };
}

// === MOTOR MODEL ===
function motorForce(pwm, wheelLinSpeed, r) {
    const nls = r.noLoadSpeed || P.noLoadSpeed;
    const sf = r.stallForce || P.stallForce;
    const targetSpeed = (pwm / 255) * nls;
    const force = sf * (targetSpeed - wheelLinSpeed) / nls;
    return clamp(force, -sf * 2, sf * 2);
}

// === PHYSICS ===
function physicsStep(r, dt) {
    const m = r.mass || P.mass;
    const I = r.inertia || P.inertia;
    const baseTm = r.tractionMax || P.tractionMax;
    // Per-wheel traction: each wheel loses grip independently when its side is lifted
    const tmL = USE_TILT ? baseTm * max(0, 1 - (r.tiltL || 0) * 1.8) : baseTm;
    const tmR = USE_TILT ? baseTm * max(0, 1 - (r.tiltR || 0) * 1.8) : baseTm;
    const ca = cos(r.a), sa = sin(r.a);
    const vFwd = r.vx * ca + r.vy * sa;
    const vLat = -r.vx * sa + r.vy * ca;
    const vL = vFwd + r.omega * P.wheelBase / 2;
    const vR = vFwd - r.omega * P.wheelBase / 2;

    // Store previous velocity for IMU acceleration calc
    const prevVx = r.vx, prevVy = r.vy;

    let fL = motorForce(r.cmdL, vL, r);
    let fR = motorForce(r.cmdR, vR, r);
    if (abs(fL) > tmL) fL = tmL * sign(fL);
    if (abs(fR) > tmR) fR = tmR * sign(fR);

    const fFwd = fL + fR - P.rollDamping * vFwd * m;
    const torque = (fL - fR) * P.wheelBase / 2 - P.angDamping * r.omega;
    const avgTilt = ((r.tiltL || 0) + (r.tiltR || 0)) / 2;
    const latFactor = USE_TILT ? max(0, 1 - avgTilt * 1.5) : 1;
    const latMax = P.mu * m * P.g * 1.5 * latFactor;
    const fLat = clamp(-P.latDamping * vLat * m, -latMax, latMax);

    const fx = fFwd * ca - fLat * sa;
    const fy = fFwd * sa + fLat * ca;

    r.vx += (fx / m) * dt;
    r.vy += (fy / m) * dt;
    r.omega += (torque / I) * dt;
    r.x += r.vx * dt;
    r.y += r.vy * dt;
    r.a += r.omega * dt;

    // IMU: compute acceleration in robot frame
    const dvx = (r.vx - prevVx) / dt, dvy = (r.vy - prevVy) / dt;
    r.imuAx = dvx * ca + dvy * sa;
    r.imuAy = -dvx * sa + dvy * ca;
    r.imuGz = r.omega;

    // Tilt decay per wheel (spring back)
    if (USE_TILT) {
        if (r.tiltL) r.tiltL = max(0, r.tiltL - 3.0 * dt);
        if (r.tiltR) r.tiltR = max(0, r.tiltR - 3.0 * dt);
    }
}

// Continuous tilt: called every physics step when robots are close enough
function applyContinuousTilt(victim, attacker, dt) {
    if (!USE_TILT) return;
    const dx = attacker.x - victim.x, dy = attacker.y - victim.y;
    const dist = hypot(dx, dy);
    const contact = (victim.colR || P.colRadius) + (attacker.colR || P.colRadius);
    if (dist > contact * 1.2) return;

    const nx = dx / dist, ny = dy / dist;
    const relVx = attacker.vx - victim.vx, relVy = attacker.vy - victim.vy;
    const closing = -(relVx * nx + relVy * ny);
    const attackHeadingToward = cos(attacker.a) * (-nx) + sin(attacker.a) * (-ny);
    const motorPush = attackHeadingToward > 0.2 ? abs(attacker.cmdL + attacker.cmdR) / 510 : 0;
    const pushStrength = max(closing, motorPush * 0.3);
    if (pushStrength < 0.01) return;

    const cv = cos(victim.a), sv = sin(victim.a);
    const localX = nx * cv + ny * sv;
    const localY = -nx * sv + ny * cv;

    const frontBlock = localX > 0.3 ? max(0, 1 - (localX - 0.3) * 2.5) : 1;

    const mv = victim.mass || P.mass;
    const pushIntensity = clamp(pushStrength * 5, 0.2, 1.0);
    const rampRate = pushIntensity * frontBlock * 3.5 / mv;

    if (localX < -0.2) {
        victim.tiltL = min((victim.tiltL || 0) + rampRate * dt, 0.7);
        victim.tiltR = min((victim.tiltR || 0) + rampRate * dt, 0.7);
    } else if (localY > 0.1) {
        victim.tiltR = min((victim.tiltR || 0) + rampRate * 1.3 * dt, 0.7);
    } else if (localY < -0.1) {
        victim.tiltL = min((victim.tiltL || 0) + rampRate * 1.3 * dt, 0.7);
    }
}

function resolveCollision(a, b) {
    const dx = b.x - a.x, dy = b.y - a.y;
    const dist = hypot(dx, dy);
    const minD = (a.colR || P.colRadius) + (b.colR || P.colRadius);
    if (dist >= minD || dist < 0.001) return;
    const nx = dx / dist, ny = dy / dist;
    const ov = (minD - dist) / 2;
    a.x -= nx * ov; a.y -= ny * ov;
    b.x += nx * ov; b.y += ny * ov;
    const dvn = (a.vx - b.vx) * nx + (a.vy - b.vy) * ny;
    if (dvn <= 0) return;
    const ma = a.mass || P.mass, mb = b.mass || P.mass;
    const j = (1 + P.restitution) * dvn / (1 / ma + 1 / mb);
    a.vx -= (j / ma) * nx; a.vy -= (j / ma) * ny;
    b.vx += (j / mb) * nx; b.vy += (j / mb) * ny;

    // Tilt is now handled by applyContinuousTilt in physics loop
}

function isOut(r) { return hypot(r.x, r.y) > P.arenaR + (r.colR || P.colRadius) * 0.5; }

// === SENSORS ===
function linePos(r) {
    return [l2w(r, P.lineFX, -P.lineFY), l2w(r, P.lineFX, P.lineFY), l2w(r, P.lineRX, 0)];
}
function onLine(p) { return hypot(p.x, p.y) > P.arenaR - P.arenaBorder; }

function rayCast(ox, oy, ang, tx, ty, tr, maxR) {
    const dx = cos(ang), dy = sin(ang);
    const fx = ox - tx, fy = oy - ty;
    const b = 2 * (fx * dx + fy * dy);
    const c = fx * fx + fy * fy - tr * tr;
    const disc = b * b - 4 * c;
    if (disc < 0) return maxR;
    const sq = sqrt(disc);
    const t1 = (-b - sq) / 2;
    if (t1 > 0 && t1 < maxR) return t1;
    const t2 = (-b + sq) / 2;
    if (t2 > 0 && t2 < maxR) return t2;
    return maxR;
}

function getLaser(r, tgt) {
    const hl = P.robotL / 2;
    const tr = tgt.colR || P.colRadius;
    const lp = l2w(r, hl, -P.laserOffY);
    const cp = l2w(r, hl, 0);
    const rp = l2w(r, hl, P.laserOffY);
    return {
        d0: rayCast(cp.x, cp.y, r.a, tgt.x, tgt.y, tr, P.laserRange),
        d1: rayCast(lp.x, lp.y, r.a - P.laserAngle, tgt.x, tgt.y, tr, P.laserRange),
        d2: rayCast(rp.x, rp.y, r.a + P.laserAngle, tgt.x, tgt.y, tr, P.laserRange),
    };
}

// === BOT AI (parameterized by S) ===
let aiSt, evT, evD, evM, crT;
let lastSeenDir = 0;   // last known direction to enemy: +1=left, -1=right
let searchTimer = 0;   // time spent in SEARCH without detection
let curSearchDir;       // current search rotation direction

// IMU state
let imuHeading = 0;        // accumulated yaw (rad)
let imuSearchStart = 0;    // heading at start of search
let impactReactT = 0;      // time remaining in IMPACT_REACT state
let impactReactDir = 0;    // spin direction for impact reaction
let tiltEscapeT = 0;       // time remaining in TILT_ESCAPE state
let tiltEscapeDir = 0;     // spin direction during tilt escape

// Flanking state
let flankDir = 0;          // +1=arc left, -1=arc right (relative to enemy)
let flankTimer = 0;        // time spent in current flank maneuver
let counterDodgeT = 0;     // time remaining in counter-dodge
let counterDodgeDir = 0;   // dodge direction

function botAI(bot, ene, dt) {
    const maxPwm = 255 * S.pwmScale;
    const lr = linePos(bot).map(onLine);
    const las = getLaser(bot, ene);
    const d0mm = las.d0 * 1000;
    const d1mm = las.d1 * 1000, d2mm = las.d2 * 1000;
    const rangeMax = P.laserRange * 1000 * 0.95;
    const det0 = d0mm < rangeMax;
    const det1 = d1mm < rangeMax;
    const det2 = d2mm < rangeMax;
    const anyLaserDet = det0 || det1 || det2;
    // Effective side distances: center fills gap with offset to preserve steering direction
    const eff1 = det1 ? d1mm : (det0 ? d0mm + S.centerFill : rangeMax);
    const eff2 = det2 ? d2mm : (det0 ? d0mm + S.centerFill : rangeMax);

    // === IMU update ===
    if (USE_IMU) {
        imuHeading += bot.imuGz * dt;

        // --- TILT ESCAPE: being lifted → reverse + spin to escape ---
        // Real robot: MPU6050 gives overall tilt via accel Z drop + lateral accel for side detection
        if (tiltEscapeT > 0) {
            tiltEscapeT -= dt;
            const spinFactor = S.tiltEscapeSpin;
            const rev = -maxPwm;
            bot.cmdL = rev * (1 - spinFactor) + tiltEscapeDir * maxPwm * spinFactor;
            bot.cmdR = rev * (1 - spinFactor) - tiltEscapeDir * maxPwm * spinFactor;
            aiSt = 'TILT_ESC';
            return lr;
        }
        // Detect tilt using IMU data available on real robot:
        // - Forward accel (imuAx) spike + lateral accel (imuAy) indicate being pushed/lifted
        // - accelZ < 9.0 m/s² means not fully on ground (normal = 9.81)
        // In simulation: use tiltL/tiltR as proxy for what MPU6050 would sense
        const maxTilt = max(bot.tiltL || 0, bot.tiltR || 0);
        if (maxTilt > 0.25) {
            tiltEscapeT = 0.2 + maxTilt * 0.3;
            // Direction from lateral IMU: imuAy tells which side the force comes from
            // (real robot would use the same imuAy reading)
            tiltEscapeDir = bot.imuAy > 0 ? 1 : -1;
            const spinFactor = S.tiltEscapeSpin;
            bot.cmdL = -maxPwm * (1 - spinFactor) + tiltEscapeDir * maxPwm * spinFactor;
            bot.cmdR = -maxPwm * (1 - spinFactor) - tiltEscapeDir * maxPwm * spinFactor;
            aiSt = 'TILT_ESC';
            return lr;
        }

        // --- IMPACT REACT: lateral hit detected → spin toward source ---
        if (impactReactT > 0) {
            impactReactT -= dt;
            // If we now see enemy with lasers, abort react and go to TRACK
            if (anyLaserDet) { impactReactT = 0; }
            else {
                bot.cmdL = impactReactDir * maxPwm;
                bot.cmdR = -impactReactDir * maxPwm;
                aiSt = 'IMPACT';
                return lr;
            }
        }
        // Detect lateral impact (not during EVADE/CHARGE which have their own accel)
        if (aiSt === 'SEARCH' || aiSt === 'CENTER' || aiSt === 'TRACK') {
            const latImpact = bot.imuAy; // positive = force from right
            if (abs(latImpact) > 15) {   // ~1.5g lateral shock
                impactReactT = 0.25;     // spin for 250ms toward source
                impactReactDir = latImpact > 0 ? 1 : -1; // spin toward source
            }
        }

        // --- COUNTER-DODGE: frontal collision detected → dodge laterally then re-engage ---
        if (counterDodgeT > 0) {
            counterDodgeT -= dt;
            bot.cmdL = counterDodgeDir * maxPwm * S.counterPwm;
            bot.cmdR = -counterDodgeDir * maxPwm * S.counterPwm;
            aiSt = 'COUNTER';
            return lr;
        }
        // Detect head-on collision (strong backward deceleration while we were charging)
        if ((aiSt === 'CHARGE' || aiSt === 'TRACK') && bot.imuAx < -S.counterThresh) {
            counterDodgeT = S.counterDodgeTime;
            // Dodge to the side where enemy isn't (use last laser readings)
            counterDodgeDir = det1 && !det2 ? -1 : det2 && !det1 ? 1 : (random() < 0.5 ? 1 : -1);
        }
    }

    if (evT > 0) {
        evT -= dt;
        const revT = evM === 'rear' ? S.evadeRearTime : S.evadeFrontTime * S.evadeReverseRatio;
        if (evM === 'rear') {
            bot.cmdL = maxPwm * S.evadePwm; bot.cmdR = maxPwm * S.evadePwm;
        } else if (evT > S.evadeFrontTime - revT) {
            bot.cmdL = -maxPwm * S.evadePwm; bot.cmdR = -maxPwm * S.evadePwm;
        } else {
            bot.cmdL = evD * maxPwm * 0.8; bot.cmdR = -evD * maxPwm * 0.8;
        }
        aiSt = 'EVADE';
        return lr;
    }

    // === CENTER RETURN (after EVADE, drive forward briefly) ===
    // Real robot: no position knowledge, just drive forward for centerReturnTime
    // The evade already turned us inward, so forward = roughly toward center
    if (crT > 0) {
        crT -= dt;
        const noLine = !lr[0] && !lr[1] && !lr[2];
        const noDet = !det0 && !det1 && !det2;
        if (noLine && noDet) {
            // Simple forward drive — no position/heading needed
            bot.cmdL = maxPwm * 0.7;
            bot.cmdR = maxPwm * 0.7;
            aiSt = 'CENTER';
            return lr;
        }
        crT = 0; // abort: line or enemy detected
    }

    if (lr[0] || lr[1] || lr[2]) {
        const fwdDet = det0 || det1 || det2;
        const engaging = fwdDet && (aiSt === 'CHARGE' || aiSt === 'TRACK');
        const singleFront = (lr[0] || lr[1]) && !(lr[0] && lr[1]) && !lr[2];

        if (engaging && singleFront) {
            // Pushing enemy near edge: steer away from triggered sensor, keep charging
            const minD = min(det0 ? d0mm : 9999, det1 ? d1mm : 9999, det2 ? d2mm : 9999);
            const err = eff1 - eff2;
            const cor = S.kp * err;
            const base = minD < S.chargeThreshold ? maxPwm * S.chargePwm : maxPwm * S.trackPwm;
            const edgeSteer = lr[0] ? maxPwm * S.edgeSteer : -maxPwm * S.edgeSteer;
            bot.cmdL = clamp(base + cor + edgeSteer, -maxPwm, maxPwm);
            bot.cmdR = clamp(base - cor - edgeSteer, -maxPwm, maxPwm);
            aiSt = 'CHARGE';
            return lr;
        }

        // Full evade: both front, rear only, or not engaging
        if (lr[2] && !lr[0] && !lr[1]) { evT = S.evadeRearTime; evM = 'rear'; }
        else {
            evT = S.evadeFrontTime; evM = 'front';
            evD = lr[0] && !lr[1] ? 1 : lr[1] && !lr[0] ? -1 : (random() < 0.5 ? 1 : -1);
        }
        crT = S.centerReturnTime;
        aiSt = 'EVADE';
        return lr;
    }

    const anyDet = det0 || det1 || det2;
    if (!anyDet) {
        // Track entry into SEARCH for heading-based optimization
        if (aiSt !== 'SEARCH' && USE_IMU) { imuSearchStart = imuHeading; }
        aiSt = 'SEARCH';
        flankTimer = 0; // reset flank state when losing target

        // IMU: if we've spun >360° without finding anything → drive forward to relocate
        // (no position knowledge — only IMU heading available on real robot)
        const searchedAngle = USE_IMU ? abs(imuHeading - imuSearchStart) : 0;
        const fullScanDone = searchedAngle > TAU * 1.1; // >396°

        if (fullScanDone) {
            // Full scan done: drive forward briefly to change position, then resume spin
            // Line sensors will prevent going off the ring
            bot.cmdL = maxPwm * S.searchPwm * 0.7;
            bot.cmdR = maxPwm * S.searchPwm * 0.7;
            // Reset scan counter after driving forward a bit
            if (searchedAngle > TAU * 1.3) imuSearchStart = imuHeading;
        } else {
            // Pure spin search — sensor-only, no position needed
            bot.cmdL = S.searchDir * maxPwm * S.searchPwm;
            bot.cmdR = -S.searchDir * maxPwm * S.searchPwm;
        }
    } else {
        const minD = min(det0 ? d0mm : 9999, det1 ? d1mm : 9999, det2 ? d2mm : 9999);
        const err = eff1 - eff2;
        const cor = S.kp * err;

        // === FLANKING STRATEGY ===
        // When enemy is far (> flankThreshold), arc to approach from side
        // No position check needed — line sensors protect from going off-ring
        const shouldFlank = S.flankEnabled && minD > S.flankThreshold;

        if (shouldFlank) {
            aiSt = 'FLANK';
            flankTimer += dt;
            // Pick flank direction: prefer the side where sensor sees farther (enemy edge)
            if (flankTimer < dt * 2) {
                flankDir = det1 && !det2 ? -1 : det2 && !det1 ? 1 : (random() < 0.5 ? 1 : -1);
            }
            // Arc: add angular offset to the tracking direction
            const arcOffset = flankDir * S.flankAngle;
            const arcCor = S.kp * err + arcOffset * 150;
            const base = maxPwm * S.flankPwm;
            bot.cmdL = clamp(base + arcCor, -maxPwm, maxPwm);
            bot.cmdR = clamp(base - arcCor, -maxPwm, maxPwm);
        } else {
            flankTimer = 0;
            let base;
            if (minD < S.chargeThreshold) { aiSt = 'CHARGE'; base = maxPwm * S.chargePwm; }
            else { aiSt = 'TRACK'; base = maxPwm * S.trackPwm; }
            bot.cmdL = clamp(base + cor, -maxPwm, maxPwm);
            bot.cmdR = clamp(base - cor, -maxPwm, maxPwm);
        }
    }
    return lr;
}

// === ENEMY AI (multi-behavior, same as visual sim) ===
let eaiSt, eEvT, eEvD, eEvM;
let eBehav, eBehavT, eWanderA, eOrbitDir;
let mTime;

function pickBehavior() {
    const c = ['WANDER', 'ORBIT', 'AGGRESSIVE', 'DODGE', 'ZIGZAG'];
    eBehav = c[Math.floor(random() * c.length)];
    eBehavT = 1.5 + random() * 3;
    eWanderA = random() * TAU;
    eOrbitDir = random() < 0.5 ? 1 : -1;
}

function eneAI(ene, bot, dt) {
    const maxPwm = 255 * S.pwmScale * 0.85;
    const lr = linePos(ene).map(onLine);

    if (eEvT > 0) {
        eEvT -= dt;
        if (eEvM === 'rear') { ene.cmdL = maxPwm * 0.7; ene.cmdR = maxPwm * 0.7; }
        else if (eEvT > 0.15) { ene.cmdL = -maxPwm * 0.6; ene.cmdR = -maxPwm * 0.6; }
        else { ene.cmdL = eEvD * maxPwm * 0.7; ene.cmdR = -eEvD * maxPwm * 0.7; }
        eaiSt = 'EVADE'; return lr;
    }
    if (lr[0] || lr[1] || lr[2]) {
        if (lr[2] && !lr[0] && !lr[1]) { eEvT = 0.25; eEvM = 'rear'; }
        else { eEvT = 0.35; eEvM = 'front'; eEvD = lr[0] && !lr[1] ? 1 : lr[1] && !lr[0] ? -1 : (random() < 0.5 ? 1 : -1); }
        eaiSt = 'EVADE'; return lr;
    }

    eBehavT -= dt;
    if (eBehavT <= 0) pickBehavior();
    eWanderA += (random() - 0.5) * 3 * dt;

    const toP = atan2(bot.y - ene.y, bot.x - ene.x);
    const toC = atan2(-ene.y, -ene.x);
    const dC = hypot(ene.x, ene.y);
    const dP = hypot(bot.x - ene.x, bot.y - ene.y);
    const innerR = P.arenaR - P.arenaBorder;
    const edge = max(0, (dC - innerR * 0.7) / (innerR * 0.3));

    let steer, fwd;
    if (eBehav === 'WANDER')     { eaiSt = 'WANDER'; steer = eWanderA; fwd = maxPwm * 0.55; }
    else if (eBehav === 'ORBIT') { eaiSt = 'ORBIT'; steer = toC + eOrbitDir * PI / 2; fwd = maxPwm * 0.6; }
    else if (eBehav === 'AGGRESSIVE') { eaiSt = dP < 0.15 ? 'CHARGE' : 'TRACK'; steer = toP; fwd = dP < 0.15 ? maxPwm : maxPwm * 0.7; }
    else if (eBehav === 'DODGE') { eaiSt = 'DODGE'; steer = toP + eOrbitDir * PI / 2; fwd = maxPwm * 0.65; }
    else { eaiSt = 'ZIGZAG'; steer = toP + sin(mTime * 4) * 0.8; fwd = maxPwm * 0.6; }

    if (edge > 0) steer = steer * (1 - edge) + toC * edge;
    const cor = angD(ene.a, steer) * 150;
    ene.cmdL = clamp(fwd + cor, -255, 255);
    ene.cmdR = clamp(fwd - cor, -255, 255);
    return lr;
}

// === SMART ENEMY AI (omniscient, remote-controlled) ===
// Full knowledge of bot position, heading, velocity, AI state.
// 7 tactics with weighted scoring + randomness for unpredictability.
let eSE = {};

function resetSE() {
    eSE = { tactic: 'FLANK', timer: 0, side: random() < 0.5 ? 1 : -1, jukeT: 0, hesitate: 0 };
}

function steerTo(r, ang, spd, mp) {
    const c = clamp(angD(r.a, ang) * 250, -mp, mp);
    r.cmdL = clamp(spd + c, -mp, mp);
    r.cmdR = clamp(spd - c, -mp, mp);
}

function smartEneAI(ene, bot, dt) {
    const mp = 255;
    const lr = linePos(ene).map(onLine);

    // --- Reactive evade (safety net) ---
    if (eEvT > 0) {
        eEvT -= dt;
        steerTo(ene, atan2(-ene.y, -ene.x), mp * 0.85, mp);
        eaiSt = 'EVADE';
        return lr;
    }
    if (lr[0] || lr[1] || lr[2]) {
        const d = hypot(bot.x - ene.x, bot.y - ene.y);
        const sf = (lr[0] || lr[1]) && !(lr[0] && lr[1]) && !lr[2];
        if (d < 0.14 && sf) {
            // Edge-push: keep pushing bot while near line
            const tb = atan2(bot.y - ene.y, bot.x - ene.x);
            steerTo(ene, tb + (lr[0] ? 0.25 : -0.25), mp, mp);
            eaiSt = 'EDGE_PUSH';
            return lr;
        }
        eEvT = 0.2;
        eaiSt = 'EVADE';
        return lr;
    }

    // --- Omniscient analysis ---
    const dx = bot.x - ene.x, dy = bot.y - ene.y;
    const dist = hypot(dx, dy);
    const toBot = atan2(dy, dx);
    const inCone = abs(angD(bot.a, atan2(-dy, -dx))) < (P.laserAngle + 0.18) && dist < P.laserRange;
    const myR = hypot(ene.x, ene.y);
    const botR = hypot(bot.x, bot.y);
    const botSpd = hypot(bot.vx, bot.vy);
    const closing = (bot.vx * dx + bot.vy * dy) / (dist + 1e-6);
    // Predicted bot position in 0.25s
    const px = bot.x + bot.vx * 0.25, py = bot.y + bot.vy * 0.25;
    const toPred = atan2(py - ene.y, px - ene.x);

    // --- Kill zone: bot near edge + we have center → committed charge ---
    const botEdge = P.arenaR - botR;
    if (botEdge < 0.07 && myR < botR - 0.04 && dist < 0.35) {
        steerTo(ene, toPred, mp, mp);
        eaiSt = 'KILL';
        return lr;
    }

    // --- Tactic selection (scored + random) ---
    eSE.timer -= dt;
    if (eSE.timer <= 0) {
        eSE.timer = 1.0 + random() * 1.5;
        eSE.side = random() < 0.5 ? 1 : -1;
        eSE.jukeT = 0;
        // 12% chance of brief hesitation on tactic switch
        if (random() < 0.12) eSE.hesitate = 0.08 + random() * 0.14;

        // Immediate reactive picks
        if (aiSt === 'EVADE') { eSE.tactic = 'EXPLOIT_EVADE'; }
        else if (closing > 0.15 && dist < 0.22 && (P.arenaR - botR) > 0.06) { eSE.tactic = 'MATADOR'; }
        else {
            // Weighted scoring
            const sc = {
                FLANK:     30 + (inCone && dist > 0.15 ? 25 : 0) + (aiSt === 'TRACK' ? 10 : 0),
                RUSH:      20 + (!inCone ? 40 : 0) + (botSpd < 0.05 ? 15 : 0) + (botEdge < 0.1 ? 25 : 0),
                SHADOW:    20 + (aiSt === 'SEARCH' ? 40 : 0),
                EDGE_TRAP: 20 + (myR < botR - 0.03 ? 35 : 0) + (botEdge < 0.1 ? 25 : 0),
                BULL:      10 + (dist < 0.15 ? 15 : 0) + (aiSt === 'SEARCH' ? 20 : 0),
                JUKE:       5 + (dist < 0.2 ? 15 : 0),
                MATADOR:    5 + (closing > 0.08 ? 15 : 0),
            };
            // 30% randomness band
            for (const k in sc) sc[k] *= (0.7 + random() * 0.6);
            let best = 'FLANK', bv = -1;
            for (const k in sc) if (sc[k] > bv) { bv = sc[k]; best = k; }
            eSE.tactic = best;
        }
    }

    // --- Hesitation (human reaction delay) ---
    if (eSE.hesitate > 0) {
        eSE.hesitate -= dt;
        ene.cmdL = ene.cmdL * 0.3; ene.cmdR = ene.cmdR * 0.3;
        eaiSt = 'THINK';
        return lr;
    }

    // --- Execute tactic ---
    let tA, tS;

    switch (eSE.tactic) {
        case 'FLANK': {
            // Circle to bot's blind side (>60° from heading), then rush
            const fa = bot.a + eSE.side * PI * 0.65;
            let fx = bot.x + cos(fa) * 0.18, fy = bot.y + sin(fa) * 0.18;
            const fr = hypot(fx, fy);
            if (fr > P.arenaR - 0.05) { const k = (P.arenaR - 0.05) / fr; fx *= k; fy *= k; }
            const tf = atan2(fy - ene.y, fx - ene.x);
            const df = hypot(fx - ene.x, fy - ene.y);
            if (df > 0.07 && inCone) { tA = tf; tS = mp * 0.8; }
            else if (dist < 0.30) { tA = toPred; tS = mp; }
            else { tA = tf; tS = mp * 0.75; }
            eaiSt = 'FLANK';
            break;
        }
        case 'MATADOR': {
            // Face bot, wait for charge, dodge laterally at last moment
            if (dist > 0.12 || closing < 0.06) {
                tA = toBot; tS = mp * 0.12;
                eaiSt = 'BAIT';
            } else {
                let da = toBot + eSE.side * PI * 0.45;
                // Check dodge won't go off arena
                if (hypot(ene.x + cos(da) * 0.15, ene.y + sin(da) * 0.15) > P.arenaR - 0.05)
                    da = toBot - eSE.side * PI * 0.45;
                tA = da; tS = mp;
                eaiSt = 'DODGE';
            }
            break;
        }
        case 'RUSH': {
            // Full speed at predicted position
            tA = toPred; tS = mp;
            eaiSt = 'RUSH';
            break;
        }
        case 'SHADOW': {
            // Stay behind bot, match spin, then backstab
            const bh = bot.a + PI;
            const shX = bot.x + cos(bh) * 0.13, shY = bot.y + sin(bh) * 0.13;
            const toSh = atan2(shY - ene.y, shX - ene.x);
            const dSh = hypot(shX - ene.x, shY - ene.y);
            if (dSh < 0.08) { tA = toBot; tS = mp; eaiSt = 'BACKSTAB'; }
            else { tA = toSh; tS = mp * 0.75; eaiSt = 'SHADOW'; }
            break;
        }
        case 'EDGE_TRAP': {
            // Position between bot and center, push outward
            const bc = atan2(-bot.y, -bot.x);
            const trX = bot.x + cos(bc) * 0.13, trY = bot.y + sin(bc) * 0.13;
            const toTr = atan2(trY - ene.y, trX - ene.x);
            const dTr = hypot(trX - ene.x, trY - ene.y);
            if (dTr > 0.06) { tA = toTr; tS = mp * 0.75; eaiSt = 'TRAP_POS'; }
            else { tA = toBot; tS = mp * 0.9; eaiSt = 'TRAP_PUSH'; }
            break;
        }
        case 'JUKE': {
            // Rapid zigzag to overwhelm P-controller, then straight charge
            eSE.jukeT += dt;
            const jd = Math.floor(eSE.jukeT / 0.15) % 2 === 0 ? 1 : -1;
            if (eSE.jukeT < 0.3) { tA = toBot + jd * 0.65; tS = mp * 0.85; eaiSt = 'JUKE'; }
            else { tA = toPred; tS = mp; eaiSt = 'JUKE_CHG'; }
            break;
        }
        case 'BULL': {
            // Retreat to blind spot at distance, then full-speed charge with momentum
            if (dist < 0.25 || inCone) {
                // Phase 1: move to flanking position at distance
                const blindAng = bot.a + eSE.side * PI * 0.7;
                let bx = bot.x + cos(blindAng) * 0.28, by = bot.y + sin(blindAng) * 0.28;
                const br = hypot(bx, by);
                if (br > P.arenaR - 0.05) { const k = (P.arenaR - 0.05) / br; bx *= k; by *= k; }
                tA = atan2(by - ene.y, bx - ene.x); tS = mp * 0.85;
                eaiSt = 'BULL_BACK';
            } else {
                // Phase 2: enough runway + blind spot → full charge
                tA = toPred; tS = mp;
                eaiSt = 'BULL_CHG';
            }
            break;
        }
        case 'EXPLOIT_EVADE': {
            // Rush during bot's predictable EVADE sequence
            tA = toPred; tS = mp;
            eaiSt = 'EXPLOIT';
            break;
        }
        default: { tA = toBot; tS = mp * 0.7; eaiSt = 'ASSESS'; }
    }

    // --- Proactive edge blend ---
    const safeR = P.arenaR - 0.04;
    if (myR > safeR) {
        const u = clamp((myR - safeR) / 0.03, 0, 1);
        tA += angD(tA, atan2(-ene.y, -ene.x)) * u;
    }

    // --- Human imprecision (joystick noise + throttle variation) ---
    tA += (random() - 0.5) * 0.2;   // ±0.1 rad steering noise (~6°)
    tS *= (0.82 + random() * 0.18);  // 82-100% speed variation

    steerTo(ene, tA, tS, mp);
    return lr;
}

// === ROUND SIMULATION ===
function makeRobot(x, y, a, colR, mass, spdFactor) {
    mass = mass || P.mass;
    spdFactor = spdFactor || 1.0;
    return {
        x, y, a, vx: 0, vy: 0, omega: 0, cmdL: 0, cmdR: 0,
        colR: colR || P.colRadius,
        mass,
        inertia: mass * (P.robotL ** 2 + P.robotW ** 2) / 12,
        stallForce: P.stallForce * spdFactor,
        noLoadSpeed: P.noLoadSpeed * spdFactor,
        tractionMax: P.mu * mass * P.g / 2,
        tiltL: 0, tiltR: 0, imuAx: 0, imuAy: 0, imuGz: 0,
    };
}

function runRound() {
    // Random spawn
    const bAng = random() * TAU;
    const eAng = bAng + PI * (0.6 + random() * 0.8);
    const bR = 0.08 + random() * 0.06;
    const eR = 0.08 + random() * 0.06;
    const bFace = bAng + PI + (random() - 0.5) * 1.2;
    const eFace = eAng + PI + (random() - 0.5) * 1.2;

    const bot = makeRobot(cos(bAng) * bR, sin(bAng) * bR, bFace, P.colRadius, P.mass, 1.0);
    const ene = makeRobot(cos(eAng) * eR, sin(eAng) * eR, eFace, ENEMY_COL_RADIUS, ENEMY_MASS, ENEMY_SPD_FACTOR);

    // Reset AI state
    aiSt = 'SEARCH'; eaiSt = 'SEARCH';
    evT = 0; evD = 0; evM = 'front'; crT = 0;
    lastSeenDir = 0; searchTimer = 0; curSearchDir = S.searchDir;
    imuHeading = 0; imuSearchStart = 0; impactReactT = 0; tiltEscapeT = 0; tiltEscapeDir = 0;
    flankDir = 0; flankTimer = 0; counterDodgeT = 0; counterDodgeDir = 0;
    eEvT = 0; eEvD = 0; eEvM = 'front';
    eBehav = 'ORBIT'; eBehavT = 2 + random() * 2;
    eWanderA = random() * TAU; eOrbitDir = random() < 0.5 ? 1 : -1;
    if (SMART_ENEMY) resetSE();
    mTime = 0;

    // Simulate (no countdown — start immediately)
    const aiDt = 1 / 60; // AI runs at 60Hz
    let aiAccum = 0;

    while (mTime < MAX_TIME) {
        aiAccum += DT;
        if (aiAccum >= aiDt) {
            botAI(bot, ene, aiAccum);
            if (SMART_ENEMY) smartEneAI(ene, bot, aiAccum);
            else eneAI(ene, bot, aiAccum);
            aiAccum = 0;
        }

        physicsStep(bot, DT);
        physicsStep(ene, DT);
        resolveCollision(bot, ene);
        applyContinuousTilt(bot, ene, DT);
        applyContinuousTilt(ene, bot, DT);
        mTime += DT;

        const bOut = isOut(bot), eOut = isOut(ene);
        if (bOut || eOut) {
            const winner = (bOut && eOut) ? 'draw' : eOut ? 'bot' : 'enemy';
            return { winner, duration: mTime, botState: aiSt, eneState: eaiSt, eneTactic: SMART_ENEMY ? eSE.tactic : eBehav };
        }
    }

    // Timeout — closest to center wins
    const bDist = hypot(bot.x, bot.y);
    const eDist = hypot(ene.x, ene.y);
    const winner = bDist < eDist ? 'bot' : eDist < bDist ? 'enemy' : 'draw';
    return { winner, duration: mTime, timeout: true, botState: aiSt, eneState: eaiSt, eneTactic: SMART_ENEMY ? eSE.tactic : eBehav };
}

// === BATCH RUN ===
function runBatch() {
    const t0 = Date.now();
    const results = [];
    let botWins = 0, eneWins = 0, draws = 0;
    let totalDur = 0, botWinDur = 0, eneWinDur = 0;
    let timeouts = 0;
    const stateCounts = {};

    for (let i = 0; i < ROUNDS; i++) {
        const r = runRound();
        results.push(r);
        totalDur += r.duration;
        if (r.winner === 'bot')   { botWins++; botWinDur += r.duration; }
        if (r.winner === 'enemy') { eneWins++; eneWinDur += r.duration; }
        if (r.winner === 'draw')  draws++;
        if (r.timeout) timeouts++;

        // Track what state bot was in at end
        const sk = r.botState || 'UNKNOWN';
        stateCounts[sk] = (stateCounts[sk] || 0) + 1;
    }

    const elapsed = ((Date.now() - t0) / 1000).toFixed(2);

    const output = {
        params: { ...S },
        rounds: ROUNDS,
        maxTime: MAX_TIME,
        elapsed: elapsed + 's',
        results: {
            botWins,
            eneWins,
            draws,
            timeouts,
            winRate: +(botWins / ROUNDS).toFixed(4),
            avgDuration: +(totalDur / ROUNDS).toFixed(2),
            botWinAvgDuration: botWins > 0 ? +(botWinDur / botWins).toFixed(2) : null,
            eneWinAvgDuration: eneWins > 0 ? +(eneWinDur / eneWins).toFixed(2) : null,
        },
        botEndStates: stateCounts,
    };

    if (SMART_ENEMY) {
        const lossTactics = {}, winTactics = {};
        results.forEach(r => {
            if (r.winner === 'enemy' && r.eneTactic) lossTactics[r.eneTactic] = (lossTactics[r.eneTactic] || 0) + 1;
            if (r.winner === 'bot' && r.eneTactic) winTactics[r.eneTactic] = (winTactics[r.eneTactic] || 0) + 1;
        });
        output.smartEnemy = { lossTactics, winTactics };
    }

    if (VERBOSE) {
        output.roundDetails = results;
    }

    console.log(JSON.stringify(output, null, 2));
}

runBatch();
