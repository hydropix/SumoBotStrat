"""Random spawn logic — matches the JS headless.js runRound() function."""

import numpy as np
from math import cos, sin, pi

TAU = 2.0 * pi


def random_spawn() -> dict:
    """
    Generate random starting positions for bot and enemy.
    Returns dict with bot_pos, bot_angle, ene_pos, ene_angle.
    Matches JS: bAng random, eAng offset by pi*(0.6..1.4), radii 0.08..0.14.
    """
    b_ang = np.random.uniform(0, TAU)
    e_ang = b_ang + pi * (0.6 + np.random.uniform() * 0.8)
    b_r = 0.08 + np.random.uniform() * 0.06
    e_r = 0.08 + np.random.uniform() * 0.06
    b_face = b_ang + pi + (np.random.uniform() - 0.5) * 1.2
    e_face = e_ang + pi + (np.random.uniform() - 0.5) * 1.2

    return {
        'bot_pos': (cos(b_ang) * b_r, sin(b_ang) * b_r),
        'bot_angle': b_face,
        'ene_pos': (cos(e_ang) * e_r, sin(e_ang) * e_r),
        'ene_angle': e_face,
    }
