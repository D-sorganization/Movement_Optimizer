"""Property-based tests using Hypothesis.

These tests fuzz the core models with randomly generated inputs to
catch edge cases that unit tests might miss.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from movement_optimizer.models import (
    BodyModel,
    HillTorqueModel,
    LagrangianDynamics,
    clamp_joint_angles,
)


class TestBodyModelProperties:
    @given(
        body_mass=st.floats(min_value=30.0, max_value=200.0),
        height=st.floats(min_value=1.2, max_value=2.2),
    )
    @settings(max_examples=100)
    def test_body_model_valid_inputs(self, body_mass: float, height: float):
        """BodyModel should accept any reasonable mass and height."""
        body = BodyModel(body_mass=body_mass, height=height)
        assert body.body_mass == body_mass
        assert body.height == height
        assert len(body.L) == 3
        assert all(body.L > 0)
        assert body.inner_heel < body.inner_toe

    @given(
        body_mass=st.floats(min_value=-100.0, max_value=0.0),
    )
    @settings(max_examples=100)
    def test_body_model_rejects_nonpositive_mass(self, body_mass: float):
        """BodyModel should reject non-positive mass."""
        with pytest.raises(ValueError, match="body_mass"):
            BodyModel(body_mass=body_mass, height=1.75)

    @given(
        ll=st.floats(min_value=0.5, max_value=2.0),
        ul=st.floats(min_value=0.5, max_value=2.0),
        to=st.floats(min_value=0.5, max_value=2.0),
    )
    @settings(max_examples=100)
    def test_segment_multipliers_preserve_proportionality(self, ll: float, ul: float, to: float):
        """Segment lengths should scale linearly with multipliers."""
        base = BodyModel(75.0, 1.75)
        scaled = BodyModel(
            75.0,
            1.75,
            seg_multipliers={"lower_leg": ll, "upper_leg": ul, "torso": to},
        )
        np.testing.assert_allclose(scaled.L[0], base.L[0] * ll, rtol=1e-10)
        np.testing.assert_allclose(scaled.L[1], base.L[1] * ul, rtol=1e-10)
        np.testing.assert_allclose(scaled.L[2], base.L[2] * to, rtol=1e-10)


class TestHillTorqueModelProperties:
    @given(
        q=st.floats(min_value=-2.0, max_value=2.0),
        qd=st.floats(min_value=-10.0, max_value=10.0),
    )
    @settings(max_examples=100)
    def test_available_torque_nonnegative(self, q: float, qd: float):
        """Available torque should always be non-negative."""
        model = HillTorqueModel(tau_max=200.0, q_optimal=1.0)
        t = model.available_torque(q, qd)
        assert float(t) >= 0.0

    @given(
        tau_max=st.floats(min_value=10.0, max_value=1000.0),
    )
    @settings(max_examples=100)
    def test_peak_torque_at_optimal_angle(self, tau_max: float):
        """Torque at optimal angle with zero velocity should equal tau_max."""
        model = HillTorqueModel(tau_max=tau_max, q_optimal=1.0)
        t = model.available_torque(1.0, 0.0)
        np.testing.assert_allclose(float(t), tau_max, rtol=1e-6)


class TestClampJointAnglesProperties:
    @given(
        q0=st.floats(min_value=-3.0, max_value=3.0),
        q1=st.floats(min_value=-3.0, max_value=3.0),
        q2=st.floats(min_value=-3.0, max_value=3.0),
    )
    @settings(max_examples=100)
    def test_clamped_angles_within_limits(self, q0: float, q1: float, q2: float):
        """Clamped angles should always be within joint limits."""
        from movement_optimizer.constants import JOINT_LIMITS, JOINT_NAMES

        q = np.array([q0, q1, q2])
        clamped = clamp_joint_angles(q)
        for i, name in enumerate(JOINT_NAMES):
            lo, hi = JOINT_LIMITS[name]
            assert clamped[i] >= lo - 1e-10
            assert clamped[i] <= hi + 1e-10


class TestInverseDynamicsProperties:
    @given(
        q0=st.floats(min_value=-1.5, max_value=1.5),
        q1=st.floats(min_value=-1.5, max_value=1.5),
        q2=st.floats(min_value=-1.5, max_value=1.5),
    )
    @settings(max_examples=100)
    def test_static_torques_finite(self, q0: float, q1: float, q2: float):
        """Static torques (zero velocity/acceleration) should be finite."""
        body = BodyModel(75.0, 1.75)
        dyn = LagrangianDynamics(body, body.m_squat.copy(), body.I_squat.copy(), 60.0)
        q = np.array([q0, q1, q2])
        qd = np.zeros(3)
        qdd = np.zeros(3)
        tau = dyn.inverse_dynamics(q, qd, qdd)
        assert np.all(np.isfinite(tau))

    @given(
        q0=st.floats(min_value=-1.5, max_value=1.5),
        q1=st.floats(min_value=-1.5, max_value=1.5),
        q2=st.floats(min_value=-1.5, max_value=1.5),
    )
    @settings(max_examples=100)
    def test_mass_matrix_positive_definite(self, q0: float, q1: float, q2: float):
        """Mass matrix should be positive definite for any configuration."""
        body = BodyModel(75.0, 1.75)
        dyn = LagrangianDynamics(body, body.m_squat.copy(), body.I_squat.copy(), 60.0)
        q = np.array([q0, q1, q2])
        M = dyn.mass_matrix(q)
        eigenvalues = np.linalg.eigvalsh(M)
        assert np.all(eigenvalues > 0)
