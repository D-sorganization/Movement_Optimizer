"""Tests for comparison module -- trial storage and metrics."""

from __future__ import annotations

import numpy as np

from movement_optimizer.comparison import ComparisonStore, comparison_metrics
from movement_optimizer.trajectory import OptimizationResult


def _make_result(seed: int = 42, cost: float = 42.5) -> OptimizationResult:
    """Create a minimal OptimizationResult for testing."""
    n = 10
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 2, n)
    q = rng.random((n, 3))
    qd = rng.random((n, 3))
    qdd = rng.random((n, 3))
    torques = rng.random((n, 3))
    power = torques * qd
    com = rng.random((n, 2))
    bar = rng.random((n, 2))
    return OptimizationResult(
        t=t,
        q=q,
        qd=qd,
        qdd=qdd,
        torques=torques,
        power=power,
        com=com,
        bar=bar,
        success=True,
        cost=cost,
        com_horizontal_range_cm=3.2,
        elapsed_s=1.5,
        n_evals=100,
    )


class TestComparisonStore:
    def test_add_and_get_trials(self):
        store = ComparisonStore()
        r1 = _make_result(seed=1)
        r2 = _make_result(seed=2)
        store.add_trial("Trial A", r1, {"body_mass": 75.0}, 60.0)
        store.add_trial("Trial B", r2, {"body_mass": 80.0}, 80.0)

        trials = store.get_trials()
        assert len(trials) == 2
        assert trials[0]["name"] == "Trial A"
        assert trials[1]["name"] == "Trial B"
        assert trials[0]["bar_mass"] == 60.0

    def test_clear(self):
        store = ComparisonStore()
        store.add_trial("T", _make_result(), {}, 60.0)
        assert len(store.get_trials()) == 1
        store.clear()
        assert len(store.get_trials()) == 0

    def test_empty_store(self):
        store = ComparisonStore()
        assert store.get_trials() == []


class TestComparisonMetrics:
    def test_metrics_keys(self):
        r1 = _make_result(seed=1)
        r2 = _make_result(seed=2)
        trials = [
            {"name": "A", "result": r1, "body_params": {}, "bar_mass": 60.0},
            {"name": "B", "result": r2, "body_params": {}, "bar_mass": 80.0},
        ]
        metrics = comparison_metrics(trials)
        assert len(metrics) == 2
        for m in metrics:
            assert "name" in m
            assert "peak_torques" in m
            assert "total_work" in m
            assert "com_sway_cm" in m

    def test_metrics_values_are_reasonable(self):
        r = _make_result(seed=10)
        trials = [{"name": "X", "result": r, "body_params": {}, "bar_mass": 60.0}]
        metrics = comparison_metrics(trials)
        m = metrics[0]
        assert len(m["peak_torques"]) == 3
        assert all(v >= 0 for v in m["peak_torques"])
        assert m["total_work"] >= 0
        assert m["com_sway_cm"] >= 0

    def test_empty_trials(self):
        metrics = comparison_metrics([])
        assert metrics == []
