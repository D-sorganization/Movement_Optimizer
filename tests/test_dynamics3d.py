"""Tests for movement_optimizer.three_d.dynamics3d -- 3D inverse dynamics."""

from __future__ import annotations

import numpy as np
import pytest

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
    """Inverse dynamics raises NotImplementedError (GitHub issues #76, #77)."""

    def test_inverse_dynamics_not_implemented(self, dynamics: Dynamics3D):
        """inverse_dynamics must raise NotImplementedError (issue #77)."""
        q = np.zeros(16)
        qd = np.zeros(16)
        qdd = np.zeros(16)
        with pytest.raises(NotImplementedError):
            dynamics.inverse_dynamics(q, qd, qdd)

    def test_inverse_dynamics_batch_not_implemented(self, dynamics: Dynamics3D):
        """inverse_dynamics_batch must raise NotImplementedError (issue #77)."""
        N = 5
        q = np.zeros((N, 16))
        qd = np.zeros((N, 16))
        qdd = np.zeros((N, 16))
        with pytest.raises(NotImplementedError):
            dynamics.inverse_dynamics_batch(q, qd, qdd)


class TestCOM:
    """Centre of mass raises NotImplementedError (GitHub issues #76, #77)."""

    def test_com_position_not_implemented(self, dynamics: Dynamics3D):
        """com_position must raise NotImplementedError (issue #77)."""
        q = np.zeros(16)
        with pytest.raises(NotImplementedError):
            dynamics.com_position(q)

    def test_bar_position_not_implemented(self, dynamics: Dynamics3D):
        """bar_position must raise NotImplementedError (issue #77)."""
        q = np.zeros(16)
        with pytest.raises(NotImplementedError):
            dynamics.bar_position(q, "squat")

    def test_com_x_batch_not_implemented(self, dynamics: Dynamics3D):
        """com_x_batch must raise NotImplementedError (issue #77)."""
        N = 5
        q = np.zeros((N, 16))
        with pytest.raises(NotImplementedError):
            dynamics.com_x_batch(q, "squat", 0.0)
