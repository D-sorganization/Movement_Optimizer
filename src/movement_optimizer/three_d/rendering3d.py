"""3D rendering using matplotlib Axes3D with mplot3d Poly3DCollection.

Provides a professional 3D body renderer for visualising the 16-DOF
bilateral body model in three dimensions.

Design Principles:
    DRY  -- common drawing patterns are factored into class methods.
    LoD  -- renderers accept only the data they need, not whole objects.
"""

from __future__ import annotations

from typing import ClassVar

import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from numpy.typing import NDArray

from .math3d import cylinder_mesh


class Renderer3D:
    """Professional 3D body renderer using matplotlib."""

    # Segment colours (matching 2D palette)
    COLORS: ClassVar[dict[str, str]] = {
        "shank": "#569cd6",
        "thigh": "#f44747",
        "torso": "#4ec9b0",
        "pelvis": "#4ec9b0",
        "upper_arm": "#ffb74d",
        "forearm": "#ffb74d",
        "head": "#e0e0e0",
        "foot": "#8888aa",
        "hand": "#e0e0e0",
    }

    def draw_segment(
        self,
        ax,
        p0: NDArray,
        p1: NDArray,
        radius: float = 0.04,
        color: str = "blue",
        alpha: float = 0.7,
    ) -> None:
        """Draw a cylinder between two 3D points."""
        verts, faces = cylinder_mesh(p0, p1, radius, n_segments=10)
        polys = [[verts[f[j]] for j in range(len(f))] for f in faces]
        collection = Poly3DCollection(polys, alpha=alpha, facecolor=color, edgecolor="none")
        ax.add_collection3d(collection)

    def draw_joint(
        self,
        ax,
        center: NDArray,
        radius: float = 0.03,
        color: str = "white",
    ) -> None:
        """Draw a sphere at a joint location."""
        u = np.linspace(0, 2 * np.pi, 8)
        v = np.linspace(0, np.pi, 6)
        x = center[0] + radius * np.outer(np.cos(u), np.sin(v))
        y = center[1] + radius * np.outer(np.sin(u), np.sin(v))
        z = center[2] + radius * np.outer(np.ones_like(u), np.cos(v))
        ax.plot_surface(x, y, z, color=color, alpha=0.8)

    def draw_ground_plane(self, ax, size: float = 1.0) -> None:
        """Draw a semi-transparent ground plane at z=0."""
        xx, yy = np.meshgrid([-size, size], [-size, size])
        zz = np.zeros_like(xx)
        ax.plot_surface(xx, yy, zz, alpha=0.1, color="#888888")

    def draw_barbell(
        self,
        ax,
        position: NDArray,
        bar_length: float = 2.2,
        bar_radius: float = 0.025,
        plate_radius: float = 0.225,
    ) -> None:
        """Draw barbell as cylinder with plate discs at ends."""
        half = bar_length / 2
        # Bar shaft along y-axis (lateral)
        p0 = position + np.array([0, -half, 0])
        p1 = position + np.array([0, half, 0])
        self.draw_segment(ax, p0, p1, radius=bar_radius, color="#c0c0c0", alpha=0.6)
        # Plates at each end
        for y_off in [-half, half]:
            center = position + np.array([0, y_off, 0])
            self.draw_joint(ax, center, radius=plate_radius, color="#555555")

    def draw_body(self, ax, joint_positions: dict[str, NDArray], body) -> None:
        """Draw the full 3D body from joint positions."""
        # Define segment connections
        connections = [
            ("ankle_l", "knee_l", "shank"),
            ("knee_l", "hip_l", "thigh"),
            ("ankle_r", "knee_r", "shank"),
            ("knee_r", "hip_r", "thigh"),
            ("hip_l", "pelvis_center", "pelvis"),
            ("hip_r", "pelvis_center", "pelvis"),
            ("pelvis_center", "shoulder_center", "torso"),
            ("shoulder_center", "head_top", "head"),
            ("shoulder_l", "elbow_l", "upper_arm"),
            ("elbow_l", "wrist_l", "forearm"),
            ("shoulder_r", "elbow_r", "upper_arm"),
            ("elbow_r", "wrist_r", "forearm"),
        ]
        for j1, j2, seg_type in connections:
            if j1 in joint_positions and j2 in joint_positions:
                color = self.COLORS.get(seg_type, "#888888")
                radius = 0.035 if seg_type in ("torso", "thigh") else 0.025
                self.draw_segment(
                    ax,
                    joint_positions[j1],
                    joint_positions[j2],
                    radius=radius,
                    color=color,
                )

        # Draw joints
        for _name, pos in joint_positions.items():
            self.draw_joint(ax, pos, radius=0.02, color="white")

    def setup_axes(self, ax, title: str = "") -> None:
        """Configure 3D axes for body viewing."""
        ax.set_xlim(-0.8, 0.8)
        ax.set_ylim(-0.8, 0.8)
        ax.set_zlim(-0.1, 2.0)
        ax.set_xlabel("X (forward)")
        ax.set_ylabel("Y (lateral)")
        ax.set_zlabel("Z (up)")
        ax.set_title(title, fontsize=10)
        ax.view_init(elev=20, azim=-60)
