"""Tests for movement_optimizer.three_d.dynamics3d -- 3D inverse dynamics."""

from __future__ import annotations

import numpy as np
import pytest
from numpy.testing import assert_allclose

from movement_optimizer.backend import PhysicsBackend
from movement_optimizer.three_d.body3d import BodyModel3D
from movement_optimizer.three_d.dynamics3d import Dynamics3D


@pytest.fixture()
def body() -> BodyModel3D:
    return BodyModel3D(body_mass=75.0, height=1.75)


@pytest.fixture()
def dynamics(body: BodyModel3D) -> Dynamics3D:
    return Dynamics3D(body=body, load_mass=0.0)


class TestInterface:
    """Dynamics3D implements PhysicsBackend."""

    def test_implements_backend(self, dynamics: Dynamics3D):
        """Dynamics3D must be a PhysicsBackend."""
        assert isinstance(dynamics, PhysicsBackend)

    def test_n_dof(self, dynamics: Dynamics3D):
        """n_dof should return 16."""
        assert dynamics.n_dof == 16


class TestInverseDynamics:
    """Inverse dynamics computations."""

    def test_standing_torques_near_zero(self, dynamics: Dynamics3D):
        """At standing (q=0, qd=0, qdd=0) joint torques should be near zero."""
        q = np.zeros(16)
        qd = np.zeros(16)
        qdd = np.zeros(16)
        tau = dynamics.inverse_dynamics(q, qd, qdd)
        # Standing is an equilibrium; gravity torques should be small
        # (not exactly zero because of how COM aligns, but small)
        assert_allclose(tau, np.zeros(16), atol=50.0)

    def test_inverse_dynamics_shape(self, dynamics: Dynamics3D):
        """Inverse dynamics returns shape (16,) for single timestep."""
        q = np.zeros(16)
        qd = np.zeros(16)
        qdd = np.zeros(16)
        tau = dynamics.inverse_dynamics(q, qd, qdd)
        assert tau.shape == (16,)

    def test_batch_shape(self, dynamics: Dynamics3D):
        """Batch inverse dynamics returns (N, 16) for N timesteps."""
        N = 5
        q = np.zeros((N, 16))
        qd = np.zeros((N, 16))
        qdd = np.zeros((N, 16))
        tau = dynamics.inverse_dynamics_batch(q, qd, qdd)
        assert tau.shape == (N, 16)

    def test_bilateral_symmetry(self, dynamics: Dynamics3D):
        """Symmetric pose should give symmetric torques for left/right."""
        q = np.zeros(16)
        qd = np.zeros(16)
        qdd = np.zeros(16)
        tau = dynamics.inverse_dynamics(q, qd, qdd)
        # DOF layout: [ankle_l, knee_l, hip_flex_l, hip_abd_l,
        #              ankle_r, knee_r, hip_flex_r, hip_abd_r,
        #              spine_flex, spine_lat,
        #              sh_flex_l, sh_abd_l, elbow_l,
        #              sh_flex_r, sh_abd_r, elbow_r]
        # Left leg (0:4) should mirror right leg (4:8)
        assert_allclose(tau[0:4], tau[4:8], atol=1e-6)


class TestCOM:
    """Centre of mass computations."""

    def test_com_at_standing(self, dynamics: Dynamics3D):
        """COM at standing should be roughly at body centre height."""
        q = np.zeros(16)
        com = dynamics.com_position(q)
        # COM z should be roughly 55% of height (Winter anthropometry)
        expected_z = 0.55 * 1.75
        assert abs(com[2] - expected_z) < 0.3 * 1.75
