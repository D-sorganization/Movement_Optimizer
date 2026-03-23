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
    "lower_legs": 0.093,
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
}

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
# Base-of-support constraint: fraction of foot that is "in bounds"
# The outer 20% on each end is excluded.
# ------------------------------------------------------------------
BOS_INNER_FRACTION: float = 0.60

# numpy compat shim  (trapz renamed to trapezoid in numpy 2.0)
trapezoid = getattr(np, "trapezoid", getattr(np, "trapz", None))
