"""Parallel multi-start trajectory optimiser engine."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import CubicSpline
from scipy.optimize import minimize

from ..backend import PhysicsBackend
from ..constants import BAR_KNEE_CLEARANCE_M, BENCH_BAR_PATH_WEIGHT, TV_RATE_WEIGHT_RATIO
from ..models import BodyModel
from .result import CancelledError, OptimizationResult, ProgressReport
from .tuning import (
    BALANCE_BARRIER_WEIGHT,
    BALANCE_CENTER_WEIGHT,
    DEFAULT_ENDPOINT_WEIGHT,
    DEFAULT_JERK_WEIGHT,
    DEFAULT_N_STARTS,
    DEFAULT_TORQUE_RATE_WEIGHT,
    MAX_ITER_PER_START,
    PERTURBATION_SCALE,
    STALL_THRESHOLD,
    STALL_WINDOW,
)

logger = logging.getLogger(__name__)


class TrajectoryOptimizer:
    """Parallel multi-start trajectory optimiser.

    Preconditions:
        q_start, q_end are length-3 arrays.
        q_bounds is (3, 2).
        n_waypoints >= 4.
        dynamics implements PhysicsBackend.

    The optimizer enforces COM within the middle 60% of the foot
    (body.inner_heel to body.inner_toe) using a steep barrier penalty.
    Multiple starts with perturbed initial guesses run in parallel
    threads.  The best solution is returned.
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
        self.body = body
        self.dynamics = dynamics
        self.exercise_type = exercise_type
        self.bar_mass = bar_mass
        self.q_start = q_start
        self.q_end = q_end
        self.q_bounds = q_bounds
        self.q_via = q_via
        self.duration = duration
        self.n_waypoints = n_waypoints
        self.n_eval = n_eval
        self.progress_cb = progress_cb
        self.cancel_event = cancel_event or threading.Event()
        self.n_starts = n_starts

        # Smoothing weights (scaled by user knob)
        self.jerk_weight = jerk_weight * smoothness
        self.torque_rate_weight = torque_rate_weight * smoothness
        self.endpoint_weight = endpoint_weight * smoothness

        # Balance barrier (tighter inner BOS)
        self.inner_heel = body.inner_heel
        self.inner_toe = body.inner_toe
        self.inner_center = body.inner_center
        self.balance_barrier_weight = BALANCE_BARRIER_WEIGHT
        self.balance_center_weight = BALANCE_CENTER_WEIGHT

        # Time grids
        self._setup_time_grids()
        self.dt = duration / (n_eval - 1)

        # Endpoint damping pre-computation
        self._n_damp = max(2, n_eval // 8)
        self._damp_weights = 1.0 - np.arange(self._n_damp) / self._n_damp

        # Mutable diagnostics (only used by the primary start)
        self._iter = 0
        self._cost_history: list[float] = []
        self._best_cost = float("inf")
        self._start_time = 0.0
        self._progress_lock = threading.Lock()

    def _setup_time_grids(self) -> None:
        n_ctrl = self.n_waypoints + 2
        if self.q_via is not None:
            n_ctrl += 1
        self.t_ctrl = np.linspace(0, self.duration, n_ctrl)
        self.t_eval = np.linspace(0, self.duration, self.n_eval)

    # -- spline construction ------------------------------------

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

    # ==========================================================
    # Cost sub-terms (each independently testable)
    # ==========================================================

    def _torque_cost(self, torques: NDArray) -> float:
        """Integral of squared joint torques."""
        return float(np.sum(torques**2) * self.dt)

    def _jerk_cost(self, qddd: NDArray) -> float:
        """Smoothness: integral of squared jerk."""
        return self.jerk_weight * float(np.sum(qddd**2)) * self.dt

    def _torque_rate_cost(self, torques: NDArray) -> float:
        """Penalise rapid torque changes (dtau/dt).

        Uses both L2 (squared differences) and total-variation (L1)
        regularization for robust smoothing without over-damping.
        """
        dtau = np.diff(torques, axis=0) / self.dt
        l2_cost = float(np.sum(dtau**2)) * self.dt
        tv_cost = float(np.sum(np.abs(dtau))) * self.dt * TV_RATE_WEIGHT_RATIO
        return self.torque_rate_weight * (l2_cost + tv_cost)

    def _endpoint_damping_cost(self, qd: NDArray, qdd: NDArray) -> float:
        """Extra penalty on motion near trajectory endpoints."""
        nd = self._n_damp
        w = self._damp_weights

        vel_start = np.sum(qd[:nd] ** 2, axis=1)
        vel_end = np.sum(qd[-nd:] ** 2, axis=1)
        acc_start = np.sum(qdd[:nd] ** 2, axis=1)
        acc_end = np.sum(qdd[-nd:] ** 2, axis=1)

        w_end = w[::-1]

        cost = (
            np.dot(w, vel_start)
            + np.dot(w_end, vel_end)
            + 0.1 * np.dot(w, acc_start)
            + 0.1 * np.dot(w_end, acc_end)
        )
        return self.endpoint_weight * float(cost) * self.dt

    def _balance_cost(self, com_x: NDArray) -> float:
        """Soft centering preference (hard bounds enforced via SLSQP constraints)."""
        center = self.inner_center
        return self.balance_center_weight * float(np.sum((com_x - center) ** 2)) * self.dt

    def _com_constraint_values(self, x: NDArray) -> NDArray:
        """Return COM constraint violation for SLSQP.

        Returns array of length 2*n_eval:
            [0..n_eval-1]   = com_x - inner_heel  (must be >= 0)
            [n_eval..2*n-1] = inner_toe - com_x    (must be >= 0)
        """
        splines = self.build_splines(x)
        q = np.column_stack([s(self.t_eval) for s in splines])
        com_x = self.dynamics.com_x_batch(q, self.exercise_type, self.bar_mass)
        lower = com_x - self.inner_heel
        upper = self.inner_toe - com_x
        return np.concatenate([lower, upper])

    def _bar_knee_clearance(self, x: NDArray) -> NDArray:
        """Bar must stay in front of the knees during pulling exercises.

        Returns array of length n_eval:
            bar_x - knee_x + margin  (must be >= 0)
        Active for deadlift, clean, and snatch exercises.
        """
        splines = self.build_splines(x)
        q = np.column_stack([s(self.t_eval) for s in splines])
        L = self.body.L
        knee_x = L[0] * np.sin(q[:, 0])
        hip_x = knee_x + L[1] * np.sin(q[:, 1])
        shoulder_x = hip_x + L[2] * np.sin(q[:, 2])
        # Approximation: bar_x = shoulder_x assumes the bar hangs directly
        # below the shoulder in the sagittal plane.  In reality the arms
        # swing slightly forward, so the true bar x-position is offset by
        # a small amount that depends on arm angle.  This simplification
        # is acceptable because the offset is small relative to knee-bar
        # clearance and does not materially affect the constraint.
        bar_x = shoulder_x
        return bar_x - knee_x + BAR_KNEE_CLEARANCE_M

    # ==========================================================
    # Pure cost computation (thread-safe, no side effects)
    # ==========================================================

    def _compute_cost(self, x: NDArray) -> float:
        """Compute total cost without mutating instance state.

        This is the function called by parallel worker threads.
        All reads from self are to immutable configuration set
        during __init__.
        """
        if self.cancel_event.is_set():
            return float("inf")

        splines = self.build_splines(x)
        q, qd, qdd, qddd = self.eval_trajectory(splines)
        torques = self.dynamics.inverse_dynamics_batch(q, qd, qdd)

        total = (
            self._torque_cost(torques)
            + self._jerk_cost(qddd)
            + self._torque_rate_cost(torques)
            + self._endpoint_damping_cost(qd, qdd)
        )

        if self.exercise_type == "bench_press":
            # Bar-path verticality: penalise horizontal drift from shoulder joint.
            # In bench FK, origin=shoulder, segments are upper_arm→forearm→hand.
            # hand_x = sum of L[i]*sin(q[i]) — should stay near zero (bar above shoulder).
            L = self.dynamics.L  # type: ignore[attr-defined]
            hand_x = L[0] * np.sin(q[:, 0]) + L[1] * np.sin(q[:, 1]) + L[2] * np.sin(q[:, 2])
            total += BENCH_BAR_PATH_WEIGHT * float(np.sum(hand_x**2)) * self.dt
        else:
            com_x = self.dynamics.com_x_batch(q, self.exercise_type, self.bar_mass)
            total += self._balance_cost(com_x)

        return total

    # ==========================================================
    # Legacy cost() for single-thread compat / progress tracking
    # ==========================================================

    def cost(self, x: NDArray) -> float:
        """Total cost with progress tracking (single-thread path)."""
        total = self._compute_cost(x)

        self._iter += 1
        self._cost_history.append(total)
        self._best_cost = min(self._best_cost, total)

        if self.progress_cb and self._iter % 20 == 0:
            self._emit_progress(total)

        return total

    def _emit_progress(self, current_cost: float) -> None:
        elapsed = time.monotonic() - self._start_time
        if len(self._cost_history) >= 40:
            prev = self._cost_history[-40]
            improvement = (prev - current_cost) / abs(prev) * 100 if prev != 0 else 0.0
        else:
            improvement = 0.0

        is_stalled, stall_reason = self._detect_stall()
        recent_history = self._cost_history[-200:]

        report = ProgressReport(
            iteration=self._iter,
            cost=current_cost,
            best_cost=self._best_cost,
            improvement_pct=improvement,
            elapsed_s=elapsed,
            cost_history=recent_history,
            is_stalled=is_stalled,
            stall_reason=stall_reason,
        )
        if self.progress_cb:
            self.progress_cb(report)

    def _detect_stall(self) -> tuple[bool, str]:
        history = self._cost_history
        if len(history) < STALL_WINDOW:
            return False, ""
        recent = history[-STALL_WINDOW:]
        old_cost = recent[0]
        new_cost = recent[-1]
        if old_cost == 0:
            return False, ""
        rel_improvement = abs(old_cost - new_cost) / abs(old_cost)
        if rel_improvement < STALL_THRESHOLD:
            return True, (
                f"Cost changed < {STALL_THRESHOLD * 100:.2f}% "
                f"over last {STALL_WINDOW} evals "
                f"({old_cost:.1f} -> {new_cost:.1f})"
            )
        return False, ""

    # ==========================================================
    # Initial guess generation
    # ==========================================================

    def _initial_guess(self) -> NDArray:
        """Linear interpolation between start/end (or start/via/end)."""
        wp = np.zeros((self.n_waypoints, self.n_dof))
        if self.q_via is not None:
            n_half = self.n_waypoints // 2
            for j in range(self.n_dof):
                wp[:n_half, j] = np.linspace(self.q_start[j], self.q_via[j], n_half + 2)[1:-1]
                wp[n_half:, j] = np.linspace(
                    self.q_via[j],
                    self.q_end[j],
                    self.n_waypoints - n_half + 2,
                )[1:-1]
        else:
            for j in range(self.n_dof):
                wp[:, j] = np.linspace(self.q_start[j], self.q_end[j], self.n_waypoints + 2)[1:-1]
        return wp

    def _perturbed_guess(self, seed: int) -> NDArray:
        """Generate a perturbed initial guess for multi-start.

        Seed 0 returns the unperturbed baseline.  Other seeds add
        smooth random perturbations scaled to PERTURBATION_SCALE of
        the joint range.
        """
        wp = self._initial_guess()
        if seed == 0:
            return wp

        rng = np.random.default_rng(seed * 42 + 7)
        joint_range = self.q_bounds[:, 1] - self.q_bounds[:, 0]
        noise = rng.normal(0, PERTURBATION_SCALE, wp.shape) * joint_range
        wp_perturbed = wp + noise

        # Clip to joint bounds
        for j in range(self.n_dof):
            wp_perturbed[:, j] = np.clip(
                wp_perturbed[:, j], self.q_bounds[j, 0], self.q_bounds[j, 1]
            )
        return wp_perturbed

    def _build_bounds(self) -> list[tuple[float, float]]:
        bounds: list[tuple[float, float]] = []
        for _ in range(self.n_waypoints):
            for j in range(self.n_dof):
                bounds.append((self.q_bounds[j, 0], self.q_bounds[j, 1]))
        return bounds

    # ==========================================================
    # Single-start optimisation
    # ==========================================================

    def _cancel_callback(self, _xk: NDArray) -> None:
        """SLSQP iteration callback — raises to abort immediately."""
        if self.cancel_event.is_set():
            raise CancelledError("Optimization cancelled by user")

    def _joint_limit_constraint_values(self, x: NDArray) -> NDArray:
        """Return joint limit constraint violation for SLSQP.

        Ensures all evaluated trajectory points stay within joint limits,
        preventing spline overshoot between control points from violating
        the physical bounds.
        """
        splines = self.build_splines(x)
        q = np.column_stack([s(self.t_eval) for s in splines])

        # lower shape: (n_eval, n_dof)
        lower = q - self.q_bounds[:, 0]
        upper = self.q_bounds[:, 1] - q

        return np.concatenate([lower.flatten(), upper.flatten()])

    def _build_constraints(self) -> list[dict]:
        """Build SLSQP inequality constraints.

        Bench press has no COM/balance constraints because the lifter
        is lying on a bench, not standing.
        """
        constraints = [
            {"type": "ineq", "fun": self._joint_limit_constraint_values},
        ]

        if self.exercise_type != "bench_press":
            constraints.append({"type": "ineq", "fun": self._com_constraint_values})

            pulling_exercises = {"deadlift", "clean", "snatch"}
            if self.exercise_type in pulling_exercises:
                constraints.append(
                    {"type": "ineq", "fun": self._bar_knee_clearance},
                )
        return constraints

    def _run_single_start(self, seed: int) -> tuple[object, int] | None:
        """Run one SLSQP solve with a perturbed initial guess.

        Returns (scipy result, eval_count) or None if cancelled.
        """
        if self.cancel_event.is_set():
            return None

        wp0 = self._perturbed_guess(seed)
        bounds = self._build_bounds()
        constraints = self._build_constraints()
        eval_count = [0]

        def cost_fn(x: NDArray) -> float:
            if self.cancel_event.is_set():
                raise CancelledError("cancelled")
            eval_count[0] += 1
            return self._compute_cost(x)

        try:
            res = minimize(
                cost_fn,
                wp0.flatten(),
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                callback=self._cancel_callback,
                options={"maxiter": MAX_ITER_PER_START, "ftol": 1e-6, "disp": False},
            )
        except CancelledError:
            return None

        if self.cancel_event.is_set():
            return None

        return res, eval_count[0]

    # ==========================================================
    # Main optimisation driver (parallel multi-start)
    # ==========================================================

    def optimize(self) -> OptimizationResult:
        """Run parallel multi-start SLSQP and return best result.

        Uses SLSQP with hard COM inequality constraints to guarantee
        the COM stays within the middle 60% of the foot at all times.
        Multiple starts run concurrently; cancellation is immediate
        via callback + exception.

        Raises CancelledError if cancel_event is set.
        """
        self._iter = 0
        self._cost_history = []
        self._best_cost = float("inf")
        self._start_time = time.monotonic()

        n_workers = min(self.n_starts, os.cpu_count() or 4)

        logger.info(
            "Starting optimisation: exercise=%s, n_starts=%d, n_workers=%d, n_wp=%d",
            self.exercise_type,
            self.n_starts,
            n_workers,
            self.n_waypoints,
        )

        results: list[tuple[object, int]] = []

        if n_workers <= 1 or self.n_starts <= 1:
            out = self._run_single_start_with_progress()
            if self.cancel_event.is_set():
                raise CancelledError("Optimization cancelled by user")
            elapsed = time.monotonic() - self._start_time
            return self._package_results(out, elapsed)
        else:
            with ThreadPoolExecutor(max_workers=n_workers) as pool:
                pending: set[Future] = {
                    pool.submit(self._run_single_start, seed) for seed in range(self.n_starts)
                }
                total_evals = [0]

                while pending:
                    if self.cancel_event.is_set():
                        for f in pending:
                            f.cancel()
                        raise CancelledError("Optimization cancelled by user")

                    done, pending = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)

                    for future in done:
                        result = future.result()
                        if result is not None:
                            results.append(result)
                            res, n_evals = result
                            total_evals[0] += n_evals

                            with self._progress_lock:
                                self._iter = total_evals[0]
                                cost_val = float(res.fun)
                                self._cost_history.append(cost_val)
                                self._best_cost = min(self._best_cost, cost_val)
                                if self.progress_cb:
                                    self._emit_progress(cost_val)

        if not results:
            raise CancelledError("All optimization starts were cancelled")

        best_res, _ = min(results, key=lambda r: float(r[0].fun))  # type: ignore[attr-defined]
        elapsed = time.monotonic() - self._start_time
        total_evals_sum = sum(n for _, n in results)

        logger.info(
            "Optimisation finished: best_cost=%.2f, total_evals=%d, n_starts=%d, time=%.1fs",
            best_res.fun,  # type: ignore[attr-defined]
            total_evals_sum,
            len(results),
            elapsed,
        )

        return self._package_results(best_res, elapsed, total_evals_sum)

    def _run_single_start_with_progress(self) -> object:
        """Single-start path with progress tracking."""
        self._iter = 0
        self._cost_history = []
        self._best_cost = float("inf")

        wp0 = self._initial_guess()
        bounds = self._build_bounds()
        constraints = self._build_constraints()

        try:
            res = minimize(
                self.cost,
                wp0.flatten(),
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                callback=self._cancel_callback,
                options={"maxiter": MAX_ITER_PER_START * 2, "ftol": 1e-6, "disp": False},
            )
        except CancelledError:
            raise

        return res

    # ==========================================================
    # Result packaging
    # ==========================================================

    def _package_results(
        self, res: object, elapsed: float = 0.0, n_evals: int = 0
    ) -> OptimizationResult:
        splines = self.build_splines(res.x)  # type: ignore[attr-defined]
        q, qd, qdd, _ = self.eval_trajectory(splines)

        torques = self.dynamics.inverse_dynamics_batch(q, qd, qdd)
        power = torques * qd

        # Batch-vectorized COM x-coordinate and per-row COM y / bar trajectories
        n_pts = q.shape[0]
        com_x = self.dynamics.com_x_batch(q, self.exercise_type, self.bar_mass)
        com_traj = np.empty((n_pts, 2))
        bar_traj = np.empty((n_pts, 2))
        for n in range(n_pts):
            com_full = self.dynamics.com_position(q[n], self.exercise_type, self.bar_mass)
            com_traj[n, 0] = com_x[n]
            com_traj[n, 1] = com_full[1]
            bar_traj[n] = self.dynamics.bar_position(q[n], self.exercise_type)

        com_h_range = (np.max(com_x) - np.min(com_x)) * 100.0

        # Success: cost is finite AND COM stays within inner BOS (the hard constraint)
        # Bench press: no COM constraint (lifter is on a bench)
        cost_val = float(res.fun)  # type: ignore[attr-defined]
        cost_finite = cost_val < float("inf") and not np.isnan(cost_val)

        if self.exercise_type == "bench_press":
            com_in_bounds = True
        else:
            com_in_bounds = bool(
                np.all(com_x >= self.inner_heel - 0.005) and np.all(com_x <= self.inner_toe + 0.005)
            )
            if cost_finite and not com_in_bounds:
                logger.warning(
                    "Solution found but COM violated inner BOS: min=%.4f max=%.4f "
                    "(bounds: [%.4f, %.4f])",
                    com_x.min(),
                    com_x.max(),
                    self.inner_heel,
                    self.inner_toe,
                )

        success = cost_finite and com_in_bounds

        # Warn and record joint limit violations from spline overshoot
        n_joint_limit_violations = 0
        if self.q_bounds is not None:
            _lower = self.q_bounds[:, 0]
            _upper = self.q_bounds[:, 1]
            n_joint_limit_violations = int(np.sum((q < _lower) | (q > _upper)))
            if n_joint_limit_violations > 0:
                logger.warning(
                    "Trajectory has %d point(s) violating joint limits "
                    "(spline overshoot between control points).",
                    n_joint_limit_violations,
                )

        return OptimizationResult(
            t=self.t_eval,
            q=q,
            qd=qd,
            qdd=qdd,
            torques=torques,
            power=power,
            com=com_traj,
            bar=bar_traj,
            success=success,
            cost=cost_val,
            com_horizontal_range_cm=com_h_range,
            elapsed_s=elapsed,
            n_evals=n_evals or self._iter,
            n_joint_limit_violations=n_joint_limit_violations,
        )
