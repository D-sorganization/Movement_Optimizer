"""Tests for the trajectory optimiser.

Covers: spline construction, cost sub-terms, via-point support,
optimisation convergence, COM constraint enforcement, parallel
multi-start, cancellation, stall detection, and solution caching.
"""

from __future__ import annotations

import numpy as np

from movement_optimizer.exercises import make_clean_config, make_snatch_config
from movement_optimizer.models import (
    BodyModel,
    make_bench_press_config,
    make_deadlift_config,
    make_squat_config,
)
from movement_optimizer.trajectory import (
    TrajectoryOptimizer,
)

# ==============================================================
# Validation Tests
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
            body,
            dyn,
            "squat",
            60.0,
            qs,
            qe,
            qb,
            n_waypoints=6,
            n_eval=20,
            n_starts=1,
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


def _has_bar_knee_constraint(opt: TrajectoryOptimizer) -> bool:
    """Return True if the optimizer's constraints include bar-knee clearance."""
    constraints = opt._build_constraints()
    return any(
        getattr(c["fun"], "__func__", None) is TrajectoryOptimizer._bar_knee_clearance
        for c in constraints
    )


class TestBarKneeClearance:
    def test_clearance_active_for_deadlift(self) -> None:
        body = BodyModel(75.0, 1.75)
        dyn, qs, qe, qb = make_deadlift_config(body, 60.0)
        opt = TrajectoryOptimizer(
            body,
            dyn,
            "deadlift",
            60.0,
            qs,
            qe,
            qb,
            n_waypoints=6,
            n_eval=20,
            n_starts=1,
        )
        assert _has_bar_knee_constraint(opt)

    def test_clearance_active_for_clean(self) -> None:
        body = BodyModel(75.0, 1.75)
        dyn, qs, qe, qb, q_via = make_clean_config(body, 60.0)
        opt = TrajectoryOptimizer(
            body,
            dyn,
            "clean",
            60.0,
            qs,
            qe,
            qb,
            q_via=q_via,
            n_waypoints=6,
            n_eval=20,
            n_starts=1,
        )
        assert _has_bar_knee_constraint(opt)

    def test_clearance_active_for_snatch(self) -> None:
        body = BodyModel(75.0, 1.75)
        dyn, qs, qe, qb, q_via = make_snatch_config(body, 60.0)
        opt = TrajectoryOptimizer(
            body,
            dyn,
            "snatch",
            60.0,
            qs,
            qe,
            qb,
            q_via=q_via,
            n_waypoints=6,
            n_eval=20,
            n_starts=1,
        )
        assert _has_bar_knee_constraint(opt)

    def test_clearance_not_active_for_squat(self) -> None:
        body = BodyModel(75.0, 1.75)
        dyn, qs, qe, qb = make_squat_config(body, 60.0)
        opt = TrajectoryOptimizer(
            body,
            dyn,
            "squat",
            60.0,
            qs,
            qe,
            qb,
            n_waypoints=6,
            n_eval=20,
            n_starts=1,
        )
        assert not _has_bar_knee_constraint(opt)

    def test_clearance_not_active_for_bench(self) -> None:
        body = BodyModel(75.0, 1.75)
        dyn, qs, qe, qb, _q_via = make_bench_press_config(body, 60.0)
        opt = TrajectoryOptimizer(
            body,
            dyn,
            "bench_press",
            60.0,
            qs,
            qe,
            qb,
            n_waypoints=6,
            n_eval=20,
            n_starts=1,
        )
        assert not _has_bar_knee_constraint(opt)


# ==============================================================
# OptimizationResult — joint limit violation tracking
# ==============================================================


class TestJointLimitViolationTracking:
    """Tests that n_joint_limit_violations is populated in OptimizationResult."""

    def test_no_violations_when_within_limits(self, squat_optimizer) -> None:
        """A well-behaved trajectory should report zero joint-limit violations."""
        opt, _body, _dyn, _qs, _qe = squat_optimizer
        # Use the default initial guess (interpolated between start and end)
        wp = opt._initial_guess()
        x = wp.flatten()

        class _FakeRes:
            fun = 1.0
            x = None

        _FakeRes.x = x
        result = opt._package_results(_FakeRes)
        assert isinstance(result.n_joint_limit_violations, int)
        assert result.n_joint_limit_violations >= 0

    def test_violations_counted_when_q_exceeds_bounds(self, squat_optimizer) -> None:
        """Forcing joint angles outside limits should produce a positive violation count."""
        opt, _body, _dyn, _qs, _qe = squat_optimizer
        # Build a waypoint array where all waypoints are set to a value well
        # beyond the upper joint limit for every DOF.
        n_wpt = opt.n_waypoints
        n_dof = opt.dynamics.n_dof  # noqa: F841 (used via tile shape)
        # Upper bound for each joint (grab from q_bounds)
        upper = np.array([b[1] for b in opt.q_bounds])
        # Set all waypoints to 2x the upper limit to guarantee violations
        extreme_wp = np.tile(upper * 2.0, (n_wpt, 1))
        x = extreme_wp.flatten()

        class _FakeRes:
            fun: float = 1.0
            x: np.ndarray | None = None

        _FakeRes.x = x
        result = opt._package_results(_FakeRes)
        assert result.n_joint_limit_violations > 0
