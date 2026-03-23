"""Snatch exercise configuration.

The snatch lifts the bar from the floor to overhead in one continuous
motion.  The wide grip means a slightly different torso angle at the
start compared to the clean.  The catch is an overhead squat position.

Uses the same 3-link planar model and balance utilities as the existing
squat/deadlift factories in ``models.py``.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from ..constants import PLATE_RADIUS_STD_M
from ..models import BodyModel, LagrangianDynamics, _balance_pose


def _snatch_start_angles(body: BodyModel) -> NDArray:
    """Compute starting joint angles for the snatch (bar at plate height).

    Similar to clean start but wider grip means a slightly more upright
    torso (less forward lean needed to reach the bar).
    """
    target_shoulder_h = PLATE_RADIUS_STD_M + body.L_arm
    q0 = np.radians(15)
    q2 = np.radians(48)  # slightly less lean than clean (wider grip)
    needed = target_shoulder_h - body.L[0] * np.cos(q0) - body.L[2] * np.cos(q2)
    cos_q1 = np.clip(needed / body.L[1], -1, 1)
    q1 = -np.arccos(cos_q1)
    return np.array([q0, q1, q2])


def _snatch_via_angles() -> NDArray:
    """Power position / overhead squat catch via-point.

    Deep squat with bar overhead: significant knee flexion, torso
    relatively upright to keep bar overhead.
    """
    q0 = np.radians(20)
    q1 = np.radians(-70)
    q2 = np.radians(15)
    return np.array([q0, q1, q2])


def _snatch_end_angles() -> NDArray:
    """Standing with bar overhead: torso vertical, arms locked out."""
    q0 = np.radians(5)
    q1 = np.radians(-5)
    q2 = np.radians(3)
    return np.array([q0, q1, q2])


def make_snatch_config(
    body: BodyModel, bar_mass: float
) -> tuple[LagrangianDynamics, NDArray, NDArray, NDArray, NDArray]:
    """Create dynamics and trajectory config for the snatch.

    The start uses deadlift-style mass distribution (arms hanging to
    reach the bar), while the end uses squat-style (bar overhead on
    shoulders).  We use the deadlift model for the pull phase dynamics.

    Returns:
        (dynamics, q_start, q_end, q_bounds, q_via)
    """
    load = body.m_arms + bar_mass
    dyn = LagrangianDynamics(body, body.m_deadlift.copy(), body.I_deadlift.copy(), load)

    q_start_raw = _snatch_start_angles(body)
    q_start = _balance_pose(dyn, q_start_raw, "deadlift", bar_mass, adjust_joint=0)

    # End: standing with bar overhead -- use squat-style COM for balance check
    # but keep the same dynamics object
    q_end_raw = _snatch_end_angles()
    q_end = _balance_pose(dyn, q_end_raw, "squat", bar_mass, adjust_joint=0)

    q_via_raw = _snatch_via_angles()
    q_via = _balance_pose(dyn, q_via_raw, "deadlift", bar_mass, adjust_joint=2)

    q_bounds = np.array(
        [
            [np.radians(-5), np.radians(35)],
            [np.radians(-110), np.radians(10)],
            [np.radians(-10), np.radians(80)],
        ]
    )

    return dyn, q_start, q_end, q_bounds, q_via
