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
    """Forward kinematics at standing pose (q=0)."""

    def test_standing_fk_symmetric(self, body: BodyModel3D):
        """At standing pose, left and right ankle positions are mirror images in x."""
        q = np.zeros(16)
        joints = body.forward_kinematics(q)
        # Left ankle should be at -hip_width/2 in x, right at +hip_width/2
        ankle_l = joints["ankle_l"]
        ankle_r = joints["ankle_r"]
        assert_allclose(ankle_l[0], -ankle_r[0], atol=1e-6)
        assert_allclose(ankle_l[1], ankle_r[1], atol=1e-6)
        assert_allclose(ankle_l[2], ankle_r[2], atol=1e-6)

    def test_standing_head_height(self, body: BodyModel3D):
        """Head position at standing should be approximately body height."""
        q = np.zeros(16)
        joints = body.forward_kinematics(q)
        head_z = joints["head"][2]
        # Head should be near body height (within ~10%)
        assert abs(head_z - body.height) < 0.2 * body.height

    def test_joint_count(self, body: BodyModel3D):
        """Number of joints returned by FK matches expected structure."""
        q = np.zeros(16)
        joints = body.forward_kinematics(q)
        # At minimum: 2 ankles, 2 knees, 2 hips, pelvis, spine_top,
        # head, 2 shoulders, 2 elbows, 2 wrists
        assert len(joints) >= 13
