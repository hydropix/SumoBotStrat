"""Monte Carlo parameter optimization — port of montecarlo_v3.js.

Usage:
    python -m runners.montecarlo --configs 40 --rounds 200 --smart
    python -m runners.montecarlo --configs 80 --rounds 200 --topN 8 --revalRounds 800
"""

import argparse
import json
import time
import sys
import os
import random
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from physics.sim_engine import SumoSimulation
from ai.bot_ai import BotAI
from ai.enemy_ai import EnemyAI, SmartEnemyAI
from ai.strategy_params import DEFAULT_PARAMS, merge_params
from utils.spawn import random_spawn


# Parameter ranges for random search
PARAM_RANGES = {
    'kp':              (0.2, 1.5),
    'searchPwm':       (0.5, 1.0),
    'trackPwm':        (0.7, 1.0),
    'chargePwm':       (0.7, 1.0),
    'chargeThreshold': (150, 600),
    'evadeFrontTime':  (0.2, 0.8),
    'evadeRearTime':   (0.15, 0.5),
    'evadeReverseRatio': (0.2, 0.7),
    'evadePwm':        (0.7, 1.0),
    'edgeSteer':       (0.1, 0.8),
    'centerReturnTime': (0.1, 0.6),
    'centerFill':      (50, 300),
    'flankAngle':      (0.2, 1.0),
    'flankThreshold':  (300, 800),
    'flankPwm':        (0.4, 0.9),
}


def parse_args():
    p = argparse.ArgumentParser(description='SumoBot Monte Carlo Optimizer')
    p.add_argument('--configs', type=int, default=40, help='Number of random configs')
    p.add_argument('--rounds', type=int, default=200, help='Rounds per config')
    p.add_argument('--topN', type=int, default=8, help='Top configs to revalidate')
    p.add_argument('--revalRounds', type=int, default=800, help='Rounds for revalidation')
    p.add_argument('--maxTime', type=float, default=20.0)
    p.add_argument('--smart', action='store_true')
    p.add_argument('--output', type=str, default=None, help='Output JSON file')
    return p.parse_args()


def random_config() -> dict:
    """Generate a random parameter configuration."""
    params = DEFAULT_PARAMS.copy()
    for k, (lo, hi) in PARAM_RANGES.items():
        if isinstance(params[k], int):
            params[k] = random.randint(int(lo), int(hi))
        else:
            params[k] = lo + random.random() * (hi - lo)
    return params


def evaluate(params: dict, sim: SumoSimulation, rounds: int,
             max_time: float, smart: bool) -> dict:
    """Evaluate a parameter config over N rounds."""
    bot_ai = BotAI(params)
    if smart:
        enemy_ai = SmartEnemyAI(pwm_scale=params['pwmScale'])
    else:
        enemy_ai = EnemyAI(pwm_scale=params['pwmScale'])

    bot_wins = 0
    timeouts = 0
    total_dur = 0.0

    ai_dt = 1.0 / 60
    physics_dt = sim.model.opt.timestep

    for _ in range(rounds):
        spawn = random_spawn()
        sim.reset(spawn['bot_pos'], spawn['bot_angle'],
                  spawn['ene_pos'], spawn['ene_angle'])
        bot_ai.reset()
        enemy_ai.reset()

        ai_accum = 0.0
        bot_pwm_l = bot_pwm_r = 0.0
        ene_pwm_l = ene_pwm_r = 0.0
        done = False

        while sim.time < max_time and not done:
            ai_accum += physics_dt
            if ai_accum >= ai_dt:
                bot_sensors = sim.get_bot_sensors()
                bot_pwm_l, bot_pwm_r = bot_ai.update(bot_sensors, ai_accum)

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
                if e_out and not b_out:
                    bot_wins += 1
                total_dur += sim.time
                done = True

        if not done:
            # Timeout
            timeouts += 1
            total_dur += max_time
            from math import hypot
            bp = sim.get_bot_pose()
            ep = sim.get_ene_pose()
            if hypot(bp['x'], bp['y']) < hypot(ep['x'], ep['y']):
                bot_wins += 1

    return {
        'winRate': bot_wins / rounds,
        'timeoutRate': timeouts / rounds,
        'avgDuration': total_dur / rounds,
        'botWins': bot_wins,
    }


def run_optimization(args):
    t0 = time.time()
    sim = SumoSimulation()

    print(f"Monte Carlo optimization: {args.configs} configs x {args.rounds} rounds")
    print(f"Enemy: {'SMART' if args.smart else 'BASIC'}")
    print()

    # Phase 1: Random search
    configs = []
    for i in range(args.configs):
        params = random_config()
        result = evaluate(params, sim, args.rounds, args.maxTime, args.smart)
        configs.append({'params': params, **result})
        wr = result['winRate'] * 100
        print(f"  Config {i+1}/{args.configs}: WR={wr:.1f}% "
              f"(timeouts={result['timeoutRate']*100:.0f}%)")

    # Sort by win rate
    configs.sort(key=lambda c: c['winRate'], reverse=True)

    # Phase 2: Revalidate top N
    print(f"\nRevalidating top {args.topN} with {args.revalRounds} rounds each:")
    top_configs = configs[:args.topN]
    for i, cfg in enumerate(top_configs):
        result = evaluate(cfg['params'], sim, args.revalRounds, args.maxTime, args.smart)
        cfg.update(result)
        cfg['revalidated'] = True
        wr = result['winRate'] * 100
        print(f"  #{i+1}: WR={wr:.1f}% (timeouts={result['timeoutRate']*100:.0f}%)")

    # Sort again by revalidated win rate
    top_configs.sort(key=lambda c: c['winRate'], reverse=True)

    elapsed = round(time.time() - t0, 1)
    best = top_configs[0]

    output = {
        'elapsed': f'{elapsed}s',
        'configs_tested': args.configs,
        'rounds_initial': args.rounds,
        'rounds_reval': args.revalRounds,
        'smart_enemy': args.smart,
        'best': {
            'winRate': best['winRate'],
            'params': best['params'],
        },
        'top_results': [{
            'rank': i + 1,
            'winRate': c['winRate'],
            'timeoutRate': c['timeoutRate'],
            'params': c['params'],
        } for i, c in enumerate(top_configs)],
    }

    print(f"\nBest: WR={best['winRate']*100:.1f}%")
    print(f"Elapsed: {elapsed}s")

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"Results saved to {args.output}")
    else:
        print(json.dumps(output, indent=2))


if __name__ == '__main__':
    run_optimization(parse_args())
