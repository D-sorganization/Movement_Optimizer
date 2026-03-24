"""3D deadlift exercise configuration (16-DOF bilateral model).

Conventional deadlift: bar at floor -> lockout.  Symmetric bilateral movement.
"""

from __future__ import annotations

from numpy.typing import NDArray

from ..three_d.body3d import BodyModel3D
from ..three_d.dynamics3d import Dynamics3D
from ._common import make_symmetric_config


def make_deadlift_config_3d(
    body: BodyModel3D, bar_mass: float
) -> tuple[Dynamics3D, NDArray, NDArray, NDArray]:
    """Create dynamics and trajectory config for the 3D deadlift."""
    return make_symmetric_config(
        body,
        bar_mass,
        start={
            "ankle_flex": 15,
            "knee_flex": -60,
            "hip_flex": 70,
            "hip_abd": 0,
            "spine_flex": 10,
            "spine_lat": 0,
            "sh_flex": 10,
            "sh_abd": 0,
            "elbow_flex": 0,
        },
        end={
            "ankle_flex": 5,
            "knee_flex": 0,
            "hip_flex": 0,
            "hip_abd": 0,
            "spine_flex": 0,
            "spine_lat": 0,
            "sh_flex": 0,
            "sh_abd": 0,
            "elbow_flex": 0,
        },
    )
