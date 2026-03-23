"""3D squat exercise configuration (16-DOF bilateral model).

Full squat: standing -> bottom -> standing.  Symmetric bilateral movement.
"""

from __future__ import annotations

from numpy.typing import NDArray

from ..three_d.body3d import BodyModel3D
from ..three_d.dynamics3d import Dynamics3D
from ._common import default_bounds, symmetric_pose


def make_squat_config_3d(
    body: BodyModel3D, bar_mass: float
) -> tuple[Dynamics3D, NDArray, NDArray, NDArray, NDArray]:
    """Create dynamics and trajectory config for the 3D squat.

    Returns:
        (dynamics, q_start, q_end, q_bounds, q_via)
        q_via is the bottom position for a full squat.
    """
    dyn = Dynamics3D(body=body, load_mass=bar_mass)

    # Standing (start and end): slight ankle dorsiflexion, arms holding bar on back
    q_start = symmetric_pose(
        ankle_flex=5,
        knee_flex=0,
        hip_flex=0,
        hip_abd=0,
        spine_flex=5,
        spine_lat=0,
        sh_flex=-20,
        sh_abd=30,
        elbow_flex=90,
    )
    q_end = q_start.copy()

    # Bottom of squat: deep flexion
    q_via = symmetric_pose(
        ankle_flex=25,
        knee_flex=-90,
        hip_flex=90,
        hip_abd=5,
        spine_flex=15,
        spine_lat=0,
        sh_flex=-20,
        sh_abd=30,
        elbow_flex=90,
    )

    q_bounds = default_bounds()

    return dyn, q_start, q_end, q_bounds, q_via
