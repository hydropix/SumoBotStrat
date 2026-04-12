"""VL53L0X laser distance sensor simulation via MuJoCo raycasting."""

import mujoco
import numpy as np

LASER_RANGE = 0.80  # max range in meters


def read_lasers(model: mujoco.MjModel, data: mujoco.MjData,
                site_names: list[str], exclude_body_id: int) -> list[float]:
    """
    Cast rays from laser sites and return distances in meters.

    Args:
        model: MuJoCo model
        data: MuJoCo data (after mj_step)
        site_names: List of 3 site names [center, left, right]
        exclude_body_id: Body ID of the robot itself (don't hit own geoms)

    Returns:
        List of 3 distances in meters. LASER_RANGE if no hit.
    """
    distances = []
    geomid = np.array([-1], dtype=np.int32)

    for name in site_names:
        site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, name)
        origin = data.site_xpos[site_id].copy()
        # Site X-axis (forward direction) from rotation matrix
        xmat = data.site_xmat[site_id].reshape(3, 3)
        direction = xmat[:, 0].copy()  # first column = X-axis

        dist = mujoco.mj_ray(
            model, data, origin, direction,
            geomgroup=None, flg_static=0,
            bodyexclude=exclude_body_id, geomid=geomid
        )

        if dist < 0 or dist > LASER_RANGE:
            distances.append(LASER_RANGE)
        else:
            distances.append(float(dist))

    return distances
