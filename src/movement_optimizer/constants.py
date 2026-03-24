"""Anthropometric and equipment constants.

Sources:
    Winter, D.A. (2009). Biomechanics and Motor Control of Human Movement.
    Segment mass and length fractions for a standard adult.
"""

from __future__ import annotations

import numpy as np

# ------------------------------------------------------------------
# Segment mass fractions  (fraction of total body mass)
# Bilateral segments are lumped into a single 2-D sagittal-plane value.
# ------------------------------------------------------------------
MASS_FRAC: dict[str, float] = {
    "feet": 0.028,
    "lower_legs": 0.094,
    "upper_legs": 0.200,
    "trunk_head": 0.578,
    "arms": 0.100,
}

# ------------------------------------------------------------------
# Segment length fractions  (fraction of body height)
# ------------------------------------------------------------------
LENGTH_FRAC: dict[str, float] = {
    "lower_leg": 0.246,
    "upper_leg": 0.245,
    "torso": 0.288,
    "arm": 0.387,
    "foot": 0.152,
    "neck": 0.075,  # C7 to base of skull, ~7.5% of height
}

# ------------------------------------------------------------------
# Neck joint angle limit (degrees)
#
# The neck can tilt up to 45 degrees in any direction relative to the
# torso.  The 2-D model does not currently have a separate neck DOF,
# but the constant is documented here so the rendering keeps the neck
# roughly aligned with the torso.
# ------------------------------------------------------------------
NECK_MAX_ANGLE_DEG: float = 45.0

# ------------------------------------------------------------------
# COM position as fraction of segment length from proximal joint
# ------------------------------------------------------------------
COM_FRAC: dict[str, float] = {
    "lower_leg": 0.433,
    "upper_leg": 0.433,
    "torso": 0.500,
    "arm": 0.530,
    "foot": 0.500,
}

# ------------------------------------------------------------------
# Standard Olympic barbell
# ------------------------------------------------------------------
BAR_MASS_KG: float = 20.0
BAR_LENGTH_M: float = 2.20
PLATE_RADIUS_STD_M: float = 0.225
BAR_RADIUS_M: float = 0.025

# ------------------------------------------------------------------
# Default exercise angles (radians)
# ------------------------------------------------------------------
SQUAT_BOTTOM = np.array([np.radians(20), np.radians(-90), np.radians(40)])
STANDING = np.array([0.0, 0.0, 0.0])

# ------------------------------------------------------------------
# Anatomical joint angle limits (radians)
#
# These represent the physiological range of motion for each joint
# in the sagittal-plane model.  Convention: angles are measured from
# the vertical (0 = straight).
#
# Sources: Norkin & White (2016), Joint Range of Motion.
# ------------------------------------------------------------------
JOINT_LIMITS: dict[str, tuple[float, float]] = {
    # Ankle: dorsiflexion (-20°) to plantarflexion (+50°)
    "ankle": (np.radians(-20), np.radians(50)),
    # Knee: full extension (+5°) to full flexion (-140°)
    "knee": (np.radians(-140), np.radians(5)),
    # Hip: full flexion forward (+120°) to hyperextension (-10°)
    "hip": (np.radians(-10), np.radians(120)),
}

# Joint names for the 3-link chain (index → name)
JOINT_NAMES: tuple[str, ...] = ("ankle", "knee", "hip")

# ------------------------------------------------------------------
# Default maximum isometric joint torques (N·m)
#
# Representative values for an average adult male.  These are the
# τ_max parameter in the Hill-type torque-angle-velocity model.
#
# Sources: Anderson et al. (2007), Biomechanics and Motor Control.
# ------------------------------------------------------------------
DEFAULT_MAX_JOINT_TORQUES: dict[str, float] = {
    "ankle": 150.0,
    "knee": 250.0,
    "hip": 250.0,
}

# ------------------------------------------------------------------
# Hill-type torque model parameters
#
# The available torque at each joint is:
#   τ_avail = τ_max · f_angle(q) · f_velocity(qd)
#
# f_angle: Gaussian-shaped torque-angle curve centered at q_opt
#   f_angle = exp(-((q - q_opt) / angle_width)²)
#
# f_velocity: Hill's force-velocity relationship
#   concentric (shortening):  f_vel = (v_max - |qd|) / (v_max + |qd| / k_shape)
#   eccentric (lengthening):  f_vel = (1 + ecc_factor * |qd|) / (1 + |qd| / k_shape)
#   clamped to [0, max_eccentric_ratio]
# ------------------------------------------------------------------
HILL_OPTIMAL_ANGLES: dict[str, float] = {
    "ankle": np.radians(15),
    "knee": np.radians(-45),
    "hip": np.radians(45),
}

HILL_ANGLE_WIDTH: float = np.radians(60)

HILL_MAX_ANGULAR_VELOCITY: float = np.radians(600)

HILL_K_SHAPE: float = 0.25

HILL_ECCENTRIC_FACTOR: float = 0.3

HILL_MAX_ECCENTRIC_RATIO: float = 1.4

# ------------------------------------------------------------------
# Bench press model constants
#
# The bench press is modelled as a supine press: the lifter lies on
# a bench with the bar at chest level and presses vertically.  In the
# sagittal plane this is a 2-link chain (upper arm + forearm) with the
# shoulder as the fixed pivot.  For the 3-link model we map:
#   q[0] → shoulder flexion/extension
#   q[1] → elbow flexion/extension
#   q[2] → wrist (held fixed, ≈ 0)
#
# Segment fractions for the arm chain (fraction of arm length):
# ------------------------------------------------------------------
BENCH_UPPER_ARM_FRAC: float = 0.56  # shoulder to elbow (anatomical ~48% + shoulder width)
BENCH_FOREARM_FRAC: float = 0.38  # elbow to wrist (anatomical ~38%)

BENCH_PRESS_JOINT_LIMITS: dict[str, tuple[float, float]] = {
    "shoulder": (np.radians(-5), np.radians(95)),  # main driver of the press
    "elbow": (np.radians(-110), np.radians(5)),  # tighter: lockout to ~110 deg flexion
    "wrist": (np.radians(-1), np.radians(1)),  # effectively locked straight
}

BENCH_PRESS_JOINT_NAMES: tuple[str, ...] = ("shoulder", "elbow", "wrist")

BENCH_PRESS_MAX_JOINT_TORQUES: dict[str, float] = {
    "shoulder": 120.0,
    "elbow": 80.0,
    "wrist": 30.0,
}

BENCH_PRESS_HILL_OPTIMAL_ANGLES: dict[str, float] = {
    "shoulder": np.radians(45),
    "elbow": np.radians(-70),
    "wrist": np.radians(0),
}

# ------------------------------------------------------------------
# Base-of-support constraint: fraction of foot that is "in bounds"
# The outer 20% on each end is excluded.
# ------------------------------------------------------------------
BOS_INNER_FRACTION: float = 0.60

# ------------------------------------------------------------------
# Trajectory optimisation tuning constants
# ------------------------------------------------------------------

# Bench press bar-path penalty weight: penalises horizontal deviation of
# the bar (hand position) from a vertical path during the press.
BENCH_BAR_PATH_WEIGHT: float = 500.0

# Total-variation weight ratio: TV regularisation is this fraction of the
# L2 torque-rate regularisation term.
TV_RATE_WEIGHT_RATIO: float = 0.1

# Minimum bar-to-knee clearance for pulling exercises (deadlift, clean,
# snatch).  The bar must stay at least this many metres in front of the
# knees throughout the lift.
BAR_KNEE_CLEARANCE_M: float = 0.05

from typing import Any, Callable

# numpy compat shim (trapz renamed to trapezoid in numpy 2.0)
_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))
if _trapz is None:
    raise ImportError("Neither np.trapezoid nor np.trapz found in numpy")
trapezoid: Callable[..., Any] = _trapz
