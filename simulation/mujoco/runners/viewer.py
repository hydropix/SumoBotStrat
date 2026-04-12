"""Interactive MuJoCo viewer for SumoBot simulation.

Usage:
    python -m runners.viewer
    python -m runners.viewer --smart
"""

import argparse
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mujoco
import mujoco.viewer

from physics.sim_engine import SumoSimulation
from ai.bot_ai import BotAI
from ai.enemy_ai import EnemyAI, SmartEnemyAI
from ai.strategy_params import DEFAULT_PARAMS
from utils.spawn import random_spawn


def parse_args():
    p = argparse.ArgumentParser(description='SumoBot MuJoCo Viewer')
    p.add_argument('--smart', action='store_true', help='Use smart enemy')
    p.add_argument('--maxTime', type=float, default=20.0)
    p.add_argument('--speed', type=float, default=1.0, help='Simulation speed multiplier')
    return p.parse_args()


def run_viewer(args):
    sim = SumoSimulation()
    bot_ai = BotAI(DEFAULT_PARAMS)
    smart = args.smart
    if smart:
        enemy_ai = SmartEnemyAI()
    else:
        enemy_ai = EnemyAI()

    # Initial spawn
    spawn = random_spawn()
    sim.reset(spawn['bot_pos'], spawn['bot_angle'],
              spawn['ene_pos'], spawn['ene_angle'])
    bot_ai.reset()
    enemy_ai.reset()

    ai_dt = 1.0 / 60
    ai_accum = 0.0
    physics_dt = sim.model.opt.timestep

    bot_pwm_l, bot_pwm_r = 0.0, 0.0
    ene_pwm_l, ene_pwm_r = 0.0, 0.0
    round_num = 0

    def reset_round():
        nonlocal bot_pwm_l, bot_pwm_r, ene_pwm_l, ene_pwm_r, ai_accum, round_num
        spawn = random_spawn()
        sim.reset(spawn['bot_pos'], spawn['bot_angle'],
                  spawn['ene_pos'], spawn['ene_angle'])
        bot_ai.reset()
        enemy_ai.reset()
        bot_pwm_l = bot_pwm_r = ene_pwm_l = ene_pwm_r = 0.0
        ai_accum = 0.0
        round_num += 1
        print(f"\n--- Round {round_num} ---")

    round_num = 1
    print(f"--- Round {round_num} ---")
    print("Close the viewer window to exit.")
    print(f"Enemy type: {'SMART' if smart else 'BASIC'}")

    with mujoco.viewer.launch_passive(sim.model, sim.data) as viewer:
        # Set camera to top-down view
        viewer.cam.lookat[:] = [0, 0, 0.05]
        viewer.cam.distance = 1.0
        viewer.cam.elevation = -60
        viewer.cam.azimuth = 90

        while viewer.is_running():
            step_start = time.time()

            # AI update
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

            # Physics step
            sim.step(bot_pwm_l, bot_pwm_r, ene_pwm_l, ene_pwm_r)

            # Check round end
            b_out = sim.is_out('bot')
            e_out = sim.is_out('enemy')
            timeout = sim.time >= args.maxTime

            if b_out or e_out or timeout:
                if b_out and e_out:
                    winner = 'DRAW'
                elif e_out:
                    winner = 'BOT WINS'
                elif b_out:
                    winner = 'ENEMY WINS'
                else:
                    from math import hypot
                    bp = sim.get_bot_pose()
                    ep = sim.get_ene_pose()
                    bd = hypot(bp['x'], bp['y'])
                    ed = hypot(ep['x'], ep['y'])
                    winner = 'BOT WINS (timeout)' if bd < ed else 'ENEMY WINS (timeout)'

                print(f"  {winner} | t={sim.time:.2f}s | bot={bot_ai.state} ene={enemy_ai.state}")
                time.sleep(0.5)
                reset_round()

            viewer.sync()

            # Real-time pacing
            elapsed = time.time() - step_start
            target = physics_dt / args.speed
            if elapsed < target:
                time.sleep(target - elapsed)


if __name__ == '__main__':
    run_viewer(parse_args())
