"""Benchmarking suite for performance regression testing.

These tests measure execution time of critical code paths and fail if
they exceed generous upper bounds.  The bounds are intentionally loose
to avoid flaky CI failures -- they catch order-of-magnitude regressions
rather than fine-grained performance changes.

Each benchmark uses *median* timing over multiple independent trials to
reduce sensitivity to transient CPU load, OS scheduling, and thermal
throttling.  Thresholds are set high enough to pass on slow CI machines
(observed up to ~44ms for batch ID on Windows) while still catching
genuine regressions.

Run with:
    python3 -m pytest tests/test_benchmarks.py -v --tb=short
"""

from __future__ import annotations

import statistics
import time

import numpy as np

from movement_optimizer.models import BodyModel, make_squat_config

# ---------------------------------------------------------------------------
# Number of independent timing trials for each benchmark.  The *median*
# trial is compared against the threshold so that a single slow outlier
# (e.g. OS context-switch) cannot cause a failure.
# ---------------------------------------------------------------------------
_BENCHMARK_TRIALS = 5


def _measure_ms(fn: object, iterations: int, trials: int = _BENCHMARK_TRIALS) -> float:
    """Return the *median* per-call time in milliseconds.

    Runs *fn* for *iterations* calls in each of *trials* independent
    timing windows, then returns ``statistics.median`` of the per-call
    times.  Using the median rather than a single measurement makes the
    benchmark resilient to transient system noise.
    """
    times: list[float] = []
    for _ in range(trials):
        start = time.perf_counter()
        for _ in range(iterations):
            fn()  # type: ignore[operator]
        elapsed = time.perf_counter() - start
        times.append(elapsed / iterations * 1000)  # ms per call
    return statistics.median(times)


class TestInverseDynamicsBenchmark:
    """Benchmark the inverse dynamics hot path."""

    def test_single_inverse_dynamics_speed(self, default_body: BodyModel):
        """Single-pose inverse dynamics should complete in < 2ms (median)."""
        dyn, _, _, _ = make_squat_config(default_body, 60.0)
        q = np.array([0.1, -0.5, 0.3])
        qd = np.array([0.5, -0.3, 0.2])
        qdd = np.array([1.0, -1.0, 0.5])

        # Warmup -- multiple calls to stabilise JIT / CPU caches
        for _ in range(10):
            dyn.inverse_dynamics(q, qd, qdd)

        per_call_ms = _measure_ms(lambda: dyn.inverse_dynamics(q, qd, qdd), iterations=1000)
        assert per_call_ms < 2.0, f"Single ID call took {per_call_ms:.3f}ms median (limit: 2ms)"

    def test_batch_inverse_dynamics_speed(self, default_body: BodyModel):
        """Batch inverse dynamics (100 timesteps) should complete in < 50ms (median).

        The threshold is intentionally generous (observed ~5-44ms across
        platforms) to avoid flaky failures on slow CI runners while still
        catching order-of-magnitude regressions.
        """
        dyn, _, _, _ = make_squat_config(default_body, 60.0)
        n = 100
        rng = np.random.default_rng(42)
        q = rng.uniform(-1.5, 1.5, (n, 3))
        qd = rng.uniform(-5, 5, (n, 3))
        qdd = rng.uniform(-10, 10, (n, 3))

        # Warmup -- multiple calls to stabilise JIT / CPU caches
        for _ in range(5):
            dyn.inverse_dynamics_batch(q, qd, qdd)

        per_call_ms = _measure_ms(lambda: dyn.inverse_dynamics_batch(q, qd, qdd), iterations=100)
        assert per_call_ms < 50.0, f"Batch ID (N=100) took {per_call_ms:.3f}ms median (limit: 50ms)"


class TestMassMatrixBenchmark:
    def test_mass_matrix_speed(self, default_body: BodyModel):
        """Mass matrix computation should complete in < 1ms (median)."""
        dyn, _, _, _ = make_squat_config(default_body, 60.0)
        q = np.array([0.1, -0.5, 0.3])

        # Warmup
        for _ in range(10):
            dyn.mass_matrix(q)

        per_call_ms = _measure_ms(lambda: dyn.mass_matrix(q), iterations=1000)
        assert per_call_ms < 1.0, f"Mass matrix took {per_call_ms:.3f}ms median (limit: 1ms)"


class TestForwardKinematicsBenchmark:
    def test_forward_kinematics_speed(self, default_body: BodyModel):
        """Forward kinematics should complete in < 1ms (median)."""
        dyn, _, _, _ = make_squat_config(default_body, 60.0)
        q = np.array([0.1, -0.5, 0.3])

        # Warmup
        for _ in range(10):
            dyn.forward_kinematics(q)

        per_call_ms = _measure_ms(lambda: dyn.forward_kinematics(q), iterations=1000)
        assert per_call_ms < 1.0, f"FK took {per_call_ms:.3f}ms median (limit: 1ms)"


class TestBodyModelBenchmark:
    def test_body_model_construction_speed(self):
        """BodyModel construction should complete in < 2ms (median)."""
        # Warmup
        for _ in range(10):
            BodyModel(75.0, 1.75)

        per_call_ms = _measure_ms(lambda: BodyModel(75.0, 1.75), iterations=1000)
        assert per_call_ms < 2.0, f"BodyModel init took {per_call_ms:.3f}ms median (limit: 2ms)"
