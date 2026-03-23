"""Tests for persistence module -- save/load solutions and app state."""

from __future__ import annotations

import json

import numpy as np
import pytest

from movement_optimizer.persistence import (
    load_app_state,
    load_solution,
    save_app_state,
    save_solution,
)
from movement_optimizer.trajectory import OptimizationResult


def _make_result() -> OptimizationResult:
    """Create a minimal OptimizationResult for testing."""
    n = 10
    t = np.linspace(0, 2, n)
    q = np.random.default_rng(42).random((n, 3))
    qd = np.random.default_rng(43).random((n, 3))
    qdd = np.random.default_rng(44).random((n, 3))
    torques = np.random.default_rng(45).random((n, 3))
    power = np.random.default_rng(46).random((n, 3))
    com = np.random.default_rng(47).random((n, 2))
    bar = np.random.default_rng(48).random((n, 2))
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
        cost=42.5,
        com_horizontal_range_cm=3.2,
        elapsed_s=1.5,
        n_evals=100,
    )


class TestSaveSolution:
    def test_round_trip_preserves_all_fields(self, tmp_path):
        result = _make_result()
        body_params = {
            "body_mass": 80.0,
            "height": 1.80,
            "seg_multipliers": {"lower_leg": 1.0, "upper_leg": 1.0, "torso": 1.0},
        }
        path = tmp_path / "solution.json"

        save_solution(str(path), result, body_params, "squat", 60.0)
        loaded = load_solution(str(path))

        assert loaded["exercise_type"] == "squat"
        assert loaded["bar_mass"] == 60.0
        assert loaded["body_params"] == body_params
        assert loaded["metadata"]["success"] is True
        assert loaded["metadata"]["cost"] == pytest.approx(42.5)
        assert loaded["metadata"]["com_horizontal_range_cm"] == pytest.approx(3.2)
        assert loaded["metadata"]["elapsed_s"] == pytest.approx(1.5)
        assert loaded["metadata"]["n_evals"] == 100

    def test_round_trip_preserves_arrays(self, tmp_path):
        result = _make_result()
        body_params = {"body_mass": 75.0, "height": 1.75}
        path = tmp_path / "solution.json"

        save_solution(str(path), result, body_params, "deadlift", 100.0)
        loaded = load_solution(str(path))

        for key in ("t", "q", "qd", "qdd", "torques", "power", "com", "bar"):
            original = getattr(result, key)
            restored = np.array(loaded["arrays"][key])
            np.testing.assert_allclose(restored, original, atol=1e-10)

    def test_load_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_solution("/nonexistent/path/solution.json")

    def test_load_corrupt_file_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json {{{")
        with pytest.raises(json.JSONDecodeError):
            load_solution(str(path))


class TestAppState:
    def test_round_trip_state(self, tmp_path):
        result = _make_result()
        results_dict = {"squat": result}
        slider_values = {
            "body_mass": 80.0,
            "height": 1.80,
            "lower_leg": 1.0,
            "upper_leg": 1.1,
            "torso": 0.9,
            "bar_mass": 60.0,
            "duration": 2.0,
            "smoothness": 1.0,
        }

        state_dir = tmp_path / ".movement_optimizer"
        save_app_state(results_dict, slider_values, state_dir=str(state_dir))
        loaded = load_app_state(state_dir=str(state_dir))

        assert loaded is not None
        assert loaded["slider_values"] == slider_values
        assert "squat" in loaded["results"]
        np.testing.assert_allclose(
            np.array(loaded["results"]["squat"]["arrays"]["t"]),
            result.t,
            atol=1e-10,
        )

    def test_load_missing_state_returns_none(self, tmp_path):
        state_dir = tmp_path / "nonexistent"
        loaded = load_app_state(state_dir=str(state_dir))
        assert loaded is None

    def test_load_corrupt_state_returns_none(self, tmp_path):
        state_dir = tmp_path / ".movement_optimizer"
        state_dir.mkdir(parents=True)
        (state_dir / "last_state.json").write_text("corrupted{{{")
        loaded = load_app_state(state_dir=str(state_dir))
        assert loaded is None
