"""3D math utilities: rotations, transforms, and mesh generation.

Pure functions operating on NumPy arrays.  No mutable state.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

# ---------------------------------------------------------------------------
# Rotation matrices
# ---------------------------------------------------------------------------


def rotation_x(angle_rad: float) -> NDArray:
    """3x3 rotation about the X axis."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, c, -s],
            [0.0, s, c],
        ]
    )


def rotation_y(angle_rad: float) -> NDArray:
    """3x3 rotation about the Y axis."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array(
        [
            [c, 0.0, s],
            [0.0, 1.0, 0.0],
            [-s, 0.0, c],
        ]
    )


def rotation_z(angle_rad: float) -> NDArray:
    """3x3 rotation about the Z axis."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array(
        [
            [c, -s, 0.0],
            [s, c, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )


def rotation_axis_angle(axis: NDArray, angle_rad: float) -> NDArray:
    """3x3 rotation via Rodrigues' formula for arbitrary *axis*."""
    axis = axis / np.linalg.norm(axis)
    K = np.array(
        [
            [0.0, -axis[2], axis[1]],
            [axis[2], 0.0, -axis[0]],
            [-axis[1], axis[0], 0.0],
        ]
    )
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.eye(3) + s * K + (1.0 - c) * (K @ K)


# ---------------------------------------------------------------------------
# Homogeneous transforms
# ---------------------------------------------------------------------------


def homogeneous_transform(R: NDArray, t: NDArray) -> NDArray:
    """Build a 4x4 homogeneous transform from rotation *R* and translation *t*."""
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t
    return T


def transform_point(T: NDArray, p: NDArray) -> NDArray:
    """Apply 4x4 transform *T* to a 3-vector *p*, returning a 3-vector."""
    p_h = np.array([p[0], p[1], p[2], 1.0])
    result = T @ p_h
    return result[:3]


# ---------------------------------------------------------------------------
# Mesh generation
# ---------------------------------------------------------------------------


def cylinder_mesh(
    p0: NDArray,
    p1: NDArray,
    radius: float,
    n_segments: int = 12,
) -> tuple[NDArray, NDArray]:
    """Generate a cylinder mesh between two 3D points.

    Returns (vertices, faces) where vertices is (2*n_segments, 3)
    and faces is (2*n_segments, 3) triangles.
    """
    # Build a local frame along the cylinder axis
    axis = p1 - p0
    length = np.linalg.norm(axis)
    axis = np.array([0.0, 0.0, 1.0]) if length < 1e-12 else axis / length

    # Find two orthogonal vectors
    if abs(axis[0]) < 0.9:
        perp = np.cross(axis, np.array([1.0, 0.0, 0.0]))
    else:
        perp = np.cross(axis, np.array([0.0, 1.0, 0.0]))
    perp = perp / np.linalg.norm(perp)
    perp2 = np.cross(axis, perp)

    # Generate circle vertices at bottom and top
    angles = np.linspace(0, 2 * math.pi, n_segments, endpoint=False)
    verts = np.zeros((2 * n_segments, 3))
    for i, a in enumerate(angles):
        offset = radius * (math.cos(a) * perp + math.sin(a) * perp2)
        verts[i] = p0 + offset
        verts[n_segments + i] = p1 + offset

    # Triangulate the side walls
    faces = []
    for i in range(n_segments):
        j = (i + 1) % n_segments
        # Two triangles per quad
        faces.append([i, j, n_segments + i])
        faces.append([j, n_segments + j, n_segments + i])

    return verts, np.array(faces, dtype=int)


def ellipsoid_mesh(
    center: NDArray,
    radii: NDArray,
    n_segments: int = 8,
) -> NDArray:
    """Generate vertices for an ellipsoid at *center* with semi-axes *radii*.

    Returns vertices array of shape (N, 3).
    """
    u = np.linspace(0, 2 * math.pi, n_segments + 1)
    v = np.linspace(0, math.pi, n_segments + 1)
    uu, vv = np.meshgrid(u, v)

    x = center[0] + radii[0] * np.cos(uu) * np.sin(vv)
    y = center[1] + radii[1] * np.sin(uu) * np.sin(vv)
    z = center[2] + radii[2] * np.cos(vv)

    verts = np.stack([x.ravel(), y.ravel(), z.ravel()], axis=1)
    return verts


def sphere_mesh(
    center: NDArray,
    radius: float,
    n_segments: int = 8,
) -> NDArray:
    """Generate vertices for a sphere. Convenience wrapper around ellipsoid_mesh."""
    return ellipsoid_mesh(center, np.array([radius, radius, radius]), n_segments)
