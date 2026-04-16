"""Spline construction and trajectory evaluation helpers.

Separating these from :class:`TrajectoryOptimizer` gives them a single
responsibility (spline math) and makes them independently testable.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import CubicSpline

__all__ = [
    "build_splines",
    "eval_trajectory",
]


def build_splines(
    x: NDArray,
    q_start: NDArray,
    q_end: NDArray,
    q_via: NDArray | None,
    t_ctrl: NDArray,
    n_waypoints: int,
    n_dof: int,
) -> list[CubicSpline]:
    """Build per-DOF clamped cubic splines from the flat optimisation vector *x*.

    Parameters:
        x: Flat waypoint vector of length n_waypoints * n_dof.
        q_start: Start configuration, shape (n_dof,).
        q_end: End configuration, shape (n_dof,).
        q_via: Optional via-point configuration, shape (n_dof,).
        t_ctrl: Control-point time grid, length n_waypoints + 2 [+ 1 if q_via].
        n_waypoints: Number of interior waypoints.
        n_dof: Degrees of freedom.

    Returns:
        List of length n_dof, one CubicSpline per DOF.

    Preconditions:
        len(x) == n_waypoints * n_dof
        len(t_ctrl) == n_waypoints + 2 (+ 1 if q_via is not None)
    """
    wp = x.reshape(n_waypoints, n_dof)

    if q_via is not None:
        n_half = n_waypoints // 2
        q_all = np.vstack([q_start, wp[:n_half], q_via, wp[n_half:], q_end])
    else:
        q_all = np.vstack([q_start, wp, q_end])

    return [CubicSpline(t_ctrl, q_all[:, j], bc_type="clamped") for j in range(n_dof)]


def eval_trajectory(
    splines: list[CubicSpline],
    t_eval: NDArray,
) -> tuple[NDArray, NDArray, NDArray, NDArray]:
    """Evaluate position, velocity, acceleration, and jerk at the eval grid.

    Parameters:
        splines: Per-DOF CubicSpline objects (length n_dof).
        t_eval: Evaluation time grid, shape (n_eval,).

    Returns:
        Tuple (q, qd, qdd, qddd), each of shape (n_eval, n_dof).

    Preconditions:
        len(splines) >= 1
        t_eval.ndim == 1
    """
    q = np.column_stack([s(t_eval) for s in splines])
    qd = np.column_stack([s(t_eval, 1) for s in splines])
    qdd = np.column_stack([s(t_eval, 2) for s in splines])
    qddd = np.column_stack([s(t_eval, 3) for s in splines])
    return q, qd, qdd, qddd
