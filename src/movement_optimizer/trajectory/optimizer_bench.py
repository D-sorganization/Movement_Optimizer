"""Bench-press-specific helpers for the trajectory optimiser."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from ..constants import BENCH_BAR_PATH_WEIGHT

__all__ = ["compute_bench_bar_cost"]


def compute_bench_bar_cost(q: NDArray, segment_lengths: NDArray, dt: float) -> float:
    """Penalise lateral bar-path deviation for bench press exercises.

    Computes the horizontal hand position from the arm segment lengths and
    joint angles, then returns a weighted integral of squared deviation.

    Preconditions:
        q.shape[1] == 3
        len(segment_lengths) >= 3
        dt > 0
    """
    hand_x = (
        segment_lengths[0] * np.sin(q[:, 0])
        + segment_lengths[1] * np.sin(q[:, 1])
        + segment_lengths[2] * np.sin(q[:, 2])
    )
    return BENCH_BAR_PATH_WEIGHT * float(np.vdot(hand_x, hand_x)) * dt
