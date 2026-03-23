"""3D base of support as convex polygon from bilateral foot contact.

The BOS is represented as a bounding rectangle in the (x, y) ground
plane, formed by the combined footprint of left and right feet.  An
inner zone (configurable fraction) is also maintained for balance
margin checks.

Design Principles:
    DBC  -- public methods check containment clearly.
    DRY  -- inner zone reuses the same rectangle logic.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


class BaseOfSupport3D:
    """3D base of support as convex polygon from bilateral foot contact."""

    def __init__(
        self,
        stance_width: float = 0.30,
        foot_length: float = 0.26,
        foot_width: float = 0.10,
        inner_fraction: float = 0.60,
    ):
        self.stance_width = stance_width
        half_sw = stance_width / 2
        heel_x = -0.05 * foot_length
        toe_x = 0.95 * foot_length
        half_fw = foot_width / 2

        # Foot corners: (x_forward, y_lateral)
        # Left foot at y = +half_sw, right foot at y = -half_sw
        self.polygon = np.array(
            [
                [heel_x, -half_sw - half_fw],  # right heel outer
                [heel_x, -half_sw + half_fw],  # right heel inner
                [toe_x, -half_sw + half_fw],  # right toe inner
                [toe_x, -half_sw - half_fw],  # right toe outer
                [toe_x, half_sw + half_fw],  # left toe outer
                [toe_x, half_sw - half_fw],  # left toe inner
                [heel_x, half_sw - half_fw],  # left heel inner
                [heel_x, half_sw + half_fw],  # left heel outer
            ]
        )

        # Compute bounding rectangle
        self.x_min = heel_x
        self.x_max = toe_x
        self.y_min = -half_sw - half_fw
        self.y_max = half_sw + half_fw

        # Inner zone (shrink by margin)
        margin_x = (1.0 - inner_fraction) / 2 * (toe_x - heel_x)
        margin_y = (1.0 - inner_fraction) / 2 * (self.y_max - self.y_min)
        self.inner_x_min = self.x_min + margin_x
        self.inner_x_max = self.x_max - margin_x
        self.inner_y_min = self.y_min + margin_y
        self.inner_y_max = self.y_max - margin_y

        self.center = np.array(
            [
                (self.x_min + self.x_max) / 2,
                (self.y_min + self.y_max) / 2,
            ]
        )

    def contains(self, point_xy: NDArray) -> bool:
        """Return True if the (x, y) point is inside the outer BOS boundary."""
        return bool(
            self.x_min <= point_xy[0] <= self.x_max and self.y_min <= point_xy[1] <= self.y_max
        )

    def inner_contains(self, point_xy: NDArray) -> bool:
        """Return True if the (x, y) point is inside the inner (safe) zone."""
        return bool(
            self.inner_x_min <= point_xy[0] <= self.inner_x_max
            and self.inner_y_min <= point_xy[1] <= self.inner_y_max
        )

    def distance_to_boundary(self, point_xy: NDArray) -> float:
        """Signed distance to the outer BOS boundary.

        Returns:
            Negative if inside, positive if outside.
        """
        dx = max(self.x_min - point_xy[0], 0, point_xy[0] - self.x_max)
        dy = max(self.y_min - point_xy[1], 0, point_xy[1] - self.y_max)
        if dx == 0 and dy == 0:
            # Inside: return negative distance to nearest edge
            return -min(
                point_xy[0] - self.x_min,
                self.x_max - point_xy[0],
                point_xy[1] - self.y_min,
                self.y_max - point_xy[1],
            )
        return float(np.sqrt(dx**2 + dy**2))
