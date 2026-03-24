"""Shared helpers for planar exercise configuration factories."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from ..models import LagrangianDynamics, balance_pose


def pose_deg(ankle: float, knee: float, hip: float) -> NDArray:
    """Return a 3-angle pose vector built from degree inputs."""
    return np.radians(np.array([ankle, knee, hip], dtype=float))


def balance_config_pose(
    dynamics: LagrangianDynamics,
    raw_pose: NDArray,
    exercise_type: str,
    bar_mass: float,
    *,
    adjust_joint: int,
) -> NDArray:
    """Balance a raw pose using the shared planar balance helper."""
    return balance_pose(dynamics, raw_pose, exercise_type, bar_mass, adjust_joint=adjust_joint)


def default_bounds_deg(
    lower: tuple[float, float], middle: tuple[float, float], upper: tuple[float, float]
) -> NDArray:
    """Return a `(3, 2)` array of joint bounds built from degree tuples."""
    return np.radians(np.array([lower, middle, upper], dtype=float))
