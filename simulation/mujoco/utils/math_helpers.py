"""Math helpers — ports of the JS utility functions."""

import numpy as np
from math import cos, sin, atan2, hypot, pi, sqrt

TAU = 2.0 * pi


def ang_diff(a: float, b: float) -> float:
    """Signed angular difference from a to b, in [-pi, pi]."""
    return ((b - a) % TAU + 3 * pi) % TAU - pi


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def local_to_world(x: float, y: float, angle: float,
                   lx: float, ly: float) -> tuple[float, float]:
    """Transform local (lx, ly) to world coords given body pose (x, y, angle)."""
    c, s = cos(angle), sin(angle)
    return x + lx * c - ly * s, y + lx * s + ly * c


def quat_to_yaw(quat: np.ndarray) -> float:
    """Extract yaw angle from a MuJoCo quaternion [w, x, y, z]."""
    w, x, y, z = quat
    return atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def yaw_to_quat(yaw: float) -> np.ndarray:
    """Convert yaw angle to MuJoCo quaternion [w, x, y, z] (Z-up rotation)."""
    return np.array([cos(yaw / 2), 0.0, 0.0, sin(yaw / 2)])
