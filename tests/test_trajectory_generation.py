"""Tests for the trajectory optimiser.

Covers: spline construction, cost sub-terms, via-point support,
optimisation convergence, COM constraint enforcement, parallel
multi-start, cancellation, stall detection, and solution caching.
"""

from __future__ import annotations

import numpy as np
import pytest

from movement_optimizer.models import (
    BodyModel,
    make_squat_config,
)
from movement_optimizer.trajectory import (
    TrajectoryOptimizer,
)

# ==============================================================
# Generation Tests
# ==============================================================


class TestConstruction:
    def test_too_few_waypoints_raises(self) -> None:
        body = BodyModel(75.0, 1.75)
        dyn, qs, qe, qb = make_squat_config(body, 60.0)
        with pytest.raises(ValueError, match="waypoints"):
            TrajectoryOptimizer(
                body,
                dyn,
                "squat",
                60.0,
                qs,
                qe,
                qb,
                n_waypoints=2,
            )

    def test_bad_bounds_shape_raises(self) -> None:
        body = BodyModel(75.0, 1.75)
        dyn, qs, qe, _ = make_squat_config(body, 60.0)
        bad_bounds = np.zeros((2, 3))  # wrong second dim (3 instead of 2)
        with pytest.raises(ValueError, match="q_bounds"):
            TrajectoryOptimizer(
                body,
                dyn,
                "squat",
                60.0,
                qs,
                qe,
                bad_bounds,
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
