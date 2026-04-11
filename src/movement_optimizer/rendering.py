"""Matplotlib rendering helpers for the animation panel.

Separated from the GUI so rendering logic can be tested independently
and reused with different frontends.

Design Principles:
    DRY  -- common drawing patterns are factored into class methods.
    LoD  -- renderers accept only the data they need, not whole objects.
"""

from __future__ import annotations

import numpy as np
from matplotlib.axes import Axes
from matplotlib.patches import Circle
from numpy.typing import NDArray

from .constants import BAR_RADIUS_M, LENGTH_FRAC, PLATE_RADIUS_STD_M

# Neck length as a fraction of body height (used by BodyRenderer)
NECK_LENGTH_FRAC: float = LENGTH_FRAC["neck"]


try:
    from plot_theme.themes import DEFAULT_THEME, get_theme

    theme = get_theme(DEFAULT_THEME)

    class Palette:
        BG = theme.figure_facecolor
        BG_PANEL = theme.axes_facecolor
        BG_INPUT = theme.axes_facecolor
        BG_PLOT = theme.axes_facecolor
        FG = theme.text_color
        FG_DIM = theme.tick_color
        ACCENT = theme.primary_colors[0] if theme.primary_colors else "#7c6ff7"
        ACCENT2 = theme.primary_colors[1] if len(theme.primary_colors) > 1 else "#9d93f9"
        GREEN = theme.accent_color
        RED = theme.secondary_color
        BLUE = theme.primary_color
        ORANGE = theme.accent_colors[1] if len(theme.accent_colors) > 1 else "#ffb74d"
        YELLOW = theme.accent_colors[2] if len(theme.accent_colors) > 2 else "#ffd54f"
        SEG_COLORS = (
            theme.primary_colors[0] if len(theme.primary_colors) > 0 else "#569cd6",
            theme.secondary_colors[0] if len(theme.secondary_colors) > 0 else "#f44747",
            theme.accent_colors[0] if len(theme.accent_colors) > 0 else "#4ec9b0",
        )
        SEG_LABELS = ("Lower leg", "Upper leg", "Torso")
        BENCH_LABELS = ("Shoulder", "Elbow", "Wrist")

except ImportError:
    # Fallback if ud-tools isn't installed
    class Palette:  # type: ignore[no-redef]
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
        BENCH_LABELS = ("Shoulder", "Elbow", "Wrist")


class BarbellRenderer:
    """Draw barbell as seen from the side (sagittal plane).

    From the side, a loaded barbell appears as a large circle (the plate)
    with a smaller concentric circle (the bar shaft).
    """

    BAR_ALPHA = 0.60
    PLATE_ALPHA = 0.50
    BAR_COLOR = "#c0c0c0"
    BAR_EDGE = "#888888"
    PLATE_COLOR = "#444444"
    PLATE_EDGE = "#333333"

    @classmethod
    def draw(cls, ax: Axes, position: tuple[float, float]) -> None:
        x, y = position
        cls._draw_plate_circle(ax, x, y)
        cls._draw_bar_circle(ax, x, y)

    @classmethod
    def _draw_plate_circle(cls, ax: Axes, x: float, y: float) -> None:
        """Outer plate circle — the bumper plate seen from the side."""
        ax.add_patch(
            Circle(
                (x, y),
                PLATE_RADIUS_STD_M,
                facecolor=cls.PLATE_COLOR,
                edgecolor=cls.PLATE_EDGE,
                linewidth=1.5,
                alpha=cls.PLATE_ALPHA,
                zorder=7,
            )
        )

    @classmethod
    def _draw_bar_circle(cls, ax: Axes, x: float, y: float) -> None:
        """Inner bar shaft circle — the bar cross-section."""
        ax.add_patch(
            Circle(
                (x, y),
                BAR_RADIUS_M,
                facecolor=cls.BAR_COLOR,
                edgecolor=cls.BAR_EDGE,
                linewidth=1.5,
                alpha=cls.BAR_ALPHA,
                zorder=8,
            )
        )


class BodyRenderer:
    """Draw the stick-figure body on a matplotlib Axes."""

    @classmethod
    def draw_ground(cls, ax: Axes, heel_x: float, toe_x: float) -> None:
        ax.plot([-0.7, 0.7], [0, 0], color=Palette.FG_DIM, lw=2, alpha=0.3)
        ax.plot(
            [heel_x, toe_x],
            [0, 0],
            color=Palette.ORANGE,
            lw=4,
            solid_capstyle="round",
            alpha=0.5,
        )

    @classmethod
    def draw_ghost(
        cls,
        ax: Axes,
        joints: dict[str, NDArray],
        alpha: float = 0.10,
        body_height: float = 1.75,
    ) -> None:
        pts = [joints["ankle"], joints["knee"], joints["hip"], joints["shoulder"]]
        for k in range(3):
            ax.plot(
                [pts[k][0], pts[k + 1][0]],
                [pts[k][1], pts[k + 1][1]],
                "-",
                color=Palette.FG,
                lw=2,
                alpha=alpha,
            )
        # Ghost neck + head
        neck_length = NECK_LENGTH_FRAC * body_height
        shoulder = joints["shoulder"]
        neck_top = np.array([shoulder[0], shoulder[1] + neck_length])
        ax.plot(
            [shoulder[0], neck_top[0]],
            [shoulder[1], neck_top[1]],
            "-",
            color=Palette.FG,
            lw=2,
            alpha=alpha,
        )
        ax.add_patch(
            Circle(
                (neck_top[0], neck_top[1] + cls.HEAD_RADIUS),
                cls.HEAD_RADIUS,
                facecolor=Palette.FG,
                edgecolor="none",
                alpha=alpha,
                zorder=6,
            )
        )

    # Linewidths per segment: shank (thinner), thigh (medium), torso (thick)
    SEG_LINEWIDTHS = (6, 9, 12)
    HEAD_RADIUS = 0.10  # metres

    @classmethod
    def draw_segments(cls, ax: Axes, joints: dict[str, NDArray], body_height: float = 1.75) -> None:
        pts = [joints["ankle"], joints["knee"], joints["hip"], joints["shoulder"]]
        for k in range(3):
            ax.plot(
                [pts[k][0], pts[k + 1][0]],
                [pts[k][1], pts[k + 1][1]],
                "-",
                color=Palette.SEG_COLORS[k],
                lw=cls.SEG_LINEWIDTHS[k],
                solid_capstyle="round",
            )
        for pt in pts:
            ax.plot(
                pt[0],
                pt[1],
                "o",
                color=Palette.FG,
                ms=7,
                markeredgecolor="#333",
                markeredgewidth=1.2,
            )
        # Draw neck segment from shoulder upward
        neck_length = NECK_LENGTH_FRAC * body_height
        shoulder = joints["shoulder"]
        neck_top = np.array([shoulder[0], shoulder[1] + neck_length])
        ax.plot(
            [shoulder[0], neck_top[0]],
            [shoulder[1], neck_top[1]],
            "-",
            color="#d4a574",
            lw=5,
            solid_capstyle="round",
        )
        # Draw head at top of neck
        cls.draw_head(ax, neck_top)

    @classmethod
    def draw_head(cls, ax: Axes, neck_top: NDArray) -> None:
        """Draw a circle representing the head above the top of the neck."""
        head_center = (neck_top[0], neck_top[1] + cls.HEAD_RADIUS)
        ax.add_patch(
            Circle(
                head_center,
                cls.HEAD_RADIUS,
                facecolor="#d4a574",
                edgecolor="#333",
                linewidth=1.2,
                alpha=0.85,
                zorder=6,
            )
        )

    @classmethod
    def draw_arms(cls, ax: Axes, shoulder: NDArray, arm_length: float) -> None:
        hand_y = shoulder[1] - arm_length
        ax.plot(
            [shoulder[0], shoulder[0]],
            [shoulder[1], hand_y],
            "-",
            color="#b0b0b0",
            lw=3,
            solid_capstyle="round",
        )
        ax.plot(shoulder[0], hand_y, "o", color=Palette.FG, ms=5)

    @classmethod
    def draw_com_marker(cls, ax: Axes, com: NDArray) -> None:
        ax.plot(com[0], com[1], "+", color=Palette.YELLOW, ms=12, mew=2)
        ax.annotate(
            "COM",
            (com[0], com[1]),
            xytext=(8, -4),
            textcoords="offset points",
            fontsize=7,
            color=Palette.YELLOW,
        )

    @classmethod
    def draw_bar_trace(cls, ax: Axes, bar_traj: NDArray, current_idx: int) -> None:
        ax.plot(
            bar_traj[:, 0],
            bar_traj[:, 1],
            "-",
            color=Palette.ORANGE,
            lw=1,
            alpha=0.25,
        )
        ax.plot(
            bar_traj[current_idx, 0],
            bar_traj[current_idx, 1],
            "x",
            color=Palette.ORANGE,
            ms=6,
            mew=1.5,
            alpha=0.7,
        )


def style_axis(ax: Axes) -> None:
    """Apply the dark-theme styling to a matplotlib Axes."""
    try:
        from plot_theme.integration import style_axis as shared_style_axis

        shared_style_axis(ax)
    except ImportError:
        ax.set_facecolor(Palette.BG_PLOT)
        ax.tick_params(colors=Palette.FG_DIM, which="both", labelsize=8)
        for sp in ("bottom", "left"):
            ax.spines[sp].set_color(Palette.FG_DIM)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.grid(True, alpha=0.12, color=Palette.FG_DIM)
