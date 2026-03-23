"""Matplotlib rendering helpers for the animation panel.

Separated from the GUI so rendering logic can be tested independently
and reused with different frontends.

Design Principles:
    DRY  -- common drawing patterns are factored into class methods.
    LoD  -- renderers accept only the data they need, not whole objects.
"""

from __future__ import annotations

from matplotlib.axes import Axes
from matplotlib.patches import Circle, Rectangle
from numpy.typing import NDArray

from .constants import BAR_RADIUS_M, PLATE_RADIUS_STD_M


class Palette:
    """Centralised colour definitions."""

    BG = "#1e1e2e"
    BG_PANEL = "#2a2a3d"
    BG_INPUT = "#363650"
    BG_PLOT = "#1a1a2e"
    FG = "#e0e0e0"
    FG_DIM = "#8888aa"
    ACCENT = "#7c6ff7"
    ACCENT2 = "#9d93f9"
    GREEN = "#4ec9b0"
    RED = "#f44747"
    BLUE = "#569cd6"
    ORANGE = "#ffb74d"
    YELLOW = "#ffd54f"
    SEG_COLORS = ("#569cd6", "#f44747", "#4ec9b0")
    SEG_LABELS = ("Lower leg", "Upper leg", "Torso")


class BarbellRenderer:
    """Draw barbell as sagittal cross-section."""

    BAR_ALPHA = 0.50
    PLATE_ALPHA = 0.55
    BAR_COLOR = "#d4a017"
    PLATE_COLOR = "#777777"

    @classmethod
    def draw(cls, ax: Axes, position: tuple[float, float]) -> None:
        x, y = position
        cls._draw_bar_circle(ax, x, y)
        cls._draw_plate_rect(ax, x, y)

    @classmethod
    def _draw_bar_circle(cls, ax: Axes, x: float, y: float) -> None:
        ax.add_patch(
            Circle(
                (x, y),
                BAR_RADIUS_M,
                facecolor=cls.BAR_COLOR,
                edgecolor="#8B7500",
                linewidth=1.5,
                alpha=cls.BAR_ALPHA,
                zorder=8,
            )
        )

    @classmethod
    def _draw_plate_rect(cls, ax: Axes, x: float, y: float) -> None:
        pw = 0.025
        ax.add_patch(
            Rectangle(
                (x - pw / 2, y - PLATE_RADIUS_STD_M),
                pw,
                2 * PLATE_RADIUS_STD_M,
                facecolor=cls.PLATE_COLOR,
                edgecolor="#555",
                linewidth=1,
                alpha=cls.PLATE_ALPHA,
                zorder=7,
            )
        )


class BodyRenderer:
    """Draw the stick-figure body on a matplotlib Axes."""

    @classmethod
    def draw_ground(cls, ax: Axes, heel_x: float, toe_x: float) -> None:
        ax.plot([-0.7, 0.7], [0, 0], color=Palette.FG_DIM, lw=2, alpha=0.3)
        ax.plot(
            [heel_x, toe_x], [0, 0],
            color=Palette.ORANGE, lw=4, solid_capstyle="round", alpha=0.5,
        )

    @classmethod
    def draw_ghost(
        cls, ax: Axes, joints: dict[str, NDArray], alpha: float = 0.10
    ) -> None:
        pts = [joints["ankle"], joints["knee"], joints["hip"], joints["shoulder"]]
        for k in range(3):
            ax.plot(
                [pts[k][0], pts[k + 1][0]], [pts[k][1], pts[k + 1][1]],
                "-", color=Palette.FG, lw=2, alpha=alpha,
            )

    @classmethod
    def draw_segments(cls, ax: Axes, joints: dict[str, NDArray]) -> None:
        pts = [joints["ankle"], joints["knee"], joints["hip"], joints["shoulder"]]
        for k in range(3):
            ax.plot(
                [pts[k][0], pts[k + 1][0]], [pts[k][1], pts[k + 1][1]],
                "-", color=Palette.SEG_COLORS[k], lw=5, solid_capstyle="round",
            )
        for pt in pts:
            ax.plot(
                pt[0], pt[1], "o",
                color=Palette.FG, ms=7, markeredgecolor="#333", markeredgewidth=1.2,
            )

    @classmethod
    def draw_arms(cls, ax: Axes, shoulder: NDArray, arm_length: float) -> None:
        hand_y = shoulder[1] - arm_length
        ax.plot(
            [shoulder[0], shoulder[0]], [shoulder[1], hand_y],
            "-", color="#b0b0b0", lw=3, solid_capstyle="round",
        )
        ax.plot(shoulder[0], hand_y, "o", color=Palette.FG, ms=5)

    @classmethod
    def draw_com_marker(cls, ax: Axes, com: NDArray) -> None:
        ax.plot(com[0], com[1], "+", color=Palette.YELLOW, ms=12, mew=2)
        ax.annotate(
            "COM", (com[0], com[1]),
            xytext=(8, -4), textcoords="offset points",
            fontsize=7, color=Palette.YELLOW,
        )

    @classmethod
    def draw_bar_trace(cls, ax: Axes, bar_traj: NDArray, current_idx: int) -> None:
        ax.plot(
            bar_traj[:, 0], bar_traj[:, 1],
            "-", color=Palette.ORANGE, lw=1, alpha=0.25,
        )
        ax.plot(
            bar_traj[current_idx, 0], bar_traj[current_idx, 1],
            "x", color=Palette.ORANGE, ms=6, mew=1.5, alpha=0.7,
        )


def style_axis(ax: Axes) -> None:
    """Apply the dark-theme styling to a matplotlib Axes."""
    ax.set_facecolor(Palette.BG_PLOT)
    ax.tick_params(colors=Palette.FG_DIM, which="both", labelsize=8)
    for sp in ("bottom", "left"):
        ax.spines[sp].set_color(Palette.FG_DIM)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.grid(True, alpha=0.12, color=Palette.FG_DIM)
