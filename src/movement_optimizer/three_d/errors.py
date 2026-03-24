"""Shared unsupported-feature errors for the 3D backend."""

from __future__ import annotations


def unsupported_3d_message(feature: str) -> str:
    """Return a consistent fail-fast message for unsupported 3D features."""
    return (
        f"{feature} is not yet implemented for the 16-DOF 3D backend. "
        "Use the 2D optimizer (movement_optimizer.trajectory.TrajectoryOptimizer) "
        "for production trajectory optimization."
    )


def unsupported_3d_error(feature: str) -> NotImplementedError:
    """Return the repository-standard NotImplementedError for 3D stubs."""
    return NotImplementedError(unsupported_3d_message(feature))
