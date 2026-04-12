"""Static plot renderers for the Movement Optimizer."""

from typing import Any
import matplotlib.cm as cm
import numpy as np

from ..models import BodyModel
from ..rendering import Palette
from ..spine_loads import NIOSH_COMPRESSION_LIMIT, spinal_compression, spinal_shear
from ..trajectory import OptimizationResult


def plot_angles(ax: Any, r: OptimizationResult, labels: tuple = Palette.SEG_LABELS) -> None:
    n_dof = min(r.q.shape[1], len(labels))
    for j in range(n_dof):
        ax.plot(
            r.t,
            np.degrees(r.q[:, j]),
            color=Palette.SEG_COLORS[j % len(Palette.SEG_COLORS)],
            lw=2,
            label=labels[j],
        )
    ax.set_xlabel("Time (s)", color=Palette.FG_DIM, fontsize=8)
    ax.set_ylabel("Angle (deg)", color=Palette.FG_DIM, fontsize=8)
    ax.set_title("Joint Angles", color=Palette.FG, fontsize=10)
    ax.legend(
        fontsize=7,
        facecolor=Palette.BG_PANEL,
        edgecolor=Palette.FG_DIM,
        labelcolor=Palette.FG,
    )


def plot_torques(ax: Any, r: OptimizationResult, labels: tuple = Palette.SEG_LABELS) -> None:
    n_dof = min(r.torques.shape[1], len(labels))
    for j in range(n_dof):
        ax.plot(
            r.t,
            r.torques[:, j],
            color=Palette.SEG_COLORS[j % len(Palette.SEG_COLORS)],
            lw=2,
            label=labels[j],
        )
    ax.axhline(0, color=Palette.FG_DIM, lw=0.5, alpha=0.3)
    ax.set_xlabel("Time (s)", color=Palette.FG_DIM, fontsize=8)
    ax.set_ylabel("Torque (N\u00b7m)", color=Palette.FG_DIM, fontsize=8)
    ax.set_title("Joint Torques", color=Palette.FG, fontsize=10)
    ax.legend(
        fontsize=7,
        facecolor=Palette.BG_PANEL,
        edgecolor=Palette.FG_DIM,
        labelcolor=Palette.FG,
    )


def plot_power(ax: Any, r: OptimizationResult, labels: tuple = Palette.SEG_LABELS) -> None:
    n_dof = min(r.power.shape[1], len(labels))
    for j in range(n_dof):
        ax.plot(
            r.t,
            r.power[:, j],
            color=Palette.SEG_COLORS[j % len(Palette.SEG_COLORS)],
            lw=2,
            label=labels[j],
        )
    ax.plot(
        r.t,
        np.sum(r.power, axis=1),
        "--",
        color=Palette.FG,
        lw=2,
        label="Total",
        alpha=0.7,
    )
    ax.axhline(0, color=Palette.FG_DIM, lw=0.5, alpha=0.3)
    ax.set_xlabel("Time (s)", color=Palette.FG_DIM, fontsize=8)
    ax.set_ylabel("Power (W)", color=Palette.FG_DIM, fontsize=8)
    ax.set_title("Joint Power", color=Palette.FG, fontsize=10)
    ax.legend(
        fontsize=7,
        facecolor=Palette.BG_PANEL,
        edgecolor=Palette.FG_DIM,
        labelcolor=Palette.FG,
    )


def plot_com_path(ax: Any, r: OptimizationResult, body: BodyModel) -> None:
    import matplotlib as mpl

    cmap = mpl.colormaps["viridis"] if hasattr(mpl, "colormaps") else cm.get_cmap("viridis")
    colors_t = cmap(np.linspace(0.2, 0.95, len(r.t)))
    for i in range(len(r.t) - 1):
        ax.plot(
            r.com[i : i + 2, 0] * 100,
            r.com[i : i + 2, 1] * 100,
            color=colors_t[i],
            lw=2.5,
        )
    ax.plot(
        r.bar[:, 0] * 100,
        r.bar[:, 1] * 100,
        "-",
        color=Palette.ORANGE,
        lw=1.5,
        alpha=0.7,
        label="Bar path",
    )
    ax.plot(
        [r.com[0, 0] * 100, r.com[-1, 0] * 100],
        [r.com[0, 1] * 100, r.com[-1, 1] * 100],
        "--",
        color=Palette.YELLOW,
        lw=1.2,
        alpha=0.5,
        label="COM straight",
    )
    ax.plot(
        r.com[0, 0] * 100,
        r.com[0, 1] * 100,
        "o",
        color=Palette.RED,
        ms=8,
        label="Start",
    )
    ax.plot(
        r.com[-1, 0] * 100,
        r.com[-1, 1] * 100,
        "s",
        color=Palette.GREEN,
        ms=8,
        label="End",
    )
    ax.axvline(body.inner_heel * 100, color=Palette.GREEN, ls="-", lw=1.2, alpha=0.7)
    ax.axvline(body.inner_toe * 100, color=Palette.GREEN, ls="-", lw=1.2, alpha=0.7)
    ax.axvline(body.heel_x * 100, color=Palette.ORANGE, ls=":", lw=1, alpha=0.4)
    ax.axvline(body.toe_x * 100, color=Palette.ORANGE, ls=":", lw=1, alpha=0.4)
    ax.set_xlabel("Horizontal (cm)", color=Palette.FG_DIM, fontsize=8)
    ax.set_ylabel("Height (cm)", color=Palette.FG_DIM, fontsize=8)
    ax.set_title("COM & Bar Path", color=Palette.FG, fontsize=10)
    ax.legend(
        fontsize=6,
        facecolor=Palette.BG_PANEL,
        edgecolor=Palette.FG_DIM,
        labelcolor=Palette.FG,
    )


def plot_com_balance(ax: Any, r: OptimizationResult, body: BodyModel) -> None:
    ax.plot(r.t, r.com[:, 0] * 100, color=Palette.ACCENT, lw=2, label="COM x")
    ax.axhline(body.inner_heel * 100, color=Palette.GREEN, ls="-", lw=1.5, alpha=0.8)
    ax.axhline(body.inner_toe * 100, color=Palette.GREEN, ls="-", lw=1.5, alpha=0.8)
    ax.fill_between(
        r.t,
        body.inner_heel * 100,
        body.inner_toe * 100,
        alpha=0.12,
        color=Palette.GREEN,
        label="Inner BOS (60%)",
    )
    ax.axhline(body.heel_x * 100, color=Palette.ORANGE, ls=":", lw=1, alpha=0.5)
    ax.axhline(body.toe_x * 100, color=Palette.ORANGE, ls=":", lw=1, alpha=0.5)
    ax.fill_between(
        r.t,
        body.heel_x * 100,
        body.toe_x * 100,
        alpha=0.04,
        color=Palette.ORANGE,
        label="Full BOS",
    )
    ax.axhline(body.inner_center * 100, color=Palette.GREEN, ls="--", lw=0.8, alpha=0.5)
    ax.set_xlabel("Time (s)", color=Palette.FG_DIM, fontsize=8)
    ax.set_ylabel("COM x (cm)", color=Palette.FG_DIM, fontsize=8)
    ax.set_title("COM Balance", color=Palette.FG, fontsize=10)
    ax.legend(
        fontsize=6,
        facecolor=Palette.BG_PANEL,
        edgecolor=Palette.FG_DIM,
        labelcolor=Palette.FG,
    )


def plot_spine_loads(ax_comp: Any, ax_shear: Any, r: OptimizationResult, body: BodyModel, bar_mass: float, name: str) -> None:
    exercise_type = name.lower().replace(" ", "_")
    if exercise_type == "bottoms_up_squat":
        exercise_type = "squat"

    comp = spinal_compression(r.q, r.qd, r.qdd, body, bar_mass, exercise_type)
    shear = spinal_shear(r.q, r.qd, r.qdd, body, bar_mass, exercise_type)

    ax = ax_comp
    ax.plot(r.t, comp, color=Palette.RED, lw=2, label="L5/S1 compression")
    ax.axhline(
        NIOSH_COMPRESSION_LIMIT,
        color=Palette.YELLOW,
        ls="--",
        lw=1.5,
        alpha=0.8,
        label=f"NIOSH limit ({NIOSH_COMPRESSION_LIMIT:.0f} N)",
    )
    ax.fill_between(
        r.t,
        NIOSH_COMPRESSION_LIMIT,
        comp,
        where=comp > NIOSH_COMPRESSION_LIMIT,  # type: ignore[arg-type]
        alpha=0.3,
        color=Palette.RED,
        label="Exceeds limit",
    )
    ax.set_xlabel("Time (s)", color=Palette.FG_DIM, fontsize=8)
    ax.set_ylabel("Force (N)", color=Palette.FG_DIM, fontsize=8)
    ax.set_title("Spinal Compression (L5/S1)", color=Palette.FG, fontsize=10)
    ax.legend(
        fontsize=6,
        facecolor=Palette.BG_PANEL,
        edgecolor=Palette.FG_DIM,
        labelcolor=Palette.FG,
    )

    ax = ax_shear
    ax.plot(r.t, shear, color=Palette.ORANGE, lw=2, label="L5/S1 shear")
    ax.axhline(0, color=Palette.FG_DIM, lw=0.5, alpha=0.3)
    ax.set_xlabel("Time (s)", color=Palette.FG_DIM, fontsize=8)
    ax.set_ylabel("Force (N)", color=Palette.FG_DIM, fontsize=8)
    ax.set_title("Spinal Shear (L5/S1)", color=Palette.FG, fontsize=10)
    ax.legend(
        fontsize=6,
        facecolor=Palette.BG_PANEL,
        edgecolor=Palette.FG_DIM,
        labelcolor=Palette.FG,
    )
