"""TCRT5000 line sensor simulation — detects white border of the dohyo."""

import mujoco
import numpy as np
from math import hypot

ARENA_RADIUS = 0.385
BORDER_WIDTH = 0.022
ARENA_TOP_Z = 0.05  # top surface of dohyo


def read_line_sensors(model: mujoco.MjModel, data: mujoco.MjData,
                      site_names: list[str],
                      arena_radius: float = ARENA_RADIUS,
                      border_width: float = BORDER_WIDTH) -> list[bool]:
    """
    Check if each line sensor is over the white border.

    A sensor detects the line when its XY distance from arena center
    exceeds (arena_radius - border_width). Also triggers if the sensor
    is below the arena surface (robot partially off edge).

    Args:
        model: MuJoCo model
        data: MuJoCo data
        site_names: List of site names [front_left, front_right, rear]

    Returns:
        List of booleans: True = on white border (or off arena)
    """
    results = []
    threshold = arena_radius - border_width

    for name in site_names:
        site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, name)
        pos = data.site_xpos[site_id]
        r = hypot(pos[0], pos[1])
        below_surface = pos[2] < ARENA_TOP_Z - 0.005
        results.append(r > threshold or below_surface)

    return results
