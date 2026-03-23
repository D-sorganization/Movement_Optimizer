"""3D snatch exercise configuration (16-DOF bilateral model).

Snatch: bar at floor -> overhead in one continuous pull.  Symmetric
bilateral movement with a via-point at the power position.
"""

from __future__ import annotations

from numpy.typing import NDArray

from ..three_d.body3d import BodyModel3D
from ..three_d.dynamics3d import Dynamics3D
from ._common import default_bounds, symmetric_pose


def make_snatch_config_3d(
    body: BodyModel3D, bar_mass: float
) -> tuple[Dynamics3D, NDArray, NDArray, NDArray, NDArray]:
    """Create dynamics and trajectory config for the 3D snatch.

    Returns:
        (dynamics, q_start, q_end, q_bounds, q_via)
    """
    dyn = Dynamics3D(body=body, load_mass=bar_mass)

    # Start: bar on floor, wide grip pull position
    q_start = symmetric_pose(
        ankle_flex=15,
        knee_flex=-60,
        hip_flex=70,
        hip_abd=5,
        spine_flex=10,
        spine_lat=0,
        sh_flex=15,
        sh_abd=20,
        elbow_flex=0,
    )

    # End: overhead squat catch (deep squat with bar overhead)
    q_end = symmetric_pose(
        ankle_flex=5,
        knee_flex=0,
        hip_flex=0,
        hip_abd=0,
        spine_flex=0,
        spine_lat=0,
        sh_flex=170,
        sh_abd=10,
        elbow_flex=5,
    )

    # Via-point: power position (hips extended, bar at hip)
    q_via = symmetric_pose(
        ankle_flex=10,
        knee_flex=-20,
        hip_flex=25,
        hip_abd=5,
        spine_flex=5,
        spine_lat=0,
        sh_flex=30,
        sh_abd=20,
        elbow_flex=0,
    )

    q_bounds = default_bounds()

    return dyn, q_start, q_end, q_bounds, q_via
