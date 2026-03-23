"""3D physics foundation for the Movement-Optimizer.

Re-exports key classes and functions for convenient access.
"""

from .body3d import BodyModel3D
from .dynamics3d import Dynamics3D
from .math3d import (
    cylinder_mesh,
    ellipsoid_mesh,
    homogeneous_transform,
    rotation_axis_angle,
    rotation_x,
    rotation_y,
    rotation_z,
    sphere_mesh,
    transform_point,
)

__all__ = [
    "BodyModel3D",
    "Dynamics3D",
    "cylinder_mesh",
    "ellipsoid_mesh",
    "homogeneous_transform",
    "rotation_axis_angle",
    "rotation_x",
    "rotation_y",
    "rotation_z",
    "sphere_mesh",
    "transform_point",
]
