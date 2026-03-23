"""Jerk exercise configuration.

The jerk drives the bar from front rack (shoulders) to overhead lockout.
The lifter dips into a quarter-squat, then explosively extends to press
the bar overhead and catches it with arms locked out.

Uses the same 3-link planar model and balance utilities as the existing
squat/deadlift factories in ``models.py``.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from ..models import BodyModel, LagrangianDynamics, _balance_pose


def _jerk_start_angles() -> NDArray:
    """Front rack position: near-standing with a slight knee bend."""
    q0 = np.radians(5)
    q1 = np.radians(-10)
    q2 = np.radians(3)
    return np.array([q0, q1, q2])


def _jerk_via_angles() -> NDArray:
    """Dip position: quarter-squat before the drive."""
    q0 = np.radians(12)
    q1 = np.radians(-35)
    q2 = np.radians(10)
    return np.array([q0, q1, q2])


def _jerk_end_angles() -> NDArray:
    """Overhead lockout: torso vertical, slight split stance."""
    q0 = np.radians(5)
    q1 = np.radians(-5)
    q2 = np.radians(3)
    return np.array([q0, q1, q2])


def make_jerk_config(
    body: BodyModel, bar_mass: float
) -> tuple[LagrangianDynamics, NDArray, NDArray, NDArray, NDArray]:
    """Create dynamics and trajectory config for the jerk.

    The bar is on the shoulders (squat-style mass distribution: arms
    are part of the torso segment, bar at shoulder level).

    Returns:
        (dynamics, q_start, q_end, q_bounds, q_via)
    """
    dyn = LagrangianDynamics(body, body.m_squat.copy(), body.I_squat.copy(), bar_mass)

    q_start_raw = _jerk_start_angles()
    q_start = _balance_pose(dyn, q_start_raw, "squat", bar_mass, adjust_joint=0)

    q_end_raw = _jerk_end_angles()
    q_end = _balance_pose(dyn, q_end_raw, "squat", bar_mass, adjust_joint=0)

    q_via_raw = _jerk_via_angles()
    q_via = _balance_pose(dyn, q_via_raw, "squat", bar_mass, adjust_joint=2)

    q_bounds = np.array(
        [
            [np.radians(-5), np.radians(30)],
            [np.radians(-50), np.radians(5)],
            [np.radians(-5), np.radians(40)],
        ]
    )

    return dyn, q_start, q_end, q_bounds, q_via
