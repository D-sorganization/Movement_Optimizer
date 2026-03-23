"""Tests for body model and dynamics engine."""

from __future__ import annotations

import numpy as np
import pytest

from movement_optimizer.constants import BOS_INNER_FRACTION, PLATE_RADIUS_STD_M
from movement_optimizer.models import BodyModel, LagrangianDynamics


class TestBodyModel:
    def test_default_construction(self, default_body: BodyModel) -> None:
        assert default_body.body_mass == 75.0
        assert default_body.height == 1.75
        assert len(default_body.L) == 3
        assert all(default_body.L > 0)

    def test_custom_multipliers(self, custom_body: BodyModel) -> None:
        default = BodyModel(80.0, 1.80)
        assert custom_body.L[0] > default.L[0]
        assert custom_body.L[1] < default.L[1]
        assert custom_body.L[2] > default.L[2]

    def test_negative_mass_raises(self) -> None:
        with pytest.raises(AssertionError, match="body_mass"):
            BodyModel(-10, 1.75)

    def test_zero_height_raises(self) -> None:
        with pytest.raises(AssertionError, match="height"):
            BodyModel(75, 0)

    def test_multiplier_out_of_range_raises(self) -> None:
        with pytest.raises(AssertionError, match="out of range"):
            BodyModel(75, 1.75, seg_multipliers={"lower_leg": 3.0})

    def test_mass_fractions_sum(self, default_body: BodyModel) -> None:
        total = default_body.m_feet + default_body.m_squat.sum()
        assert abs(total - default_body.body_mass) < 1.0

    def test_base_of_support(self, default_body: BodyModel) -> None:
        assert default_body.heel_x < 0
        assert default_body.toe_x > 0
        assert default_body.heel_x < default_body.toe_x

    def test_inner_bos_bounds(self, default_body: BodyModel) -> None:
        """Inner BOS should be strictly inside outer BOS."""
        b = default_body
        assert b.inner_heel > b.heel_x
        assert b.inner_toe < b.toe_x
        assert b.inner_heel < b.inner_toe

    def test_inner_bos_is_60_percent(self, default_body: BodyModel) -> None:
        """Inner BOS should span 60% of the full foot."""
        b = default_body
        full_span = b.toe_x - b.heel_x
        inner_span = b.inner_toe - b.inner_heel
        np.testing.assert_allclose(
            inner_span / full_span, BOS_INNER_FRACTION, atol=1e-10
        )

    def test_inner_center_between_bounds(self, default_body: BodyModel) -> None:
        b = default_body
        assert b.inner_heel < b.inner_center < b.inner_toe


class TestDynamics:
    def test_mass_matrix_symmetric(self, squat_dynamics) -> None:
        dyn, qs, _, _ = squat_dynamics
        M = dyn.mass_matrix(qs)
        np.testing.assert_allclose(M, M.T, atol=1e-12)

    def test_mass_matrix_positive_definite(self, squat_dynamics) -> None:
        dyn, qs, _, _ = squat_dynamics
        M = dyn.mass_matrix(qs)
        eigenvalues = np.linalg.eigvals(M)
        assert all(eigenvalues > 0)

    def test_inverse_dynamics_standing(self, squat_dynamics) -> None:
        dyn, _, _, _ = squat_dynamics
        q = np.zeros(3)
        qd = np.zeros(3)
        qdd = np.zeros(3)
        tau = dyn.inverse_dynamics(q, qd, qdd)
        np.testing.assert_allclose(tau, 0, atol=1e-10)

    def test_inverse_dynamics_shape(self, squat_dynamics) -> None:
        dyn, qs, _, _ = squat_dynamics
        tau = dyn.inverse_dynamics(qs, np.zeros(3), np.zeros(3))
        assert tau.shape == (3,)

    def test_n_dof(self, squat_dynamics) -> None:
        dyn, _, _, _ = squat_dynamics
        assert dyn.n_dof == 3

    def test_backend_name(self, squat_dynamics) -> None:
        dyn, _, _, _ = squat_dynamics
        assert "Lagrangian" in dyn.name

    def test_negative_load_raises(self, default_body: BodyModel) -> None:
        with pytest.raises(AssertionError, match="load_mass"):
            LagrangianDynamics(
                default_body, default_body.m_squat, default_body.I_squat, -10,
            )

    def test_precomputed_coefficients(self, squat_dynamics) -> None:
        """Pre-computed coupling coefficients should match manual calculation."""
        dyn, _, _, _ = squat_dynamics
        b = dyn.body
        expected_a01 = (dyn.m[1] * b.d[1] + (dyn.m[2] + dyn.m_load) * b.L[1]) * b.L[0]
        np.testing.assert_allclose(dyn._a01, expected_a01, rtol=1e-12)


class TestKinematics:
    def test_standing_shoulder_height(self, squat_dynamics) -> None:
        dyn, _, _, _ = squat_dynamics
        fk = dyn.forward_kinematics(np.zeros(3))
        expected_h = dyn.L.sum()
        np.testing.assert_allclose(fk["shoulder"][1], expected_h, atol=1e-10)

    def test_ankle_at_origin(self, squat_dynamics) -> None:
        dyn, qs, _, _ = squat_dynamics
        fk = dyn.forward_kinematics(qs)
        np.testing.assert_allclose(fk["ankle"], [0, 0])

    def test_joint_positions_connected(self, squat_dynamics) -> None:
        dyn, qs, _, _ = squat_dynamics
        fk = dyn.forward_kinematics(qs)
        for i, (a, b) in enumerate([
            (fk["ankle"], fk["knee"]),
            (fk["knee"], fk["hip"]),
            (fk["hip"], fk["shoulder"]),
        ]):
            dist = np.linalg.norm(b - a)
            np.testing.assert_allclose(dist, dyn.L[i], atol=1e-10)


class TestBarAndCOM:
    def test_squat_bar_at_shoulder(self, squat_dynamics) -> None:
        dyn, _, _, _ = squat_dynamics
        q = np.zeros(3)
        fk = dyn.forward_kinematics(q)
        bp = dyn.bar_position(q, "squat")
        np.testing.assert_allclose(bp, fk["shoulder"])

    def test_deadlift_bar_below_shoulder(self, deadlift_dynamics) -> None:
        dyn, qs, _, _ = deadlift_dynamics
        fk = dyn.forward_kinematics(qs)
        bp = dyn.bar_position(qs, "deadlift")
        assert bp[1] < fk["shoulder"][1]

    def test_deadlift_start_bar_near_ground(self, deadlift_dynamics, default_body) -> None:
        dyn, qs, _, _ = deadlift_dynamics
        bp = dyn.bar_position(qs, "deadlift")
        assert abs(bp[1] - PLATE_RADIUS_STD_M) < 0.15

    def test_com_between_heel_and_toe(self, squat_dynamics) -> None:
        dyn, qs, _, _ = squat_dynamics
        com = dyn.com_position(qs, "squat", 60.0)
        assert dyn.body.heel_x - 0.03 <= com[0] <= dyn.body.toe_x + 0.05

    def test_com_positive_height(self, squat_dynamics) -> None:
        dyn, qs, _, _ = squat_dynamics
        com = dyn.com_position(qs, "squat", 60.0)
        assert com[1] > 0


class TestBatchMethods:
    def test_batch_torques_match_loop(self, squat_dynamics) -> None:
        dyn, qs, _, _ = squat_dynamics
        n = 10
        q = np.tile(qs, (n, 1)) + np.random.default_rng(42).normal(0, 0.05, (n, 3))
        qd = np.random.default_rng(43).normal(0, 0.5, (n, 3))
        qdd = np.random.default_rng(44).normal(0, 1.0, (n, 3))

        loop_torques = np.array(
            [dyn.inverse_dynamics(q[i], qd[i], qdd[i]) for i in range(n)]
        )
        batch_torques = dyn.inverse_dynamics_batch(q, qd, qdd)
        np.testing.assert_allclose(batch_torques, loop_torques, rtol=1e-10)

    def test_batch_com_x_matches_loop(self, squat_dynamics) -> None:
        dyn, qs, _, _ = squat_dynamics
        n = 10
        q = np.tile(qs, (n, 1))
        loop_cx = np.array(
            [dyn.com_position(q[i], "squat", 60.0)[0] for i in range(n)]
        )
        batch_cx = dyn.com_x_batch(q, "squat", 60.0)
        np.testing.assert_allclose(batch_cx, loop_cx, rtol=1e-10)


class TestExerciseConfigs:
    def test_squat_config_shapes(self, squat_dynamics) -> None:
        _dyn, qs, qe, qb = squat_dynamics
        assert qs.shape == (3,)
        assert qe.shape == (3,)
        assert qb.shape == (3, 2)

    def test_full_squat_has_via(self, full_squat_config) -> None:
        _dyn, qs, qe, _qb, q_via = full_squat_config
        assert q_via is not None
        assert q_via.shape == (3,)
        np.testing.assert_allclose(qs, [0, 0, 0])
        np.testing.assert_allclose(qe, [0, 0, 0])

    def test_deadlift_config_shapes(self, deadlift_dynamics) -> None:
        _dyn, qs, qe, qb = deadlift_dynamics
        assert qs.shape == (3,)
        assert qe.shape == (3,)
        assert qb.shape == (3, 2)
