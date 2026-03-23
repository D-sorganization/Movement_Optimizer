"""Clean exercise configuration.

The clean lifts the bar from the floor to front rack (shoulder height).
The motion is modelled as a deadlift-style pull followed by a catch
at the shoulders with a slight squat.

Uses the same 3-link planar model and balance utilities as the existing
squat/deadlift factories in ``models.py``.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from ..constants import PLATE_RADIUS_STD_M
from ..models import BodyModel, LagrangianDynamics, balance_pose


def _clean_start_angles(body: BodyModel) -> NDArray:
    """Compute starting joint angles for the clean (bar at plate height).

    Similar to deadlift start: bar at plate height, arms hanging.
    """
    target_shoulder_h = PLATE_RADIUS_STD_M + body.L_arm
    q0 = np.radians(15)
    q2 = np.radians(52)
    needed = target_shoulder_h - body.L[0] * np.cos(q0) - body.L[2] * np.cos(q2)
    cos_q1 = np.clip(needed / body.L[1], -1, 1)
    q1 = -np.arccos(cos_q1)
    return np.array([q0, q1, q2])


def _clean_end_angles(body: BodyModel) -> NDArray:
    """Compute end joint angles for front rack position.

    Front rack: standing with bar at shoulder (clavicle) height.
    Torso near vertical (~5 deg), knees nearly straight.
    The bar rests on the front of the shoulders -- NOT overhead.
    """
    q0 = np.radians(5)  # slight shin forward lean
    q1 = np.radians(-8)  # nearly straight knees (standing)
    q2 = np.radians(5)  # torso near vertical
    return np.array([q0, q1, q2])


def _clean_via_angles(body: BodyModel) -> NDArray:
    """Compute via-point at the power position (second pull).

    Hips extended, bar at mid-thigh level.  This is the transition
    between the pull phase and the catch phase.
    """
    q0 = np.radians(8)  # shins near vertical
    q1 = np.radians(-15)  # knees slightly bent
    q2 = np.radians(20)  # torso still leaning forward (pulling)
    return np.array([q0, q1, q2])


def make_clean_config(
    body: BodyModel, bar_mass: float
) -> tuple[LagrangianDynamics, NDArray, NDArray, NDArray, NDArray]:
    """Create dynamics and trajectory config for the clean.

    Returns:
        (dynamics, q_start, q_end, q_bounds, q_via)

    The dynamics use deadlift-style mass distribution (arms hang, load
    is arm_mass + bar_mass at end effector).
    """
    load = body.m_arms + bar_mass
    dyn = LagrangianDynamics(body, body.m_deadlift.copy(), body.I_deadlift.copy(), load)

    q_start_raw = _clean_start_angles(body)
    q_start = balance_pose(dyn, q_start_raw, "deadlift", bar_mass, adjust_joint=0)

    q_end_raw = _clean_end_angles(body)
    q_end = balance_pose(dyn, q_end_raw, "deadlift", bar_mass, adjust_joint=2)

    q_via_raw = _clean_via_angles(body)
    q_via = balance_pose(dyn, q_via_raw, "deadlift", bar_mass, adjust_joint=2)

    q_bounds = np.array(
        [
            [np.radians(-5), np.radians(35)],
            [np.radians(-110), np.radians(10)],
            [np.radians(-10), np.radians(80)],
        ]
    )

    return dyn, q_start, q_end, q_bounds, q_via
