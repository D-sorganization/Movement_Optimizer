"""3D clean exercise configuration (16-DOF bilateral model).

Power clean: bar at floor -> front rack.  Symmetric bilateral movement
with a via-point at the power position (bar at mid-thigh, hips extended).
"""

from __future__ import annotations

from numpy.typing import NDArray

from ..three_d.body3d import BodyModel3D
from ..three_d.dynamics3d import Dynamics3D
from ._common import make_symmetric_config_with_via


def make_clean_config_3d(
    body: BodyModel3D, bar_mass: float
) -> tuple[Dynamics3D, NDArray, NDArray, NDArray, NDArray]:
    """Create dynamics and trajectory config for the 3D clean."""
    return make_symmetric_config_with_via(
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
            "knee_flex": -15,
            "hip_flex": 5,
            "hip_abd": 0,
            "spine_flex": 5,
            "spine_lat": 0,
            "sh_flex": 80,
            "sh_abd": 0,
            "elbow_flex": 130,
        },
        via={
            "ankle_flex": 10,
            "knee_flex": -20,
            "hip_flex": 25,
            "hip_abd": 0,
            "spine_flex": 5,
            "spine_lat": 0,
            "sh_flex": 10,
            "sh_abd": 0,
            "elbow_flex": 0,
        },
    )
