"""N20 motor model — linear torque-speed curve.

Matches the JS motorForce() function from headless.js exactly,
but operates in angular domain (torque, omega) instead of linear (force, speed).
"""

import numpy as np

# N20 12V motor at 7.5V nominal
STALL_TORQUE = 0.0245       # Nm
NO_LOAD_OMEGA = 32.7        # rad/s (312 RPM)
WHEEL_RADIUS = 0.015        # m

# Derived constants (for reference / validation)
NO_LOAD_SPEED = NO_LOAD_OMEGA * WHEEL_RADIUS   # 0.4905 m/s
STALL_FORCE = STALL_TORQUE / WHEEL_RADIUS       # 1.633 N


def compute_motor_torque(pwm: float, wheel_omega: float,
                         stall_torque: float = STALL_TORQUE,
                         no_load_omega: float = NO_LOAD_OMEGA) -> float:
    """
    Compute motor torque from PWM command and current wheel angular velocity.

    Args:
        pwm: Motor command, -255 to 255
        wheel_omega: Current wheel angular velocity in rad/s
        stall_torque: Motor stall torque in Nm
        no_load_omega: Motor no-load angular velocity in rad/s

    Returns:
        Torque in Nm to apply to wheel joint
    """
    target_omega = (pwm / 255.0) * no_load_omega
    torque = stall_torque * (target_omega - wheel_omega) / no_load_omega
    return np.clip(torque, -stall_torque * 2, stall_torque * 2)
