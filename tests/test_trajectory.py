"""Tests for the trajectory optimiser.

Covers: spline construction, cost sub-terms, via-point support,
optimisation convergence, COM constraint enforcement, parallel
multi-start, cancellation, stall detection, and solution caching.
"""

from __future__ import annotations

import threading

import numpy as np
import pytest

from movement_optimizer.models import (
    BodyModel,
    make_full_squat_config,
    make_squat_config,
)
from movement_optimizer.trajectory import (
    CancelledError,
    OptimizationResult,
    ProgressReport,
    SolutionCache,
    TrajectoryOptimizer,
)


@pytest.fixture()
def squat_optimizer():
    body = BodyModel(75.0, 1.75)
    dyn, qs, qe, qb = make_squat_config(body, 60.0)
    opt = TrajectoryOptimizer(
        body, dyn, "squat", 60.0, qs, qe, qb,
        duration=2.0, n_waypoints=6, n_eval=20, n_starts=1,
    )
    return opt, body, dyn, qs, qe


@pytest.fixture()
def full_squat_optimizer():
    body = BodyModel(75.0, 1.75)
    dyn, qs, qe, qb, q_via = make_full_squat_config(body, 60.0)
    opt = TrajectoryOptimizer(
        body, dyn, "full_squat", 60.0, qs, qe, qb,
        q_via=q_via, duration=4.0, n_waypoints=8, n_eval=20, n_starts=1,
    )
    return opt, body, dyn


# ==============================================================
# Construction & Preconditions
# ==============================================================


class TestConstruction:
    def test_too_few_waypoints_raises(self) -> None:
        body = BodyModel(75.0, 1.75)
        dyn, qs, qe, qb = make_squat_config(body, 60.0)
        with pytest.raises(AssertionError, match="waypoints"):
            TrajectoryOptimizer(
                body, dyn, "squat", 60.0, qs, qe, qb, n_waypoints=2,
            )

    def test_bad_bounds_shape_raises(self) -> None:
        body = BodyModel(75.0, 1.75)
        dyn, qs, qe, _ = make_squat_config(body, 60.0)
        bad_bounds = np.zeros((2, 2))
        with pytest.raises(AssertionError, match="q_bounds"):
            TrajectoryOptimizer(
                body, dyn, "squat", 60.0, qs, qe, bad_bounds,
            )

    def test_inner_bos_stored(self, squat_optimizer) -> None:
        """Optimizer should store inner BOS from body model."""
        opt, body, _, _, _ = squat_optimizer
        assert opt.inner_heel == body.inner_heel
        assert opt.inner_toe == body.inner_toe


# ==============================================================
# Spline & Trajectory
# ==============================================================


class TestSplines:
    def test_spline_endpoints(self, squat_optimizer) -> None:
        opt, _, _, qs, qe = squat_optimizer
        wp = opt._initial_guess()
        splines = opt.build_splines(wp.flatten())
        q, _, _, _ = opt.eval_trajectory(splines)
        np.testing.assert_allclose(q[0], qs, atol=1e-6)
        np.testing.assert_allclose(q[-1], qe, atol=1e-6)

    def test_clamped_boundary_velocities(self, squat_optimizer) -> None:
        opt, _, _, _, _ = squat_optimizer
        wp = opt._initial_guess()
        splines = opt.build_splines(wp.flatten())
        _, qd, _, _ = opt.eval_trajectory(splines)
        np.testing.assert_allclose(qd[0], 0, atol=0.1)
        np.testing.assert_allclose(qd[-1], 0, atol=0.1)

    def test_via_point_trajectory(self, full_squat_optimizer) -> None:
        opt, _, _ = full_squat_optimizer
        wp = opt._initial_guess()
        splines = opt.build_splines(wp.flatten())
        q, _, _, _ = opt.eval_trajectory(splines)
        mid = len(q) // 2
        assert q[mid, 1] < np.radians(-60), "Thigh should flex significantly at midpoint"


# ==============================================================
# Cost sub-terms
# ==============================================================


class TestCostTerms:
    def test_torque_cost_positive(self, squat_optimizer) -> None:
        opt, _, dyn, _, _ = squat_optimizer
        wp = opt._initial_guess()
        splines = opt.build_splines(wp.flatten())
        q, qd, qdd, _ = opt.eval_trajectory(splines)
        torques = dyn.inverse_dynamics_batch(q, qd, qdd)
        cost = opt._torque_cost(torques)
        assert cost > 0

    def test_jerk_cost_positive(self, squat_optimizer) -> None:
        opt, _, _, _, _ = squat_optimizer
        wp = opt._initial_guess()
        splines = opt.build_splines(wp.flatten())
        _, _, _, qddd = opt.eval_trajectory(splines)
        cost = opt._jerk_cost(qddd)
        assert cost > 0

    def test_torque_rate_cost_positive(self, squat_optimizer) -> None:
        opt, _, dyn, _, _ = squat_optimizer
        wp = opt._initial_guess()
        splines = opt.build_splines(wp.flatten())
        q, qd, qdd, _ = opt.eval_trajectory(splines)
        torques = dyn.inverse_dynamics_batch(q, qd, qdd)
        cost = opt._torque_rate_cost(torques)
        assert cost > 0

    def test_endpoint_damping_zero_at_rest(self) -> None:
        body = BodyModel(75.0, 1.75)
        dyn, qs, qe, qb = make_squat_config(body, 60.0)
        opt = TrajectoryOptimizer(
            body, dyn, "squat", 60.0, qs, qe, qb,
            n_waypoints=6, n_eval=20, n_starts=1,
        )
        qd = np.zeros((20, 3))
        qdd = np.zeros((20, 3))
        cost = opt._endpoint_damping_cost(qd, qdd)
        assert cost == 0.0

    def test_balance_cost_inside_is_centering_only(self, squat_optimizer) -> None:
        """COM inside inner bounds should incur only centering cost (no barrier)."""
        opt, body, _, _, _ = squat_optimizer
        center = body.inner_center
        com_x = np.full(20, center)
        cost = opt._balance_cost(com_x)
        # Should be zero since COM == center
        assert cost < 1e-10

    def test_balance_cost_outside_is_very_high(self, squat_optimizer) -> None:
        """COM outside inner bounds should incur very high barrier cost."""
        opt, body, _, _, _ = squat_optimizer
        # Place COM well outside inner bounds
        com_x = np.full(20, body.heel_x - 0.05)
        cost_outside = opt._balance_cost(com_x)
        # Compare to COM at center
        com_x_center = np.full(20, body.inner_center)
        cost_center = opt._balance_cost(com_x_center)
        assert cost_outside > cost_center * 100

    def test_total_cost_is_sum(self, squat_optimizer) -> None:
        opt, _, dyn, _, _ = squat_optimizer
        wp = opt._initial_guess()
        x = wp.flatten()
        splines = opt.build_splines(x)
        q, qd, qdd, qddd = opt.eval_trajectory(splines)

        torques = dyn.inverse_dynamics_batch(q, qd, qdd)
        com_x = dyn.com_x_batch(q, "squat", 60.0)

        total = (
            opt._torque_cost(torques)
            + opt._jerk_cost(qddd)
            + opt._torque_rate_cost(torques)
            + opt._endpoint_damping_cost(qd, qdd)
            + opt._balance_cost(com_x)
        )
        computed = opt._compute_cost(x)
        np.testing.assert_allclose(computed, total, rtol=1e-10)


# ==============================================================
# Optimisation
# ==============================================================


class TestOptimization:
    def test_optimize_returns_result(self, squat_optimizer) -> None:
        opt, _, _, _, _ = squat_optimizer
        result = opt.optimize()
        assert isinstance(result, OptimizationResult)

    def test_result_shapes(self, squat_optimizer) -> None:
        opt, _, _, _, _ = squat_optimizer
        result = opt.optimize()
        n = opt.n_eval
        assert result.t.shape == (n,)
        assert result.q.shape == (n, 3)
        assert result.qd.shape == (n, 3)
        assert result.torques.shape == (n, 3)
        assert result.power.shape == (n, 3)
        assert result.com.shape == (n, 2)
        assert result.bar.shape == (n, 2)

    def test_cost_decreases(self, squat_optimizer) -> None:
        opt, _, _, _, _ = squat_optimizer
        wp0 = opt._initial_guess()
        initial_cost = opt._compute_cost(wp0.flatten())
        result = opt.optimize()
        assert result.cost < initial_cost

    def test_horizontal_range_positive(self, squat_optimizer) -> None:
        opt, _, _, _, _ = squat_optimizer
        result = opt.optimize()
        assert result.com_horizontal_range_cm >= 0

    def test_full_squat_reaches_depth(self, full_squat_optimizer) -> None:
        opt, _, _ = full_squat_optimizer
        result = opt.optimize()
        min_thigh_angle = np.min(result.q[:, 1])
        assert min_thigh_angle < np.radians(-45)

    def test_optimization_succeeds(self) -> None:
        """Optimization with production-size config should succeed."""
        body = BodyModel(75.0, 1.75)
        dyn, qs, qe, qb = make_squat_config(body, 60.0)
        opt = TrajectoryOptimizer(
            body, dyn, "squat", 60.0, qs, qe, qb,
            duration=2.0, n_waypoints=12, n_eval=40, n_starts=1,
        )
        result = opt.optimize()
        assert result.cost < float("inf")
        assert result.success

    def test_com_ends_near_bos(self) -> None:
        """At the end of the squat (standing), COM should be near the foot."""
        body = BodyModel(75.0, 1.75)
        dyn, qs, qe, qb = make_squat_config(body, 60.0)
        opt = TrajectoryOptimizer(
            body, dyn, "squat", 60.0, qs, qe, qb,
            duration=2.0, n_waypoints=12, n_eval=40, n_starts=2,
        )
        result = opt.optimize()
        # At standing (end of ascent), COM should be near the ankle
        com_x_end = result.com[-1, 0]
        assert abs(com_x_end) < 0.05, (
            f"COM at standing too far from ankle: {com_x_end:.4f}"
        )
        # COM should move forward (toward foot) as the squat ascends
        com_x_start = result.com[0, 0]
        assert com_x_end > com_x_start, "COM should move forward during ascent"


# ==============================================================
# Multi-start
# ==============================================================


class TestMultiStart:
    def test_perturbed_guess_seed_0_is_baseline(self, squat_optimizer) -> None:
        opt, _, _, _, _ = squat_optimizer
        baseline = opt._initial_guess()
        perturbed = opt._perturbed_guess(0)
        np.testing.assert_array_equal(baseline, perturbed)

    def test_perturbed_guess_different_seeds_differ(self, squat_optimizer) -> None:
        opt, _, _, _, _ = squat_optimizer
        g1 = opt._perturbed_guess(1)
        g2 = opt._perturbed_guess(2)
        assert not np.allclose(g1, g2)

    def test_perturbed_guess_within_bounds(self, squat_optimizer) -> None:
        opt, _, _, _, _ = squat_optimizer
        for seed in range(10):
            wp = opt._perturbed_guess(seed)
            for j in range(3):
                assert np.all(wp[:, j] >= opt.q_bounds[j, 0])
                assert np.all(wp[:, j] <= opt.q_bounds[j, 1])

    def test_parallel_multistart_runs(self) -> None:
        """Multi-start with n_starts > 1 should run and return a result."""
        body = BodyModel(75.0, 1.75)
        dyn, qs, qe, qb = make_squat_config(body, 60.0)
        opt = TrajectoryOptimizer(
            body, dyn, "squat", 60.0, qs, qe, qb,
            duration=2.0, n_waypoints=6, n_eval=20, n_starts=3,
        )
        result = opt.optimize()
        assert isinstance(result, OptimizationResult)
        assert result.cost < float("inf")


# ==============================================================
# Cancellation
# ==============================================================


class TestCancellation:
    def test_cancel_returns_inf(self, squat_optimizer) -> None:
        opt, _, _, _, _ = squat_optimizer
        opt.cancel_event.set()
        wp = opt._initial_guess()
        result = opt._compute_cost(wp.flatten())
        assert result == float("inf")

    def test_cancel_during_optimize(self) -> None:
        body = BodyModel(75.0, 1.75)
        dyn, qs, qe, qb = make_squat_config(body, 60.0)
        cancel = threading.Event()
        opt = TrajectoryOptimizer(
            body, dyn, "squat", 60.0, qs, qe, qb,
            n_waypoints=6, n_eval=20, n_starts=1,
            cancel_event=cancel,
        )
        call_count = [0]

        def cancel_after_3(report: ProgressReport) -> None:
            call_count[0] += 1
            if call_count[0] >= 2:
                cancel.set()

        opt.progress_cb = cancel_after_3
        with pytest.raises(CancelledError):
            opt.optimize()

    def test_cancel_event_default(self, squat_optimizer) -> None:
        opt, _, _, _, _ = squat_optimizer
        assert not opt.cancel_event.is_set()


# ==============================================================
# Progress Reporting & Stall Detection
# ==============================================================


class TestProgressReporting:
    def test_progress_callback_receives_report(self) -> None:
        body = BodyModel(75.0, 1.75)
        dyn, qs, qe, qb = make_squat_config(body, 60.0)
        reports: list[ProgressReport] = []
        opt = TrajectoryOptimizer(
            body, dyn, "squat", 60.0, qs, qe, qb,
            n_waypoints=6, n_eval=20, n_starts=1,
            progress_cb=lambda r: reports.append(r),
        )
        opt.optimize()
        assert len(reports) > 0
        assert isinstance(reports[0], ProgressReport)

    def test_stall_detection_flat_cost(self, squat_optimizer) -> None:
        opt, _, _, _, _ = squat_optimizer
        opt._cost_history = [100.0] * 100
        is_stalled, reason = opt._detect_stall()
        assert is_stalled

    def test_stall_detection_improving(self, squat_optimizer) -> None:
        opt, _, _, _, _ = squat_optimizer
        opt._cost_history = list(np.linspace(1000, 100, 100))
        is_stalled, _ = opt._detect_stall()
        assert not is_stalled


# ==============================================================
# Solution Cache
# ==============================================================


class TestSolutionCache:
    def test_cache_miss_returns_none(self) -> None:
        cache = SolutionCache()
        result = cache.get("squat", 75.0, 1.75, {"lower_leg": 1.0}, 60.0, 2.0, 1.0)
        assert result is None

    def test_cache_hit_returns_result(self) -> None:
        cache = SolutionCache()
        n = 10
        dummy = OptimizationResult(
            t=np.zeros(n), q=np.zeros((n, 3)), qd=np.zeros((n, 3)),
            qdd=np.zeros((n, 3)), torques=np.zeros((n, 3)),
            power=np.zeros((n, 3)), com=np.zeros((n, 2)),
            bar=np.zeros((n, 2)), success=True, cost=42.0,
            com_horizontal_range_cm=1.5,
        )
        mults = {"lower_leg": 1.0, "upper_leg": 1.0, "torso": 1.0}
        cache.put("squat", 75.0, 1.75, mults, 60.0, 2.0, 1.0, dummy)
        hit = cache.get("squat", 75.0, 1.75, mults, 60.0, 2.0, 1.0)
        assert hit is not None
        assert hit.cost == 42.0

    def test_cache_clear(self) -> None:
        cache = SolutionCache()
        n = 10
        dummy = OptimizationResult(
            t=np.zeros(n), q=np.zeros((n, 3)), qd=np.zeros((n, 3)),
            qdd=np.zeros((n, 3)), torques=np.zeros((n, 3)),
            power=np.zeros((n, 3)), com=np.zeros((n, 2)),
            bar=np.zeros((n, 2)), success=True, cost=42.0,
            com_horizontal_range_cm=1.5,
        )
        mults = {"lower_leg": 1.0, "upper_leg": 1.0, "torso": 1.0}
        cache.put("squat", 75.0, 1.75, mults, 60.0, 2.0, 1.0, dummy)
        cache.clear()
        assert cache.get("squat", 75.0, 1.75, mults, 60.0, 2.0, 1.0) is None
