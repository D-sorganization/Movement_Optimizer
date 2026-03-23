"""3D deadlift exercise configuration (16-DOF bilateral model).

Conventional deadlift: bar at floor -> lockout.  Symmetric bilateral movement.
"""

from __future__ import annotations

from numpy.typing import NDArray

from ..three_d.body3d import BodyModel3D
from ..three_d.dynamics3d import Dynamics3D
from ._common import default_bounds, symmetric_pose


def make_deadlift_config_3d(
    body: BodyModel3D, bar_mass: float
) -> tuple[Dynamics3D, NDArray, NDArray, NDArray]:
    """Create dynamics and trajectory config for the 3D deadlift.

    Returns:
        (dynamics, q_start, q_end, q_bounds)
    """
    dyn = Dynamics3D(body=body, load_mass=bar_mass)

    # Start: bar on floor, bent over with arms hanging
    q_start = symmetric_pose(
        ankle_flex=15,
        knee_flex=-60,
        hip_flex=70,
        hip_abd=0,
        spine_flex=10,
        spine_lat=0,
        sh_flex=10,
        sh_abd=0,
        elbow_flex=0,
    )

    # End: standing lockout, arms hanging with bar
    q_end = symmetric_pose(
        ankle_flex=5,
        knee_flex=0,
        hip_flex=0,
        hip_abd=0,
        spine_flex=0,
        spine_lat=0,
        sh_flex=0,
        sh_abd=0,
        elbow_flex=0,
    )

    q_bounds = default_bounds()

    return dyn, q_start, q_end, q_bounds
