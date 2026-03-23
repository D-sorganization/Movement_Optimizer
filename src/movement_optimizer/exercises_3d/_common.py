"""Shared helpers for 3D exercise configs.

Joint order (16 DOF):
    [0]  ankle_l_flex      [1]  knee_l_flex       [2]  hip_l_flex       [3]  hip_l_abd
    [4]  ankle_r_flex      [5]  knee_r_flex       [6]  hip_r_flex       [7]  hip_r_abd
    [8]  spine_flex        [9]  spine_lat
    [10] shoulder_l_flex   [11] shoulder_l_abd    [12] elbow_l_flex
    [13] shoulder_r_flex   [14] shoulder_r_abd    [15] elbow_r_flex

For symmetric exercises, left DOFs (0-3, 10-12) mirror right DOFs (4-7, 13-15).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

# Named indices for clarity
ANKLE_L, KNEE_L, HIP_L_FLEX, HIP_L_ABD = 0, 1, 2, 3
ANKLE_R, KNEE_R, HIP_R_FLEX, HIP_R_ABD = 4, 5, 6, 7
SPINE_FLEX, SPINE_LAT = 8, 9
SH_L_FLEX, SH_L_ABD, ELBOW_L = 10, 11, 12
SH_R_FLEX, SH_R_ABD, ELBOW_R = 13, 14, 15

N_DOF = 16


def symmetric_pose(
    ankle_flex: float,
    knee_flex: float,
    hip_flex: float,
    hip_abd: float,
    spine_flex: float,
    spine_lat: float,
    sh_flex: float,
    sh_abd: float,
    elbow_flex: float,
) -> NDArray:
    """Build a 16-DOF pose vector with bilateral symmetry (angles in degrees)."""
    q = np.zeros(N_DOF)
    rad = np.radians
    q[ANKLE_L] = q[ANKLE_R] = rad(ankle_flex)
    q[KNEE_L] = q[KNEE_R] = rad(knee_flex)
    q[HIP_L_FLEX] = q[HIP_R_FLEX] = rad(hip_flex)
    q[HIP_L_ABD] = q[HIP_R_ABD] = rad(hip_abd)
    q[SPINE_FLEX] = rad(spine_flex)
    q[SPINE_LAT] = rad(spine_lat)
    q[SH_L_FLEX] = q[SH_R_FLEX] = rad(sh_flex)
    q[SH_L_ABD] = q[SH_R_ABD] = rad(sh_abd)
    q[ELBOW_L] = q[ELBOW_R] = rad(elbow_flex)
    return q


def default_bounds() -> NDArray:
    """Return conservative joint limits as (16, 2) array in radians."""
    rad = np.radians
    bounds = np.zeros((N_DOF, 2))
    # Ankles
    bounds[ANKLE_L] = bounds[ANKLE_R] = [rad(-15), rad(35)]
    # Knees (negative = flexion in our convention)
    bounds[KNEE_L] = bounds[KNEE_R] = [rad(-140), rad(5)]
    # Hip flexion
    bounds[HIP_L_FLEX] = bounds[HIP_R_FLEX] = [rad(-15), rad(120)]
    # Hip abduction
    bounds[HIP_L_ABD] = bounds[HIP_R_ABD] = [rad(-10), rad(45)]
    # Spine flexion
    bounds[SPINE_FLEX] = [rad(-10), rad(60)]
    # Spine lateral
    bounds[SPINE_LAT] = [rad(-20), rad(20)]
    # Shoulder flexion
    bounds[SH_L_FLEX] = bounds[SH_R_FLEX] = [rad(-30), rad(180)]
    # Shoulder abduction
    bounds[SH_L_ABD] = bounds[SH_R_ABD] = [rad(-10), rad(90)]
    # Elbow flexion
    bounds[ELBOW_L] = bounds[ELBOW_R] = [rad(0), rad(145)]
    return bounds
