"""3D clean exercise configuration (16-DOF bilateral model).

Power clean: bar at floor -> front rack.  Symmetric bilateral movement
with a via-point at the power position (bar at mid-thigh, hips extended).
"""

from __future__ import annotations

from numpy.typing import NDArray

from ..three_d.body3d import BodyModel3D
from ..three_d.dynamics3d import Dynamics3D
from ._common import default_bounds, symmetric_pose


def make_clean_config_3d(
    body: BodyModel3D, bar_mass: float
) -> tuple[Dynamics3D, NDArray, NDArray, NDArray, NDArray]:
    """Create dynamics and trajectory config for the 3D clean.

    Returns:
        (dynamics, q_start, q_end, q_bounds, q_via)
    """
    dyn = Dynamics3D(body=body, load_mass=bar_mass)

    # Start: bar on floor, deadlift-like pull position
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

    # End: front rack (standing with bar at shoulders, elbows high)
    q_end = symmetric_pose(
        ankle_flex=5,
        knee_flex=-15,
        hip_flex=5,
        hip_abd=0,
        spine_flex=5,
        spine_lat=0,
        sh_flex=80,
        sh_abd=0,
        elbow_flex=130,
    )

    # Via-point: power position (hips extended, bar at mid-thigh)
    q_via = symmetric_pose(
        ankle_flex=10,
        knee_flex=-20,
        hip_flex=25,
        hip_abd=0,
        spine_flex=5,
        spine_lat=0,
        sh_flex=10,
        sh_abd=0,
        elbow_flex=0,
    )

    q_bounds = default_bounds()

    return dyn, q_start, q_end, q_bounds, q_via
