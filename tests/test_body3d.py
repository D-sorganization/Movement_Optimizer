"""Tests for movement_optimizer.three_d.body3d -- 3D body model."""

from __future__ import annotations

import numpy as np
import pytest
from numpy.testing import assert_allclose

from movement_optimizer.three_d.body3d import BodyModel3D


@pytest.fixture()
def body() -> BodyModel3D:
    return BodyModel3D(body_mass=75.0, height=1.75)


class TestConstruction:
    """BodyModel3D construction and segment setup."""

    def test_default_construction(self, body: BodyModel3D):
        """Default body model has correct segment count."""
        assert len(body.SEGMENTS) == 15

    def test_segment_count(self, body: BodyModel3D):
        """15 segments: 2 feet, 2 shanks, 2 thighs, pelvis, torso, head,
        2 upper_arms, 2 forearms, 2 hands."""
        assert len(body.segment_masses) == 15

    def test_mass_sums_to_body_mass(self, body: BodyModel3D):
        """All segment masses must sum to the total body mass."""
        total = sum(body.segment_masses.values())
        assert_allclose(total, 75.0, atol=0.1)

    def test_hip_width_positive(self, body: BodyModel3D):
        """Hip width must be positive."""
        assert body.hip_width > 0

    def test_shoulder_width_positive(self, body: BodyModel3D):
        """Shoulder width must be positive."""
        assert body.shoulder_width > 0


class TestForwardKinematics:
    """Forward kinematics raises NotImplementedError (GitHub issue #76)."""

    def test_fk_not_implemented(self, body: BodyModel3D):
        """forward_kinematics must raise NotImplementedError (issue #76)."""
        q = np.zeros(16)
        with pytest.raises(NotImplementedError):
            body.forward_kinematics(q)

    def test_fk_wrong_dof_raises_value_error(self, body: BodyModel3D):
        """Passing wrong DOF count must raise ValueError before NotImplementedError."""
        q = np.zeros(10)
        with pytest.raises(ValueError):
            body.forward_kinematics(q)
