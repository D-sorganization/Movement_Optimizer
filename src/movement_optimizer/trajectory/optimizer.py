"""Parallel multi-start trajectory optimiser engine."""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import CubicSpline

from ..backend import PhysicsBackend
from ..constants import BENCH_BAR_PATH_WEIGHT
from ..models import BodyModel
from .optimizer_constraints import build_constraints
from .optimizer_cost import (
    compute_balance_cost,
    compute_endpoint_damping_cost,
    compute_jerk_cost,
    compute_torque_cost,
    compute_torque_rate_cost,
)
from .optimizer_diagnostics import run_minimize, run_single_start
from .optimizer_guess import build_bounds, build_initial_guess, build_perturbed_guess
from .optimizer_packaging import (
    build_result_object,
    check_com_feasibility,
    count_joint_limit_violations,
    evaluate_solution,
)
from .optimizer_parallel import run_parallel_starts, select_best_result
from .optimizer_progress import ProgressTracker, detect_stall
from .result import CancelledError, OptimizationResult, ProgressReport
from .tuning import (
    BALANCE_CENTER_WEIGHT,
    DEFAULT_ENDPOINT_WEIGHT,
    DEFAULT_JERK_WEIGHT,
    DEFAULT_N_STARTS,
    DEFAULT_TORQUE_RATE_WEIGHT,
    MAX_ITER_PER_START,
)

logger = logging.getLogger(__name__)


class TrajectoryOptimizer:
    """Parallel multi-start SLSQP trajectory optimiser.

    Enforces COM within the inner 60% of the foot via hard inequality constraints.
    Multiple starts run concurrently; the best solution is returned.

    Preconditions: q_start/q_end length-3; q_bounds (3,2); n_waypoints >= 4.
    """

    def __init__(
        self,
        body: BodyModel,
        dynamics: PhysicsBackend,
        exercise_type: str,
        bar_mass: float,
        q_start: NDArray,
        q_end: NDArray,
        q_bounds: NDArray,
        *,
        q_via: NDArray | None = None,
        duration: float = 2.0,
        n_waypoints: int = 12,
        n_eval: int = 60,
        jerk_weight: float = DEFAULT_JERK_WEIGHT,
        torque_rate_weight: float = DEFAULT_TORQUE_RATE_WEIGHT,
        endpoint_weight: float = DEFAULT_ENDPOINT_WEIGHT,
        smoothness: float = 1.0,
        n_starts: int = DEFAULT_N_STARTS,
        progress_cb: Callable[[ProgressReport], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        if n_waypoints < 4:
            raise ValueError("need >= 4 waypoints")
        n_dof = q_bounds.shape[0]
        if q_bounds.shape != (n_dof, 2):
            raise ValueError(f"q_bounds must be ({n_dof},2)")
        self.n_dof = n_dof
        self.body, self.dynamics = body, dynamics
        self.exercise_type, self.bar_mass = exercise_type, bar_mass
        self.q_start, self.q_end, self.q_bounds, self.q_via = q_start, q_end, q_bounds, q_via
        self.duration, self.n_waypoints, self.n_eval = duration, n_waypoints, n_eval
        self.progress_cb, self.n_starts = progress_cb, n_starts
        self.cancel_event = cancel_event or threading.Event()
        self.jerk_weight = jerk_weight * smoothness
        self.torque_rate_weight = torque_rate_weight * smoothness
        self.endpoint_weight = endpoint_weight * smoothness
        self.inner_heel, self.inner_toe, self.inner_center = (
            body.inner_heel,
            body.inner_toe,
            body.inner_center,
        )
        self.balance_center_weight = BALANCE_CENTER_WEIGHT
        self._setup_time_grids()
        self.dt = duration / (n_eval - 1)
        self._n_damp = max(2, n_eval // 8)
        self._damp_weights = 1.0 - np.arange(self._n_damp) / self._n_damp
        self._progress = ProgressTracker(progress_cb=progress_cb)
        self._progress_lock = self._progress.lock()

    def _setup_time_grids(self) -> None:
        n_ctrl = self.n_waypoints + 2
        if self.q_via is not None:
            n_ctrl += 1
        self.t_ctrl = np.linspace(0, self.duration, n_ctrl)
        self.t_eval = np.linspace(0, self.duration, self.n_eval, dtype=np.float64)

    def build_splines(self, x: NDArray) -> list[CubicSpline]:
        """Build cubic splines from the flat optimisation vector *x*."""
        wp = x.reshape(self.n_waypoints, self.n_dof)

        if self.q_via is not None:
            n_half = self.n_waypoints // 2
            q_all = np.vstack([self.q_start, wp[:n_half], self.q_via, wp[n_half:], self.q_end])
        else:
            q_all = np.vstack([self.q_start, wp, self.q_end])

        return [CubicSpline(self.t_ctrl, q_all[:, j], bc_type="clamped") for j in range(self.n_dof)]

    def eval_trajectory(
        self, splines: list[CubicSpline]
    ) -> tuple[NDArray, NDArray, NDArray, NDArray]:
        """Evaluate position, velocity, acceleration, jerk at eval grid."""
        q = np.column_stack([s(self.t_eval) for s in splines])
        qd = np.column_stack([s(self.t_eval, 1) for s in splines])
        qdd = np.column_stack([s(self.t_eval, 2) for s in splines])
        qddd = np.column_stack([s(self.t_eval, 3) for s in splines])
        return q, qd, qdd, qddd

    def _compute_cost(self, x: NDArray) -> float:
        """Compute total cost without mutating instance state."""
        if self.cancel_event.is_set():
            return float("inf")

        splines = self.build_splines(x)
        q, qd, qdd, qddd = self.eval_trajectory(splines)
        torques = self.dynamics.inverse_dynamics_batch(q, qd, qdd)

        total = (
            compute_torque_cost(torques, self.dt)
            + compute_jerk_cost(qddd, self.dt, self.jerk_weight)
            + compute_torque_rate_cost(torques, self.dt, self.torque_rate_weight)
            + compute_endpoint_damping_cost(
                qd, qdd, self.dt, self.endpoint_weight, self._n_damp, self._damp_weights
            )
        )

        if self.exercise_type == "bench_press":
            L = self.dynamics.L  # type: ignore[attr-defined]
            hand_x = L[0] * np.sin(q[:, 0]) + L[1] * np.sin(q[:, 1]) + L[2] * np.sin(q[:, 2])
            total += BENCH_BAR_PATH_WEIGHT * float(np.sum(hand_x**2)) * self.dt
        else:
            com_x = self.dynamics.com_x_batch(q, self.exercise_type, self.bar_mass)
            total += compute_balance_cost(
                com_x, self.inner_center, self.dt, self.balance_center_weight
            )

        return total

    def cost(self, x: NDArray) -> float:
        """Total cost with progress tracking (single-thread path)."""
        total = self._compute_cost(x)
        self._progress.record(total)
        return total

    @property
    def _cost_history(self) -> list[float]:
        return self._progress.cost_history

    @_cost_history.setter
    def _cost_history(self, value: list[float]) -> None:
        self._progress.cost_history = value

    def _detect_stall(self) -> tuple[bool, str]:
        return detect_stall(self._progress.cost_history)

    def _initial_guess(self) -> NDArray:
        return build_initial_guess(
            self.q_start, self.q_end, self.n_waypoints, self.n_dof, self.q_via
        )

    def _perturbed_guess(self, seed: int) -> NDArray:
        return build_perturbed_guess(
            self.q_start,
            self.q_end,
            self.q_bounds,
            self.n_waypoints,
            self.n_dof,
            seed,
            self.q_via,
        )

    def _build_bounds(self) -> list[tuple[float, float]]:
        return build_bounds(self.q_bounds, self.n_waypoints, self.n_dof)

    def _build_constraints(self) -> list[dict]:
        """Delegate to optimizer_constraints.build_constraints."""
        return build_constraints(
            self.exercise_type,
            self.build_splines,
            self.t_eval,
            self.dynamics,
            self.bar_mass,
            self.inner_heel,
            self.inner_toe,
            self.q_bounds,
            self.body,
        )

    def _minimize_single(
        self, x0: NDArray, cost_fn: Callable, max_iter: int = MAX_ITER_PER_START
    ) -> object:
        return run_minimize(
            x0,
            cost_fn,
            self._build_bounds(),
            self._build_constraints(),
            self.cancel_event,
            max_iter=max_iter,
        )

    def _run_single_start(self, seed: int) -> tuple[object, int] | None:
        return run_single_start(
            seed,
            self._perturbed_guess,
            self._compute_cost,
            self._build_bounds(),
            self._build_constraints(),
            self.cancel_event,
        )

    def optimize(self) -> OptimizationResult:
        """Run parallel multi-start SLSQP and return best result."""
        self._progress.reset()

        n_workers = min(self.n_starts, os.cpu_count() or 4)
        logger.info(
            "Starting optimisation: exercise=%s, n_starts=%d, n_workers=%d, n_wp=%d",
            self.exercise_type,
            self.n_starts,
            n_workers,
            self.n_waypoints,
        )

        if n_workers <= 1 or self.n_starts <= 1:
            return self._optimize_single_start()

        results = run_parallel_starts(
            self.n_starts,
            n_workers,
            self._run_single_start,
            self.cancel_event.is_set,
            self._progress.record_parallel,
        )
        return self._finalize_parallel_results(results)

    def _optimize_single_start(self) -> OptimizationResult:
        """Run single-start path and package its result."""
        self._progress.reset()
        wp0 = self._initial_guess()
        out = self._minimize_single(wp0.flatten(), self.cost, max_iter=MAX_ITER_PER_START * 2)
        if self.cancel_event.is_set():
            raise CancelledError("Optimization cancelled by user")
        return self._package_results(out, self._progress.elapsed())

    def _finalize_parallel_results(self, results: list[tuple[object, int]]) -> OptimizationResult:
        """Select the best result, log summary, and package output."""
        if not results:
            raise CancelledError("All optimization starts were cancelled")

        best_res, total_evals = select_best_result(results)
        elapsed = self._progress.elapsed()

        logger.info(
            "Optimisation finished: best_cost=%.2f, total_evals=%d, n_starts=%d, time=%.1fs",
            best_res.fun,  # type: ignore[attr-defined]
            total_evals,
            len(results),
            elapsed,
        )
        return self._package_results(best_res, elapsed, total_evals)

    def _check_solution_feasibility(
        self, res: object, q: NDArray, com_x: NDArray
    ) -> tuple[bool, int]:
        """Assess cost finiteness, COM bounds, and joint-limit violations.

        Args:
            res: SciPy OptimizeResult (provides ``res.fun``).
            q: Joint-angle trajectory, shape (N, 3).
            com_x: Horizontal COM trajectory, shape (N,).

        Returns:
            ``(success, n_joint_limit_violations)``
        """
        cost_val = float(res.fun)  # type: ignore[attr-defined]
        cost_finite = cost_val < float("inf") and not np.isnan(cost_val)
        com_in_bounds = check_com_feasibility(
            cost_finite, com_x, self.exercise_type, self.inner_heel, self.inner_toe
        )
        n_viol = count_joint_limit_violations(q, self.q_bounds)
        return cost_finite and com_in_bounds, n_viol

    def _package_results(
        self, res: object, elapsed: float = 0.0, n_evals: int = 0
    ) -> OptimizationResult:
        """Evaluate trajectories, assess feasibility, and build the result."""
        q, qd, qdd, torques, power, com_traj, bar_traj, com_x = evaluate_solution(
            res,
            self.dynamics,
            self.exercise_type,
            self.bar_mass,
            self.build_splines,
            self.eval_trajectory,
        )
        success, n_viol = self._check_solution_feasibility(res, q, com_x)
        return build_result_object(
            t_eval=self.t_eval,
            res=res,
            q=q,
            qd=qd,
            qdd=qdd,
            torques=torques,
            power=power,
            com_traj=com_traj,
            bar_traj=bar_traj,
            com_x=com_x,
            success=success,
            n_joint_limit_violations=n_viol,
            elapsed=elapsed,
            n_evals=n_evals or self._progress.iteration_count,
        )
