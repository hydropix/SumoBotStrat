"""Bot AI — exact port of botAI() from headless.js (lines 250-367).

MANDATORY: Uses ONLY sensor data. No simulation internals.
State machine: SEARCH -> TRACK -> CHARGE -> EVADE -> CENTER -> FLANK
"""

import random as rng
from sensors.laser_sensor import LASER_RANGE

RANGE_MAX_MM = LASER_RANGE * 1000 * 0.95  # 760mm


class BotAI:
    def __init__(self, params: dict):
        self.S = params
        self.reset()

    def reset(self):
        self.state = 'SEARCH'
        self.ev_timer = 0.0
        self.ev_dir = 0
        self.ev_mode = 'front'
        self.cr_timer = 0.0
        self.flank_dir = 0
        self.flank_timer = 0.0

    def update(self, sensors: dict, dt: float) -> tuple[float, float]:
        """
        Main AI update. Returns (cmd_left, cmd_right) as PWM -255..255.

        sensors keys:
            d0, d1, d2: laser distances in meters
            line_fl, line_fr, line_r: booleans
            imu_ax, imu_ay, imu_gz: floats (currently unused — IMU dormant)
        """
        S = self.S
        max_pwm = 255 * S['pwmScale']

        # Convert laser distances to mm (matching JS convention)
        d0mm = sensors['d0'] * 1000
        d1mm = sensors['d1'] * 1000
        d2mm = sensors['d2'] * 1000

        det0 = d0mm < RANGE_MAX_MM
        det1 = d1mm < RANGE_MAX_MM
        det2 = d2mm < RANGE_MAX_MM
        any_laser = det0 or det1 or det2

        # Effective side distances (center fills gap)
        eff1 = d1mm if det1 else (d0mm + S['centerFill'] if det0 else RANGE_MAX_MM)
        eff2 = d2mm if det2 else (d0mm + S['centerFill'] if det0 else RANGE_MAX_MM)

        lr = [sensors['line_fl'], sensors['line_fr'], sensors['line_r']]

        # === EVADE ===
        if self.ev_timer > 0:
            self.ev_timer -= dt
            if self.ev_mode == 'rear':
                cmd_l = max_pwm * S['evadePwm']
                cmd_r = max_pwm * S['evadePwm']
            else:
                rev_t = S['evadeFrontTime'] * S['evadeReverseRatio']
                if self.ev_timer > S['evadeFrontTime'] - rev_t:
                    cmd_l = -max_pwm * S['evadePwm']
                    cmd_r = -max_pwm * S['evadePwm']
                else:
                    cmd_l = self.ev_dir * max_pwm * 0.8
                    cmd_r = -self.ev_dir * max_pwm * 0.8
            self.state = 'EVADE'
            return _clamp_pwm(cmd_l, cmd_r, max_pwm)

        # === CENTER RETURN ===
        if self.cr_timer > 0:
            self.cr_timer -= dt
            no_line = not lr[0] and not lr[1] and not lr[2]
            no_det = not det0 and not det1 and not det2
            if no_line and no_det:
                cmd_l = max_pwm * 0.7
                cmd_r = max_pwm * 0.7
                self.state = 'CENTER'
                return _clamp_pwm(cmd_l, cmd_r, max_pwm)
            self.cr_timer = 0  # abort: line or enemy detected

        # === LINE DETECTION ===
        if lr[0] or lr[1] or lr[2]:
            fwd_det = det0 or det1 or det2
            engaging = fwd_det and (self.state == 'CHARGE' or self.state == 'TRACK')
            single_front = (lr[0] or lr[1]) and not (lr[0] and lr[1]) and not lr[2]

            if engaging and single_front:
                # Edge-charge: continue pushing with steering correction
                min_d = min(d0mm if det0 else 9999, d1mm if det1 else 9999, d2mm if det2 else 9999)
                err = eff1 - eff2
                cor = S['kp'] * err
                base = max_pwm * S['chargePwm'] if min_d < S['chargeThreshold'] else max_pwm * S['trackPwm']
                edge_steer = max_pwm * S['edgeSteer'] if lr[0] else -max_pwm * S['edgeSteer']
                cmd_l = _clamp(base + cor + edge_steer, -max_pwm, max_pwm)
                cmd_r = _clamp(base - cor - edge_steer, -max_pwm, max_pwm)
                self.state = 'CHARGE'
                return cmd_l, cmd_r

            # Full evade
            if lr[2] and not lr[0] and not lr[1]:
                self.ev_timer = S['evadeRearTime']
                self.ev_mode = 'rear'
            else:
                self.ev_timer = S['evadeFrontTime']
                self.ev_mode = 'front'
                if lr[0] and not lr[1]:
                    self.ev_dir = 1
                elif lr[1] and not lr[0]:
                    self.ev_dir = -1
                else:
                    self.ev_dir = 1 if rng.random() < 0.5 else -1
            self.cr_timer = S['centerReturnTime']
            self.state = 'EVADE'
            return _clamp_pwm(0, 0, max_pwm)

        # === SEARCH / TRACK / CHARGE / FLANK ===
        any_det = det0 or det1 or det2
        if not any_det:
            # SEARCH: spin in place
            self.state = 'SEARCH'
            self.flank_timer = 0
            cmd_l = S['searchDir'] * max_pwm * S['searchPwm']
            cmd_r = -S['searchDir'] * max_pwm * S['searchPwm']
            return _clamp_pwm(cmd_l, cmd_r, max_pwm)

        min_d = min(d0mm if det0 else 9999, d1mm if det1 else 9999, d2mm if det2 else 9999)
        err = eff1 - eff2
        cor = S['kp'] * err

        # FLANKING
        should_flank = S['flankEnabled'] and min_d > S['flankThreshold']
        if should_flank:
            self.state = 'FLANK'
            self.flank_timer += dt
            if self.flank_timer < dt * 2:
                if det1 and not det2:
                    self.flank_dir = -1
                elif det2 and not det1:
                    self.flank_dir = 1
                else:
                    self.flank_dir = 1 if rng.random() < 0.5 else -1
            arc_offset = self.flank_dir * S['flankAngle']
            arc_cor = S['kp'] * err + arc_offset * 150
            base = max_pwm * S['flankPwm']
            cmd_l = _clamp(base + arc_cor, -max_pwm, max_pwm)
            cmd_r = _clamp(base - arc_cor, -max_pwm, max_pwm)
            return cmd_l, cmd_r

        # TRACK / CHARGE
        self.flank_timer = 0
        if min_d < S['chargeThreshold']:
            self.state = 'CHARGE'
            base = max_pwm * S['chargePwm']
        else:
            self.state = 'TRACK'
            base = max_pwm * S['trackPwm']
        cmd_l = _clamp(base + cor, -max_pwm, max_pwm)
        cmd_r = _clamp(base - cor, -max_pwm, max_pwm)
        return cmd_l, cmd_r


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _clamp_pwm(l, r, m):
    return _clamp(l, -m, m), _clamp(r, -m, m)
