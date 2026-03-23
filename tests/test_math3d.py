"""Tests for movement_optimizer.three_d.math3d -- 3D rotation and mesh utilities."""

from __future__ import annotations

import math

import numpy as np
from numpy.testing import assert_allclose

from movement_optimizer.three_d.math3d import (
    cylinder_mesh,
    ellipsoid_mesh,
    homogeneous_transform,
    rotation_x,
    rotation_y,
    rotation_z,
    sphere_mesh,
    transform_point,
)


class TestRotations:
    """Rotation matrix construction and properties."""

    def test_rotation_x_identity(self):
        """Rx(0) should be the 3x3 identity matrix."""
        R = rotation_x(0.0)
        assert_allclose(R, np.eye(3), atol=1e-12)

    def test_rotation_y_90(self):
        """Ry(90 deg) rotates [1,0,0] to [0,0,-1]."""
        R = rotation_y(math.pi / 2)
        v = R @ np.array([1.0, 0.0, 0.0])
        assert_allclose(v, np.array([0.0, 0.0, -1.0]), atol=1e-12)

    def test_rotation_composition(self):
        """Rx(a) @ Ry(b) must be a valid rotation (det=1, orthogonal)."""
        a, b = 0.3, 0.7
        R = rotation_x(a) @ rotation_y(b)
        # Determinant should be 1
        assert_allclose(np.linalg.det(R), 1.0, atol=1e-12)
        # Orthogonality: R^T @ R == I
        assert_allclose(R.T @ R, np.eye(3), atol=1e-12)

    def test_rotation_inverse(self):
        """R @ R^T must equal identity for any rotation."""
        R = rotation_z(1.23)
        assert_allclose(R @ R.T, np.eye(3), atol=1e-12)


class TestTransforms:
    """Homogeneous transforms and point transformation."""

    def test_transform_translation(self):
        """A pure translation transform moves a point correctly."""
        t = np.array([1.0, 2.0, 3.0])
        T = homogeneous_transform(np.eye(3), t)
        p = np.array([0.0, 0.0, 0.0])
        result = transform_point(T, p)
        assert_allclose(result, t, atol=1e-12)

    def test_transform_rotation_and_translation(self):
        """Combined rotation + translation applies correctly."""
        R = rotation_x(math.pi / 2)
        t = np.array([0.0, 0.0, 5.0])
        T = homogeneous_transform(R, t)
        p = np.array([0.0, 1.0, 0.0])
        result = transform_point(T, p)
        # Rx(90)*[0,1,0] = [0,0,1], then + [0,0,5] = [0,0,6]
        assert_allclose(result, np.array([0.0, 0.0, 6.0]), atol=1e-12)


class TestMeshes:
    """Mesh generation functions."""

    def test_cylinder_mesh_shape(self):
        """Cylinder mesh returns vertices (N,3) and faces (M,3)."""
        p0 = np.array([0.0, 0.0, 0.0])
        p1 = np.array([0.0, 0.0, 1.0])
        verts, faces = cylinder_mesh(p0, p1, radius=0.1, n_segments=12)
        assert verts.ndim == 2
        assert verts.shape[1] == 3
        assert faces.ndim == 2
        assert faces.shape[1] == 3
        # Should have 2 * n_segments vertices (top + bottom rings)
        assert verts.shape[0] == 24

    def test_ellipsoid_mesh_shape(self):
        """Ellipsoid mesh returns vertices with correct dimensions."""
        center = np.array([0.0, 0.0, 0.0])
        radii = np.array([1.0, 2.0, 3.0])
        verts = ellipsoid_mesh(center, radii, n_segments=8)
        assert verts.ndim == 2
        assert verts.shape[1] == 3
        assert verts.shape[0] > 0

    def test_sphere_mesh(self):
        """Sphere mesh has expected vertex count."""
        center = np.array([0.0, 0.0, 0.0])
        verts = sphere_mesh(center, radius=1.0, n_segments=8)
        assert verts.ndim == 2
        assert verts.shape[1] == 3
        # For n_segments=8: (8+1) * (8+1) = 81 vertices
        assert verts.shape[0] == (8 + 1) * (8 + 1)
