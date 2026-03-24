"""3D jerk exercise configuration (16-DOF bilateral model).

Split/push jerk: front rack -> overhead.  Symmetric bilateral movement
with a via-point at the dip position (slight knee bend before drive).
"""

from __future__ import annotations

from numpy.typing import NDArray

from ..three_d.body3d import BodyModel3D
from ..three_d.dynamics3d import Dynamics3D
from ._common import make_symmetric_config_with_via


def make_jerk_config_3d(
    body: BodyModel3D, bar_mass: float
) -> tuple[Dynamics3D, NDArray, NDArray, NDArray, NDArray]:
    """Create dynamics and trajectory config for the 3D jerk."""
    return make_symmetric_config_with_via(
        body,
        bar_mass,
        start={
            "ankle_flex": 5,
            "knee_flex": -10,
            "hip_flex": 5,
            "hip_abd": 0,
            "spine_flex": 5,
            "spine_lat": 0,
            "sh_flex": 80,
            "sh_abd": 0,
            "elbow_flex": 130,
        },
        end={
            "ankle_flex": 5,
            "knee_flex": 0,
            "hip_flex": 0,
            "hip_abd": 0,
            "spine_flex": 0,
            "spine_lat": 0,
            "sh_flex": 170,
            "sh_abd": 0,
            "elbow_flex": 5,
        },
        via={
            "ankle_flex": 15,
            "knee_flex": -30,
            "hip_flex": 15,
            "hip_abd": 0,
            "spine_flex": 5,
            "spine_lat": 0,
            "sh_flex": 80,
            "sh_abd": 0,
            "elbow_flex": 130,
        },
    )
