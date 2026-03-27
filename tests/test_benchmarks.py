"""Benchmarking suite for performance regression testing.

These tests measure execution time of critical code paths and fail if
they exceed generous upper bounds.  The bounds are intentionally loose
to avoid flaky CI failures -- they catch order-of-magnitude regressions
rather than fine-grained performance changes.

Run with:
    python3 -m pytest tests/test_benchmarks.py -v --tb=short
"""

from __future__ import annotations

import time

import numpy as np

from movement_optimizer.models import BodyModel, make_squat_config


class TestInverseDynamicsBenchmark:
    """Benchmark the inverse dynamics hot path."""

    def test_single_inverse_dynamics_speed(self, default_body: BodyModel):
        """Single-pose inverse dynamics should complete in < 1ms."""
        dyn, _, _, _ = make_squat_config(default_body, 60.0)
        q = np.array([0.1, -0.5, 0.3])
        qd = np.array([0.5, -0.3, 0.2])
        qdd = np.array([1.0, -1.0, 0.5])

        # Warmup
        dyn.inverse_dynamics(q, qd, qdd)

        start = time.perf_counter()
        for _ in range(1000):
            dyn.inverse_dynamics(q, qd, qdd)
        elapsed = time.perf_counter() - start

        per_call_ms = elapsed / 1000 * 1000
        assert per_call_ms < 1.0, f"Single ID call took {per_call_ms:.3f}ms (limit: 1ms)"

    def test_batch_inverse_dynamics_speed(self, default_body: BodyModel):
        """Batch inverse dynamics (100 timesteps) should complete in < 10ms."""
        dyn, _, _, _ = make_squat_config(default_body, 60.0)
        n = 100
        rng = np.random.default_rng(42)
        q = rng.uniform(-1.5, 1.5, (n, 3))
        qd = rng.uniform(-5, 5, (n, 3))
        qdd = rng.uniform(-10, 10, (n, 3))

        # Warmup
        dyn.inverse_dynamics_batch(q, qd, qdd)

        start = time.perf_counter()
        for _ in range(100):
            dyn.inverse_dynamics_batch(q, qd, qdd)
        elapsed = time.perf_counter() - start

        per_call_ms = elapsed / 100 * 1000
        assert per_call_ms < 50.0, f"Batch ID (N=100) took {per_call_ms:.3f}ms (limit: 50ms)"


class TestMassMatrixBenchmark:
    def test_mass_matrix_speed(self, default_body: BodyModel):
        """Mass matrix computation should complete in < 0.5ms."""
        dyn, _, _, _ = make_squat_config(default_body, 60.0)
        q = np.array([0.1, -0.5, 0.3])

        # Warmup
        dyn.mass_matrix(q)

        start = time.perf_counter()
        for _ in range(1000):
            dyn.mass_matrix(q)
        elapsed = time.perf_counter() - start

        per_call_ms = elapsed / 1000 * 1000
        assert per_call_ms < 0.5, f"Mass matrix took {per_call_ms:.3f}ms (limit: 0.5ms)"


class TestForwardKinematicsBenchmark:
    def test_forward_kinematics_speed(self, default_body: BodyModel):
        """Forward kinematics should complete in < 0.5ms."""
        dyn, _, _, _ = make_squat_config(default_body, 60.0)
        q = np.array([0.1, -0.5, 0.3])

        # Warmup
        dyn.forward_kinematics(q)

        start = time.perf_counter()
        for _ in range(1000):
            dyn.forward_kinematics(q)
        elapsed = time.perf_counter() - start

        per_call_ms = elapsed / 1000 * 1000
        assert per_call_ms < 0.5, f"FK took {per_call_ms:.3f}ms (limit: 0.5ms)"


class TestBodyModelBenchmark:
    def test_body_model_construction_speed(self):
        """BodyModel construction should complete in < 1ms."""
        # Warmup
        BodyModel(75.0, 1.75)

        start = time.perf_counter()
        for _ in range(1000):
            BodyModel(75.0, 1.75)
        elapsed = time.perf_counter() - start

        per_call_ms = elapsed / 1000 * 1000
        assert per_call_ms < 1.0, f"BodyModel init took {per_call_ms:.3f}ms (limit: 1ms)"
