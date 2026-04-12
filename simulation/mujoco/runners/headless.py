"""Headless batch runner — replaces simulation/headless.js.

Usage:
    python -m runners.headless --rounds 200
    python -m runners.headless --rounds 500 --smart --kp 0.6
    python -m runners.headless --rounds 100 --verbose
"""

import argparse
import json
import time
import sys
import os

# Allow running from the mujoco/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from physics.sim_engine import SumoSimulation
from ai.bot_ai import BotAI
from ai.enemy_ai import EnemyAI, SmartEnemyAI
from ai.strategy_params import DEFAULT_PARAMS, merge_params
from utils.spawn import random_spawn


def parse_args():
    p = argparse.ArgumentParser(description='SumoBot MuJoCo Headless Simulator')
    p.add_argument('--rounds', type=int, default=200)
    p.add_argument('--maxTime', type=float, default=20.0)
    p.add_argument('--smart', action='store_true', help='Use smart omniscient enemy')
    p.add_argument('--verbose', action='store_true')
    # Strategy param overrides
    for k, v in DEFAULT_PARAMS.items():
        p.add_argument(f'--{k}', type=type(v), default=None)
    return p.parse_args()


def run_round(sim: SumoSimulation, bot_ai: BotAI, enemy_ai,
              max_time: float, smart: bool) -> dict:
    """Simulate one round. Returns result dict."""
    spawn = random_spawn()
    sim.reset(spawn['bot_pos'], spawn['bot_angle'],
              spawn['ene_pos'], spawn['ene_angle'])
    bot_ai.reset()
    enemy_ai.reset()

    ai_dt = 1.0 / 60  # AI runs at 60 Hz
    ai_accum = 0.0
    physics_dt = sim.model.opt.timestep

    bot_pwm_l, bot_pwm_r = 0.0, 0.0
    ene_pwm_l, ene_pwm_r = 0.0, 0.0

    while sim.time < max_time:
        ai_accum += physics_dt
        if ai_accum >= ai_dt:
            # Bot AI: sensor-only
            bot_sensors = sim.get_bot_sensors()
            bot_pwm_l, bot_pwm_r = bot_ai.update(bot_sensors, ai_accum)

            # Enemy AI: omniscient
            ene_sensors = sim.get_ene_sensors()
            bot_pose = sim.get_bot_pose()
            ene_pose = sim.get_ene_pose()

            if smart:
                ene_pwm_l, ene_pwm_r = enemy_ai.update(
                    ene_sensors, ene_pose, bot_pose, ai_accum,
                    bot_ai_state=bot_ai.state)
            else:
                ene_pwm_l, ene_pwm_r = enemy_ai.update(
                    ene_sensors, ene_pose, bot_pose, ai_accum)

            ai_accum = 0.0

        sim.step(bot_pwm_l, bot_pwm_r, ene_pwm_l, ene_pwm_r)

        b_out = sim.is_out('bot')
        e_out = sim.is_out('enemy')
        if b_out or e_out:
            if b_out and e_out:
                winner = 'draw'
            elif e_out:
                winner = 'bot'
            else:
                winner = 'enemy'
            return {
                'winner': winner,
                'duration': round(sim.time, 4),
                'botState': bot_ai.state,
                'eneState': enemy_ai.state,
                'eneTactic': enemy_ai.tactic if smart else enemy_ai.behav,
            }

    # Timeout — closest to center wins
    bot_pose = sim.get_bot_pose()
    ene_pose = sim.get_ene_pose()
    from math import hypot
    b_dist = hypot(bot_pose['x'], bot_pose['y'])
    e_dist = hypot(ene_pose['x'], ene_pose['y'])
    if b_dist < e_dist:
        winner = 'bot'
    elif e_dist < b_dist:
        winner = 'enemy'
    else:
        winner = 'draw'

    return {
        'winner': winner,
        'duration': round(sim.time, 4),
        'timeout': True,
        'botState': bot_ai.state,
        'eneState': enemy_ai.state,
        'eneTactic': enemy_ai.tactic if smart else enemy_ai.behav,
    }


def run_batch(args):
    """Run multiple rounds and output JSON statistics."""
    # Build strategy params from CLI overrides
    overrides = {}
    for k in DEFAULT_PARAMS:
        v = getattr(args, k, None)
        if v is not None:
            overrides[k] = v
    params = merge_params(overrides)

    sim = SumoSimulation()
    bot_ai = BotAI(params)
    if args.smart:
        enemy_ai = SmartEnemyAI(pwm_scale=params['pwmScale'])
    else:
        enemy_ai = EnemyAI(pwm_scale=params['pwmScale'])

    t0 = time.time()
    results = []
    bot_wins = ene_wins = draws = timeouts = 0
    total_dur = bot_win_dur = ene_win_dur = 0.0
    state_counts = {}

    for i in range(args.rounds):
        r = run_round(sim, bot_ai, enemy_ai, args.maxTime, args.smart)
        results.append(r)
        total_dur += r['duration']

        if r['winner'] == 'bot':
            bot_wins += 1
            bot_win_dur += r['duration']
        elif r['winner'] == 'enemy':
            ene_wins += 1
            ene_win_dur += r['duration']
        else:
            draws += 1

        if r.get('timeout'):
            timeouts += 1

        sk = r.get('botState', 'UNKNOWN')
        state_counts[sk] = state_counts.get(sk, 0) + 1

    elapsed = round(time.time() - t0, 2)

    output = {
        'params': params,
        'rounds': args.rounds,
        'maxTime': args.maxTime,
        'elapsed': f'{elapsed}s',
        'engine': 'mujoco',
        'results': {
            'botWins': bot_wins,
            'eneWins': ene_wins,
            'draws': draws,
            'timeouts': timeouts,
            'winRate': round(bot_wins / args.rounds, 4),
            'avgDuration': round(total_dur / args.rounds, 2),
            'botWinAvgDuration': round(bot_win_dur / bot_wins, 2) if bot_wins > 0 else None,
            'eneWinAvgDuration': round(ene_win_dur / ene_wins, 2) if ene_wins > 0 else None,
        },
        'botEndStates': state_counts,
    }

    if args.smart:
        loss_tactics = {}
        win_tactics = {}
        for r in results:
            if r['winner'] == 'enemy' and r.get('eneTactic'):
                loss_tactics[r['eneTactic']] = loss_tactics.get(r['eneTactic'], 0) + 1
            if r['winner'] == 'bot' and r.get('eneTactic'):
                win_tactics[r['eneTactic']] = win_tactics.get(r['eneTactic'], 0) + 1
        output['smartEnemy'] = {'lossTactics': loss_tactics, 'winTactics': win_tactics}

    if args.verbose:
        output['roundDetails'] = results

    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    run_batch(parse_args())
