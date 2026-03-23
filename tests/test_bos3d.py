"""Tests for movement_optimizer.three_d.bos3d -- 3D base of support polygon."""

from __future__ import annotations

import numpy as np

from movement_optimizer.three_d.bos3d import BaseOfSupport3D


class TestBOS3D:
    def test_construction(self):
        bos = BaseOfSupport3D(stance_width=0.30, foot_length=0.26)
        assert bos is not None

    def test_center_point_inside(self):
        bos = BaseOfSupport3D(stance_width=0.30, foot_length=0.26)
        assert bos.contains(np.array([0.1, 0.0]))  # mid-foot, center

    def test_far_point_outside(self):
        bos = BaseOfSupport3D(stance_width=0.30, foot_length=0.26)
        assert not bos.contains(np.array([0.5, 0.5]))  # way outside

    def test_inner_zone_smaller(self):
        bos = BaseOfSupport3D(stance_width=0.30, foot_length=0.26)
        # Inner zone should be strictly inside outer zone
        assert bos.inner_contains(np.array([0.1, 0.0]))  # center is in inner

    def test_distance_at_center_is_negative(self):
        bos = BaseOfSupport3D(stance_width=0.30, foot_length=0.26)
        d = bos.distance_to_boundary(np.array([0.1, 0.0]))
        assert d < 0  # negative = inside

    def test_distance_outside_is_positive(self):
        bos = BaseOfSupport3D(stance_width=0.30, foot_length=0.26)
        d = bos.distance_to_boundary(np.array([0.5, 0.5]))
        assert d > 0  # positive = outside
