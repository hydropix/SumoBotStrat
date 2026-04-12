"""Enemy AI — port of eneAI + smartEneAI from headless.js.

The enemy AI is omniscient (reads simulation state) — this is intentional.
It's a test tool, not the product. Only the BOT AI is sensor-only.
"""

import random as rng
from math import cos, sin, atan2, hypot, pi, sqrt
from sensors.laser_sensor import LASER_RANGE

TAU = 2.0 * pi

ARENA_RADIUS = 0.385
ARENA_BORDER = 0.022


class EnemyAI:
    """Multi-behavior enemy (WANDER, ORBIT, AGGRESSIVE, DODGE, ZIGZAG)."""

    def __init__(self, pwm_scale: float = 1.0):
        self.pwm_scale = pwm_scale
        self.reset()

    def reset(self):
        self.state = 'SEARCH'
        self.ev_timer = 0.0
        self.ev_dir = 0
        self.ev_mode = 'front'
        self.behav = 'ORBIT'
        self.behav_timer = 2.0 + rng.random() * 2.0
        self.wander_angle = rng.random() * TAU
        self.orbit_dir = 1 if rng.random() < 0.5 else -1
        self.match_time = 0.0

    def update(self, ene_sensors: dict, ene_pose: dict, bot_pose: dict,
               dt: float) -> tuple[float, float]:
        """
        Args:
            ene_sensors: line sensor data for the enemy
            ene_pose: {x, y, angle, vx, vy} of enemy
            bot_pose: {x, y, angle, vx, vy} of bot
            dt: time delta
        Returns: (cmd_left, cmd_right) PWM -255..255
        """
        max_pwm = 255 * self.pwm_scale * 0.85
        lr = [ene_sensors['line_fl'], ene_sensors['line_fr'], ene_sensors['line_r']]
        self.match_time += dt

        # === EVADE ===
        if self.ev_timer > 0:
            self.ev_timer -= dt
            if self.ev_mode == 'rear':
                cmd_l, cmd_r = max_pwm * 0.7, max_pwm * 0.7
            elif self.ev_timer > 0.15:
                cmd_l, cmd_r = -max_pwm * 0.6, -max_pwm * 0.6
            else:
                cmd_l = self.ev_dir * max_pwm * 0.7
                cmd_r = -self.ev_dir * max_pwm * 0.7
            self.state = 'EVADE'
            return _clamp2(cmd_l, cmd_r)

        # === LINE ===
        if lr[0] or lr[1] or lr[2]:
            if lr[2] and not lr[0] and not lr[1]:
                self.ev_timer = 0.25
                self.ev_mode = 'rear'
            else:
                self.ev_timer = 0.35
                self.ev_mode = 'front'
                if lr[0] and not lr[1]:
                    self.ev_dir = 1
                elif lr[1] and not lr[0]:
                    self.ev_dir = -1
                else:
                    self.ev_dir = 1 if rng.random() < 0.5 else -1
            self.state = 'EVADE'
            return _clamp2(0, 0)

        # === BEHAVIOR ===
        self.behav_timer -= dt
        if self.behav_timer <= 0:
            self._pick_behavior()
        self.wander_angle += (rng.random() - 0.5) * 3 * dt

        ex, ey, ea = ene_pose['x'], ene_pose['y'], ene_pose['angle']
        bx, by = bot_pose['x'], bot_pose['y']

        to_player = atan2(by - ey, bx - ex)
        to_center = atan2(-ey, -ex)
        d_center = hypot(ex, ey)
        d_player = hypot(bx - ex, by - ey)

        inner_r = ARENA_RADIUS - ARENA_BORDER
        edge = max(0, (d_center - inner_r * 0.7) / (inner_r * 0.3))

        if self.behav == 'WANDER':
            self.state = 'WANDER'
            steer, fwd = self.wander_angle, max_pwm * 0.55
        elif self.behav == 'ORBIT':
            self.state = 'ORBIT'
            steer = to_center + self.orbit_dir * pi / 2
            fwd = max_pwm * 0.6
        elif self.behav == 'AGGRESSIVE':
            if d_player < 0.15:
                self.state = 'CHARGE'
                steer, fwd = to_player, max_pwm
            else:
                self.state = 'TRACK'
                steer, fwd = to_player, max_pwm * 0.7
        elif self.behav == 'DODGE':
            self.state = 'DODGE'
            steer = to_player + self.orbit_dir * pi / 2
            fwd = max_pwm * 0.65
        else:  # ZIGZAG
            self.state = 'ZIGZAG'
            steer = to_player + sin(self.match_time * 4) * 0.8
            fwd = max_pwm * 0.6

        if edge > 0:
            steer = steer * (1 - edge) + to_center * edge

        cor = ang_diff(ea, steer) * 150
        cmd_l = clamp(fwd + cor, -255, 255)
        cmd_r = clamp(fwd - cor, -255, 255)
        return cmd_l, cmd_r

    def _pick_behavior(self):
        choices = ['WANDER', 'ORBIT', 'AGGRESSIVE', 'DODGE', 'ZIGZAG']
        self.behav = choices[rng.randint(0, len(choices) - 1)]
        self.behav_timer = 1.5 + rng.random() * 3
        self.wander_angle = rng.random() * TAU
        self.orbit_dir = 1 if rng.random() < 0.5 else -1


class SmartEnemyAI:
    """Omniscient smart enemy with 8 tactics + weighted scoring."""

    def __init__(self, pwm_scale: float = 1.0, laser_angle: float = 0.526):
        self.pwm_scale = pwm_scale
        self.laser_angle = laser_angle
        self.reset()

    def reset(self):
        self.state = 'SEARCH'
        self.ev_timer = 0.0
        self.tactic = 'FLANK'
        self.tactic_timer = 0.0
        self.side = 1 if rng.random() < 0.5 else -1
        self.juke_t = 0.0
        self.hesitate = 0.0
        self.bot_ai_state = 'SEARCH'  # last known bot AI state

    def update(self, ene_sensors: dict, ene_pose: dict, bot_pose: dict,
               dt: float, bot_ai_state: str = 'SEARCH') -> tuple[float, float]:
        """
        Args:
            ene_sensors: enemy line sensor data
            ene_pose: {x, y, z, angle, vx, vy, omega_z}
            bot_pose: {x, y, z, angle, vx, vy, omega_z}
            dt: time delta
            bot_ai_state: current bot AI state string (omniscient read)
        Returns: (cmd_left, cmd_right) PWM -255..255
        """
        mp = 255.0
        self.bot_ai_state = bot_ai_state
        lr = [ene_sensors['line_fl'], ene_sensors['line_fr'], ene_sensors['line_r']]

        ex, ey, ea = ene_pose['x'], ene_pose['y'], ene_pose['angle']
        bx, by, ba = bot_pose['x'], bot_pose['y'], bot_pose['angle']
        bvx, bvy = bot_pose['vx'], bot_pose['vy']

        # === Reactive evade ===
        if self.ev_timer > 0:
            self.ev_timer -= dt
            tgt = atan2(-ey, -ex)
            self.state = 'EVADE'
            return _steer_to(ea, tgt, mp * 0.85, mp)

        if lr[0] or lr[1] or lr[2]:
            d = hypot(bx - ex, by - ey)
            sf = (lr[0] or lr[1]) and not (lr[0] and lr[1]) and not lr[2]
            if d < 0.14 and sf:
                tb = atan2(by - ey, bx - ex)
                offset = 0.25 if lr[0] else -0.25
                self.state = 'EDGE_PUSH'
                return _steer_to(ea, tb + offset, mp, mp)
            self.ev_timer = 0.2
            self.state = 'EVADE'
            return _steer_to(ea, atan2(-ey, -ex), mp * 0.85, mp)

        # === Omniscient analysis ===
        dx, dy = bx - ex, by - ey
        dist = hypot(dx, dy)
        to_bot = atan2(dy, dx)
        in_cone = (abs(ang_diff(ba, atan2(-dy, -dx))) < (self.laser_angle + 0.18)
                   and dist < LASER_RANGE)
        my_r = hypot(ex, ey)
        bot_r = hypot(bx, by)
        bot_spd = hypot(bvx, bvy)
        closing = (bvx * dx + bvy * dy) / (dist + 1e-6)
        px = bx + bvx * 0.25
        py = by + bvy * 0.25
        to_pred = atan2(py - ey, px - ex)

        # === Kill zone ===
        bot_edge = ARENA_RADIUS - bot_r
        if bot_edge < 0.07 and my_r < bot_r - 0.04 and dist < 0.35:
            self.state = 'KILL'
            return _steer_to(ea, to_pred, mp, mp)

        # === Tactic selection ===
        self.tactic_timer -= dt
        if self.tactic_timer <= 0:
            self.tactic_timer = 1.0 + rng.random() * 1.5
            self.side = 1 if rng.random() < 0.5 else -1
            self.juke_t = 0.0
            if rng.random() < 0.12:
                self.hesitate = 0.08 + rng.random() * 0.14

            if bot_ai_state == 'EVADE':
                self.tactic = 'EXPLOIT_EVADE'
            elif closing > 0.15 and dist < 0.22 and (ARENA_RADIUS - bot_r) > 0.06:
                self.tactic = 'MATADOR'
            else:
                sc = {
                    'FLANK':     30 + (25 if (in_cone and dist > 0.15) else 0) + (10 if bot_ai_state == 'TRACK' else 0),
                    'RUSH':      20 + (40 if not in_cone else 0) + (15 if bot_spd < 0.05 else 0) + (25 if bot_edge < 0.1 else 0),
                    'SHADOW':    20 + (40 if bot_ai_state == 'SEARCH' else 0),
                    'EDGE_TRAP': 20 + (35 if my_r < bot_r - 0.03 else 0) + (25 if bot_edge < 0.1 else 0),
                    'BULL':      10 + (15 if dist < 0.15 else 0) + (20 if bot_ai_state == 'SEARCH' else 0),
                    'JUKE':       5 + (15 if dist < 0.2 else 0),
                    'MATADOR':    5 + (15 if closing > 0.08 else 0),
                }
                for k in sc:
                    sc[k] *= (0.7 + rng.random() * 0.6)
                self.tactic = max(sc, key=sc.get)

        # === Hesitation ===
        if self.hesitate > 0:
            self.hesitate -= dt
            self.state = 'THINK'
            return 0.0, 0.0

        # === Execute tactic ===
        t_angle, t_speed = to_bot, mp * 0.7  # default

        if self.tactic == 'FLANK':
            fa = ba + self.side * pi * 0.65
            fx = bx + cos(fa) * 0.18
            fy = by + sin(fa) * 0.18
            fr = hypot(fx, fy)
            if fr > ARENA_RADIUS - 0.05:
                k = (ARENA_RADIUS - 0.05) / fr
                fx *= k
                fy *= k
            tf = atan2(fy - ey, fx - ex)
            df = hypot(fx - ex, fy - ey)
            if df > 0.07 and in_cone:
                t_angle, t_speed = tf, mp * 0.8
            elif dist < 0.30:
                t_angle, t_speed = to_pred, mp
            else:
                t_angle, t_speed = tf, mp * 0.75
            self.state = 'FLANK'

        elif self.tactic == 'MATADOR':
            if dist > 0.12 or closing < 0.06:
                t_angle, t_speed = to_bot, mp * 0.12
                self.state = 'BAIT'
            else:
                da = to_bot + self.side * pi * 0.45
                if hypot(ex + cos(da) * 0.15, ey + sin(da) * 0.15) > ARENA_RADIUS - 0.05:
                    da = to_bot - self.side * pi * 0.45
                t_angle, t_speed = da, mp
                self.state = 'DODGE'

        elif self.tactic == 'RUSH':
            t_angle, t_speed = to_pred, mp
            self.state = 'RUSH'

        elif self.tactic == 'SHADOW':
            bh = ba + pi
            sh_x = bx + cos(bh) * 0.13
            sh_y = by + sin(bh) * 0.13
            to_sh = atan2(sh_y - ey, sh_x - ex)
            d_sh = hypot(sh_x - ex, sh_y - ey)
            if d_sh < 0.08:
                t_angle, t_speed = to_bot, mp
                self.state = 'BACKSTAB'
            else:
                t_angle, t_speed = to_sh, mp * 0.75
                self.state = 'SHADOW'

        elif self.tactic == 'EDGE_TRAP':
            bc = atan2(-by, -bx)
            tr_x = bx + cos(bc) * 0.13
            tr_y = by + sin(bc) * 0.13
            to_tr = atan2(tr_y - ey, tr_x - ex)
            d_tr = hypot(tr_x - ex, tr_y - ey)
            if d_tr > 0.06:
                t_angle, t_speed = to_tr, mp * 0.75
                self.state = 'TRAP_POS'
            else:
                t_angle, t_speed = to_bot, mp * 0.9
                self.state = 'TRAP_PUSH'

        elif self.tactic == 'JUKE':
            self.juke_t += dt
            jd = 1 if int(self.juke_t / 0.15) % 2 == 0 else -1
            if self.juke_t < 0.3:
                t_angle = to_bot + jd * 0.65
                t_speed = mp * 0.85
                self.state = 'JUKE'
            else:
                t_angle, t_speed = to_pred, mp
                self.state = 'JUKE_CHG'

        elif self.tactic == 'BULL':
            if dist < 0.25 or in_cone:
                blind_ang = ba + self.side * pi * 0.7
                bx2 = bx + cos(blind_ang) * 0.28
                by2 = by + sin(blind_ang) * 0.28
                br = hypot(bx2, by2)
                if br > ARENA_RADIUS - 0.05:
                    k = (ARENA_RADIUS - 0.05) / br
                    bx2 *= k
                    by2 *= k
                t_angle = atan2(by2 - ey, bx2 - ex)
                t_speed = mp * 0.85
                self.state = 'BULL_BACK'
            else:
                t_angle, t_speed = to_pred, mp
                self.state = 'BULL_CHG'

        elif self.tactic == 'EXPLOIT_EVADE':
            t_angle, t_speed = to_pred, mp
            self.state = 'EXPLOIT'

        # === Proactive edge blend ===
        safe_r = ARENA_RADIUS - 0.04
        if my_r > safe_r:
            u = clamp((my_r - safe_r) / 0.03, 0, 1)
            t_angle += ang_diff(t_angle, atan2(-ey, -ex)) * u

        # === Human imprecision ===
        t_angle += (rng.random() - 0.5) * 0.2
        t_speed *= (0.82 + rng.random() * 0.18)

        return _steer_to(ea, t_angle, t_speed, mp)


def ang_diff(a, b):
    return ((b - a) % TAU + 3 * pi) % TAU - pi


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _steer_to(current_angle: float, target_angle: float,
              speed: float, max_pwm: float) -> tuple[float, float]:
    cor = clamp(ang_diff(current_angle, target_angle) * 250, -max_pwm, max_pwm)
    cmd_l = clamp(speed + cor, -max_pwm, max_pwm)
    cmd_r = clamp(speed - cor, -max_pwm, max_pwm)
    return cmd_l, cmd_r


def _clamp2(l, r):
    return max(-255, min(255, l)), max(-255, min(255, r))
