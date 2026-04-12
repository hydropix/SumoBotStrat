"""MPU6050 IMU simulation from MuJoCo built-in sensors."""

import mujoco
import numpy as np


def read_imu(model: mujoco.MjModel, data: mujoco.MjData,
             accel_name: str, gyro_name: str) -> dict:
    """
    Read accelerometer and gyroscope from MuJoCo sensors.

    MuJoCo accelerometer includes gravity. To match the JS simulation
    (which computes acceleration from velocity deltas, excluding gravity),
    we subtract gravity rotated into the sensor frame.

    Args:
        model: MuJoCo model
        data: MuJoCo data
        accel_name: Name of the accelerometer sensor
        gyro_name: Name of the gyro sensor

    Returns:
        dict with ax, ay, az (m/s^2, gravity-subtracted) and gx, gy, gz (rad/s)
    """
    # Get sensor addresses
    accel_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, accel_name)
    gyro_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, gyro_name)
    accel_adr = model.sensor_adr[accel_id]
    gyro_adr = model.sensor_adr[gyro_id]

    # Raw sensor data
    accel_raw = data.sensordata[accel_adr:accel_adr + 3].copy()
    gyro_raw = data.sensordata[gyro_adr:gyro_adr + 3].copy()

    # Get the site orientation to subtract gravity
    site_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_SITE,
                                   model.sensor_objid[accel_id])
    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, site_name)
    xmat = data.site_xmat[site_id].reshape(3, 3)

    # Gravity in world frame
    gravity_world = np.array([0, 0, -9.81])
    # Gravity in sensor frame (accelerometer measures reaction to gravity = -g)
    gravity_sensor = xmat.T @ gravity_world

    # Subtract gravity contribution (accelerometer reads: a_real + reaction_to_gravity)
    # MuJoCo accelerometer = linear_accel - gravity (in sensor frame)
    # So raw reading already excludes gravity for a body in free fall,
    # but includes it when on ground. We want pure kinematic acceleration.
    # Actually MuJoCo accelerometer = a_body - g (rotated to sensor frame)
    # So for a stationary body on ground: reads [0, 0, +9.81]
    # We want: ax, ay from dynamics only (no gravity)
    accel = accel_raw.copy()
    accel[2] -= 9.81  # Remove the gravity offset for Z when upright

    return {
        'ax': float(accel[0]),   # forward/backward
        'ay': float(accel[1]),   # lateral
        'az': float(accel[2]),   # vertical (0 when upright on ground)
        'gx': float(gyro_raw[0]),
        'gy': float(gyro_raw[1]),
        'gz': float(gyro_raw[2]),  # yaw rate — primary for sumo AI
    }
