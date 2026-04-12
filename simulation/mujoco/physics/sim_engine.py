"""Core MuJoCo simulation engine for SumoBot."""

import os
import mujoco
import numpy as np
from math import hypot, cos, sin, atan2

from sensors.laser_sensor import read_lasers, LASER_RANGE
from sensors.line_sensor import read_line_sensors
from sensors.imu_sensor import read_imu
from physics.motor_model import compute_motor_torque, STALL_TORQUE, NO_LOAD_OMEGA

MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
ARENA_RADIUS = 0.385
ARENA_TOP_Z = 0.05


class SumoSimulation:
    """MuJoCo-based sumo robot simulation."""

    def __init__(self, scene_xml: str = None):
        if scene_xml is None:
            scene_xml = os.path.join(MODELS_DIR, 'scene.xml')
        self.model = mujoco.MjModel.from_xml_path(scene_xml)
        self.data = mujoco.MjData(self.model)

        # Cache body/joint/actuator/site IDs
        self._bot_body = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, 'bot_chassis')
        self._ene_body = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, 'ene_chassis')

        self._bot_joint = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, 'bot_root')
        self._ene_joint = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, 'ene_root')

        self._bot_wl_joint = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, 'bot_wheel_L_joint')
        self._bot_wr_joint = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, 'bot_wheel_R_joint')
        self._ene_wl_joint = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, 'ene_wheel_L_joint')
        self._ene_wr_joint = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, 'ene_wheel_R_joint')

        # Actuator indices
        self._bot_motor_l = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, 'bot_motor_L')
        self._bot_motor_r = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, 'bot_motor_R')
        self._ene_motor_l = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, 'ene_motor_L')
        self._ene_motor_r = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, 'ene_motor_R')

        # Qpos addresses for freejoints (pos=3 + quat=4 = 7 each)
        self._bot_qpos_adr = self.model.jnt_qposadr[self._bot_joint]
        self._ene_qpos_adr = self.model.jnt_qposadr[self._ene_joint]
        self._bot_qvel_adr = self.model.jnt_dofadr[self._bot_joint]
        self._ene_qvel_adr = self.model.jnt_dofadr[self._ene_joint]

        # Wheel qvel addresses (1 DOF each)
        self._bot_wl_qvel = self.model.jnt_dofadr[self._bot_wl_joint]
        self._bot_wr_qvel = self.model.jnt_dofadr[self._bot_wr_joint]
        self._ene_wl_qvel = self.model.jnt_dofadr[self._ene_wl_joint]
        self._ene_wr_qvel = self.model.jnt_dofadr[self._ene_wr_joint]

        # Laser site names
        self._bot_laser_sites = ['bot_laser_center', 'bot_laser_left', 'bot_laser_right']
        self._ene_laser_sites = ['ene_laser_center', 'ene_laser_left', 'ene_laser_right']
        self._bot_line_sites = ['bot_line_fl', 'bot_line_fr', 'bot_line_r']
        self._ene_line_sites = ['ene_line_fl', 'ene_line_fr', 'ene_line_r']

    def reset(self, bot_pos: tuple, bot_angle: float,
              ene_pos: tuple, ene_angle: float):
        """Reset simulation with given spawn positions on the dohyo."""
        mujoco.mj_resetData(self.model, self.data)

        z = 0.065  # chassis height above ground

        # Bot position (x, y, z) + quaternion
        ba = self._bot_qpos_adr
        self.data.qpos[ba:ba + 3] = [bot_pos[0], bot_pos[1], z]
        self.data.qpos[ba + 3:ba + 7] = _yaw_quat(bot_angle)

        # Enemy position
        ea = self._ene_qpos_adr
        self.data.qpos[ea:ea + 3] = [ene_pos[0], ene_pos[1], z]
        self.data.qpos[ea + 3:ea + 7] = _yaw_quat(ene_angle)

        # Zero velocities
        self.data.qvel[:] = 0
        self.data.ctrl[:] = 0

        mujoco.mj_forward(self.model, self.data)

    def step(self, bot_pwm_l: float, bot_pwm_r: float,
             ene_pwm_l: float, ene_pwm_r: float):
        """Advance one physics timestep. PWM values in -255..255."""
        # Read current wheel angular velocities
        bot_wl_omega = self.data.qvel[self._bot_wl_qvel]
        bot_wr_omega = self.data.qvel[self._bot_wr_qvel]
        ene_wl_omega = self.data.qvel[self._ene_wl_qvel]
        ene_wr_omega = self.data.qvel[self._ene_wr_qvel]

        # Compute motor torques
        self.data.ctrl[self._bot_motor_l] = compute_motor_torque(bot_pwm_l, bot_wl_omega)
        self.data.ctrl[self._bot_motor_r] = compute_motor_torque(bot_pwm_r, bot_wr_omega)
        self.data.ctrl[self._ene_motor_l] = compute_motor_torque(ene_pwm_l, ene_wl_omega)
        self.data.ctrl[self._ene_motor_r] = compute_motor_torque(ene_pwm_r, ene_wr_omega)

        mujoco.mj_step(self.model, self.data)

    @property
    def time(self) -> float:
        return self.data.time

    def get_bot_sensors(self) -> dict:
        """Read all bot sensor data (sensor-only, no simulation internals)."""
        lasers = read_lasers(self.model, self.data,
                             self._bot_laser_sites, self._bot_body)
        lines = read_line_sensors(self.model, self.data, self._bot_line_sites)
        imu = read_imu(self.model, self.data, 'bot_accel', 'bot_gyro')

        return {
            'd0': lasers[0], 'd1': lasers[1], 'd2': lasers[2],
            'line_fl': lines[0], 'line_fr': lines[1], 'line_r': lines[2],
            'imu_ax': imu['ax'], 'imu_ay': imu['ay'],
            'imu_gz': imu['gz'],
        }

    def get_ene_sensors(self) -> dict:
        """Read enemy sensor data (for sensor-based enemy AI if needed)."""
        lasers = read_lasers(self.model, self.data,
                             self._ene_laser_sites, self._ene_body)
        lines = read_line_sensors(self.model, self.data, self._ene_line_sites)
        imu = read_imu(self.model, self.data, 'ene_accel', 'ene_gyro')

        return {
            'd0': lasers[0], 'd1': lasers[1], 'd2': lasers[2],
            'line_fl': lines[0], 'line_fr': lines[1], 'line_r': lines[2],
            'imu_ax': imu['ax'], 'imu_ay': imu['ay'],
            'imu_gz': imu['gz'],
        }

    def get_bot_pose(self) -> dict:
        """Get bot world pose (for enemy AI that needs omniscient data)."""
        ba = self._bot_qpos_adr
        pos = self.data.qpos[ba:ba + 3].copy()
        quat = self.data.qpos[ba + 3:ba + 7].copy()
        vel_adr = self._bot_qvel_adr
        vel = self.data.qvel[vel_adr:vel_adr + 3].copy()
        omega = self.data.qvel[vel_adr + 3:vel_adr + 6].copy()
        return {
            'x': float(pos[0]), 'y': float(pos[1]), 'z': float(pos[2]),
            'angle': float(_quat_to_yaw(quat)),
            'vx': float(vel[0]), 'vy': float(vel[1]),
            'omega_z': float(omega[2]),
        }

    def get_ene_pose(self) -> dict:
        """Get enemy world pose (for omniscient enemy AI)."""
        ea = self._ene_qpos_adr
        pos = self.data.qpos[ea:ea + 3].copy()
        quat = self.data.qpos[ea + 3:ea + 7].copy()
        vel_adr = self._ene_qvel_adr
        vel = self.data.qvel[vel_adr:vel_adr + 3].copy()
        omega = self.data.qvel[vel_adr + 3:vel_adr + 6].copy()
        return {
            'x': float(pos[0]), 'y': float(pos[1]), 'z': float(pos[2]),
            'angle': float(_quat_to_yaw(quat)),
            'vx': float(vel[0]), 'vy': float(vel[1]),
            'omega_z': float(omega[2]),
        }

    def is_out(self, who: str) -> bool:
        """Check if a robot has fallen off the dohyo."""
        if who == 'bot':
            adr = self._bot_qpos_adr
        else:
            adr = self._ene_qpos_adr

        x, y, z = self.data.qpos[adr:adr + 3]
        r = hypot(x, y)

        # Off arena: center beyond radius + margin, or fallen below surface
        return r > ARENA_RADIUS + 0.03 or z < ARENA_TOP_Z - 0.02


def _yaw_quat(yaw: float) -> np.ndarray:
    """Convert yaw angle to MuJoCo quaternion [w, x, y, z]."""
    return np.array([cos(yaw / 2), 0.0, 0.0, sin(yaw / 2)])


def _quat_to_yaw(quat: np.ndarray) -> float:
    """Extract yaw from MuJoCo quaternion [w, x, y, z]."""
    w, x, y, z = quat
    return atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
