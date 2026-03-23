"""3D bench press exercise configuration (16-DOF bilateral model).

Bench press: bar at chest -> lockout.  Supine position; legs are static.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from ..three_d.body3d import BodyModel3D
from ..three_d.dynamics3d import Dynamics3D
from ._common import (
    ANKLE_L,
    ANKLE_R,
    ELBOW_L,
    ELBOW_R,
    HIP_L_ABD,
    HIP_L_FLEX,
    HIP_R_ABD,
    HIP_R_FLEX,
    KNEE_L,
    KNEE_R,
    N_DOF,
    SH_L_ABD,
    SH_L_FLEX,
    SH_R_ABD,
    SH_R_FLEX,
    SPINE_FLEX,
    SPINE_LAT,
    default_bounds,
)


def make_bench_config_3d(
    body: BodyModel3D, bar_mass: float
) -> tuple[Dynamics3D, NDArray, NDArray, NDArray]:
    """Create dynamics and trajectory config for the 3D bench press.

    Returns:
        (dynamics, q_start, q_end, q_bounds)

    Convention: supine position. Lower body is static (knees bent for
    stability).  Shoulder abduction and elbow flexion are the primary movers.
    """
    dyn = Dynamics3D(body=body, load_mass=bar_mass)

    rad = np.radians
    q_start = np.zeros(N_DOF)
    # Legs: knees bent, feet flat (static during bench)
    q_start[ANKLE_L] = q_start[ANKLE_R] = rad(10)
    q_start[KNEE_L] = q_start[KNEE_R] = rad(-60)
    q_start[HIP_L_FLEX] = q_start[HIP_R_FLEX] = rad(60)
    q_start[HIP_L_ABD] = q_start[HIP_R_ABD] = rad(0)
    q_start[SPINE_FLEX] = rad(0)
    q_start[SPINE_LAT] = rad(0)
    # Arms: bar at chest -- shoulders abducted, elbows bent
    q_start[SH_L_FLEX] = q_start[SH_R_FLEX] = rad(90)
    q_start[SH_L_ABD] = q_start[SH_R_ABD] = rad(45)
    q_start[ELBOW_L] = q_start[ELBOW_R] = rad(90)

    q_end = q_start.copy()
    # Lockout: elbows extended, shoulders same
    q_end[ELBOW_L] = q_end[ELBOW_R] = rad(5)

    q_bounds = default_bounds()

    return dyn, q_start, q_end, q_bounds
