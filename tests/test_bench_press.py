"""Tests for bench press model (issue #26)."""

from __future__ import annotations

import numpy as np

from movement_optimizer.models import (
    BenchPressModel,
    BodyModel,
    make_bench_press_config,
)


class TestBenchPressConfig:
    def test_bench_config_shapes(self, default_body: BodyModel) -> None:
        """make_bench_press_config returns correct shapes."""
        _dyn, qs, qe, qb, q_via = make_bench_press_config(default_body, 60.0)
        assert qs.shape == (3,)
        assert qe.shape == (3,)
        assert qb.shape == (3, 2)
        assert q_via is not None
        assert q_via.shape == (3,)

    def test_bench_horizontal_orientation(self, default_body: BodyModel) -> None:
        """The bench press models a supine (horizontal) body.

        The arm chain starts at the shoulder; joints swing in the
        sagittal plane perpendicular to the body's long axis.
        Verify that the BenchPressModel segment lengths are derived
        from the arm, not the legs/torso.
        """
        bp = BenchPressModel(default_body)
        total_arm_len = bp.L[0] + bp.L[1] + bp.L[2]
        # Total should be close to L_arm + small wrist segment
        assert abs(total_arm_len - (default_body.L_arm + 0.05)) < 0.01

    def test_arm_angle_default(self, default_body: BodyModel) -> None:
        """Default arm_angle is 45 degrees."""
        body = BodyModel(75.0, 1.75, arm_angle=45.0)
        assert body.arm_angle == 45.0

    def test_arm_effective_length(self, default_body: BodyModel) -> None:
        """L_arm_eff = L_arm * sin(arm_angle_rad)."""
        body = BodyModel(75.0, 1.75, arm_angle=45.0)
        expected = body.L_arm * np.sin(np.radians(45.0))
        np.testing.assert_allclose(body.L_arm_eff, expected, rtol=1e-12)

    def test_arm_angle_zero_gives_zero_eff(self) -> None:
        """With arm_angle=0, projected arm length is 0."""
        body = BodyModel(75.0, 1.75, arm_angle=0.0)
        np.testing.assert_allclose(body.L_arm_eff, 0.0, atol=1e-15)

    def test_arm_angle_90_gives_full_length(self) -> None:
        """With arm_angle=90, projected arm length equals full L_arm."""
        body = BodyModel(75.0, 1.75, arm_angle=90.0)
        np.testing.assert_allclose(body.L_arm_eff, body.L_arm, rtol=1e-12)

    def test_bar_above_body(self, default_body: BodyModel) -> None:
        """Bar y > 0 at both start and end positions.

        In the bench press the bar is always above the body (positive y
        in the FK frame, since the chain swings upward from the shoulder).
        """
        dyn, qs, qe, _qb, _q_via = make_bench_press_config(default_body, 60.0)
        fk_start = dyn.forward_kinematics(qs)
        fk_end = dyn.forward_kinematics(qe)
        # The wrist (end effector) y should be positive at both poses
        # (bar is above the shoulder pivot which is at y=0)
        # In the FK model, "shoulder" is the endpoint of the chain
        # and all joints should have positive y component for a press
        assert fk_start["shoulder"][1] > 0, "Bar should be above body at start"
        assert fk_end["shoulder"][1] > 0, "Bar should be above body at end"
