"""Tests for 3D exercise configuration factories."""

from __future__ import annotations

import pytest

from movement_optimizer.exercises_3d import (
    make_bench_config_3d,
    make_clean_config_3d,
    make_deadlift_config_3d,
    make_jerk_config_3d,
    make_snatch_config_3d,
    make_squat_config_3d,
)
from movement_optimizer.three_d.body3d import BodyModel3D
from movement_optimizer.three_d.dynamics3d import Dynamics3D


@pytest.fixture()
def body3d() -> BodyModel3D:
    return BodyModel3D(body_mass=75.0, height=1.75)


# ------------------------------------------------------------------
# Squat
# ------------------------------------------------------------------


class TestSquat3D:
    def test_squat_3d_shapes(self, body3d: BodyModel3D) -> None:
        dyn, qs, qe, qb, q_via = make_squat_config_3d(body3d, 60.0)
        assert isinstance(dyn, Dynamics3D)
        assert qs.shape == (16,)
        assert qe.shape == (16,)
        assert qb.shape == (16, 2)
        # Full squat has a via-point (bottom position)
        assert q_via is not None
        assert q_via.shape == (16,)


# ------------------------------------------------------------------
# Deadlift
# ------------------------------------------------------------------


class TestDeadlift3D:
    def test_deadlift_3d_shapes(self, body3d: BodyModel3D) -> None:
        dyn, qs, qe, qb = make_deadlift_config_3d(body3d, 60.0)
        assert isinstance(dyn, Dynamics3D)
        assert qs.shape == (16,)
        assert qe.shape == (16,)
        assert qb.shape == (16, 2)


# ------------------------------------------------------------------
# Bench Press
# ------------------------------------------------------------------


class TestBench3D:
    def test_bench_3d_shapes(self, body3d: BodyModel3D) -> None:
        dyn, qs, qe, qb = make_bench_config_3d(body3d, 60.0)
        assert isinstance(dyn, Dynamics3D)
        assert qs.shape == (16,)
        assert qe.shape == (16,)
        assert qb.shape == (16, 2)


# ------------------------------------------------------------------
# Clean
# ------------------------------------------------------------------


class TestClean3D:
    def test_clean_3d_shapes(self, body3d: BodyModel3D) -> None:
        dyn, qs, qe, qb, q_via = make_clean_config_3d(body3d, 60.0)
        assert isinstance(dyn, Dynamics3D)
        assert qs.shape == (16,)
        assert qe.shape == (16,)
        assert qb.shape == (16, 2)
        assert q_via is not None
        assert q_via.shape == (16,)


# ------------------------------------------------------------------
# Jerk
# ------------------------------------------------------------------


class TestJerk3D:
    def test_jerk_3d_shapes(self, body3d: BodyModel3D) -> None:
        dyn, qs, qe, qb, q_via = make_jerk_config_3d(body3d, 60.0)
        assert isinstance(dyn, Dynamics3D)
        assert qs.shape == (16,)
        assert qe.shape == (16,)
        assert qb.shape == (16, 2)
        assert q_via is not None
        assert q_via.shape == (16,)


# ------------------------------------------------------------------
# Snatch
# ------------------------------------------------------------------


class TestSnatch3D:
    def test_snatch_3d_shapes(self, body3d: BodyModel3D) -> None:
        dyn, qs, qe, qb, q_via = make_snatch_config_3d(body3d, 60.0)
        assert isinstance(dyn, Dynamics3D)
        assert qs.shape == (16,)
        assert qe.shape == (16,)
        assert qb.shape == (16, 2)
        assert q_via is not None
        assert q_via.shape == (16,)


# ------------------------------------------------------------------
# All configs: 16-DOF check
# ------------------------------------------------------------------


class TestAll16DOF:
    """All 3D config factories must produce q vectors of length 16."""

    def test_all_configs_return_16_dof(self, body3d: BodyModel3D) -> None:
        configs = [
            make_squat_config_3d(body3d, 60.0),
            make_deadlift_config_3d(body3d, 60.0),
            make_bench_config_3d(body3d, 60.0),
            make_clean_config_3d(body3d, 60.0),
            make_jerk_config_3d(body3d, 60.0),
            make_snatch_config_3d(body3d, 60.0),
        ]
        for cfg in configs:
            # cfg is (dyn, q_start, q_end, q_bounds[, q_via])
            q_start = cfg[1]
            q_end = cfg[2]
            assert q_start.shape == (16,), f"q_start shape {q_start.shape} != (16,)"
            assert q_end.shape == (16,), f"q_end shape {q_end.shape} != (16,)"
            if len(cfg) == 5:
                q_via = cfg[4]
                assert q_via.shape == (16,), f"q_via shape {q_via.shape} != (16,)"
