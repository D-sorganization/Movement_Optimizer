"""ExerciseTab -- individual tab logic for movement visualizations."""

from __future__ import annotations

import logging
from typing import Any

import matplotlib.cm as cm
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import (  # type: ignore[attr-defined]
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from ..constants import PLATE_RADIUS_STD_M
from ..models import BodyModel
from ..rendering import BarbellRenderer, BodyRenderer, Palette, style_axis
from ..spine_loads import NIOSH_COMPRESSION_LIMIT, spinal_compression, spinal_shear
from ..trajectory import OptimizationResult

logger = logging.getLogger(__name__)


class ExerciseTab(QWidget):
    """Single exercise tab with animation and analysis plots."""

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name = name
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.fig = Figure(figsize=(11, 9), facecolor=Palette.BG)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)

        self._create_axes()

    def _create_axes(self) -> None:
        gs = GridSpec(
            3,
            4,
            figure=self.fig,
            height_ratios=[3, 1, 1],
            hspace=0.40,
            wspace=0.40,
            left=0.06,
            right=0.97,
            top=0.93,
            bottom=0.06,
        )
        self.axes = {
            "anim": self.fig.add_subplot(gs[0, 0:3]),
            "com_path": self.fig.add_subplot(gs[0, 3]),
            "angles": self.fig.add_subplot(gs[1, 0]),
            "torques": self.fig.add_subplot(gs[1, 1]),
            "power": self.fig.add_subplot(gs[1, 2]),
            "com_time": self.fig.add_subplot(gs[1, 3]),
            "spine_comp": self.fig.add_subplot(gs[2, 0:2]),
            "spine_shear": self.fig.add_subplot(gs[2, 2:4]),
        }
        for ax in self.axes.values():
            style_axis(ax)

        self.axes["anim"].set_aspect("equal", adjustable="datalim")
        self.axes["anim"].set_xlim(-0.9, 0.9)
        self.axes["anim"].set_ylim(-0.15, 1.8)
        self.axes["anim"].text(
            0.5,
            0.5,
            "Click Optimize to begin",
            ha="center",
            va="center",
            fontsize=13,
            color=Palette.FG_DIM,
            style="italic",
            transform=self.axes["anim"].transAxes,
        )
        self.fig.suptitle(
            f"{self.name} Optimization",
            color=Palette.FG,
            fontsize=13,
            fontweight="bold",
        )
        self.canvas.draw()

    def draw_all_plots(
        self,
        result: OptimizationResult,
        body: BodyModel,
        bar_mass: float,
        exercise_type: str = "squat",
    ) -> None:
        for k in self.axes:
            if k != "anim":
                self.axes[k].clear()
                style_axis(self.axes[k])

        is_bench = exercise_type == "bench_press"
        labels = Palette.BENCH_LABELS if is_bench else Palette.SEG_LABELS

        self._plot_angles(result, labels)
        self._plot_torques(result, labels)
        self._plot_power(result, labels)
        self._plot_com_path(result, body)
        self._plot_com_balance(result, body)
        self._plot_spine_loads(result, body, bar_mass)

        self.fig.suptitle(
            f"{self.name}  |  {body.body_mass:.0f} kg body, {bar_mass:.0f} kg barbell",
            color=Palette.FG,
            fontsize=12,
            fontweight="bold",
        )
        self.canvas.draw()

    def _plot_angles(self, r: OptimizationResult, labels: tuple = Palette.SEG_LABELS) -> None:
        ax = self.axes["angles"]
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

    def _plot_torques(self, r: OptimizationResult, labels: tuple = Palette.SEG_LABELS) -> None:
        ax = self.axes["torques"]
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

    def _plot_power(self, r: OptimizationResult, labels: tuple = Palette.SEG_LABELS) -> None:
        ax = self.axes["power"]
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

    def _plot_com_path(self, r: OptimizationResult, body: BodyModel) -> None:
        ax = self.axes["com_path"]
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
        ax.plot(r.com[0, 0] * 100, r.com[0, 1] * 100, "o", color=Palette.RED, ms=8, label="Start")
        ax.plot(r.com[-1, 0] * 100, r.com[-1, 1] * 100, "s", color=Palette.GREEN, ms=8, label="End")
        # Show inner BOS bounds (middle 60%)
        ax.axvline(body.inner_heel * 100, color=Palette.GREEN, ls="-", lw=1.2, alpha=0.7)
        ax.axvline(body.inner_toe * 100, color=Palette.GREEN, ls="-", lw=1.2, alpha=0.7)
        # Show outer BOS bounds
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

    def _plot_com_balance(self, r: OptimizationResult, body: BodyModel) -> None:
        ax = self.axes["com_time"]
        ax.plot(r.t, r.com[:, 0] * 100, color=Palette.ACCENT, lw=2, label="COM x")
        # Inner BOS bounds (middle 60%) -- the hard constraint zone
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
        # Outer BOS bounds
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

    def _plot_spine_loads(self, r: OptimizationResult, body: BodyModel, bar_mass: float) -> None:
        """Plot spinal compression and shear over time."""
        exercise_type = self.name.lower().replace(" ", "_")
        if exercise_type == "bottoms_up_squat":
            exercise_type = "squat"

        comp = spinal_compression(r.q, r.qd, r.qdd, body, bar_mass, exercise_type)
        shear = spinal_shear(r.q, r.qd, r.qdd, body, bar_mass, exercise_type)

        # Compression plot
        ax = self.axes["spine_comp"]
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

        # Shear plot
        ax = self.axes["spine_shear"]
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

    def draw_anim_frame(
        self,
        fi: int,
        result: OptimizationResult,
        dynamics: Any,
        body: BodyModel,
        exercise_type: str,
    ) -> None:
        n = len(result.t)
        fi = fi % n
        ax = self.axes["anim"]
        ax.clear()
        style_axis(ax)

        q = result.q[fi]
        t_now = result.t[fi]
        fk = dynamics.forward_kinematics(q)

        if exercise_type == "bench_press":
            self._draw_bench_press_frame(ax, q, t_now, fi, result, fk)
        else:
            self._draw_standing_frame(ax, q, t_now, fi, result, dynamics, body, fk, exercise_type)

        self.canvas.draw()

    def _draw_bench_press_frame(
        self,
        ax: Any,
        q: Any,
        t_now: float,
        fi: int,
        result: OptimizationResult,
        fk: dict[str, Any],
    ) -> None:
        """Render bench press: supine body on bench with arm chain."""
        from matplotlib.patches import Circle as MplCircle

        ax.set_xlim(-0.6, 0.8)
        ax.set_ylim(-0.15, 1.4)
        ax.set_aspect("equal", adjustable="datalim")

        bench_h = 0.45

        # Draw bench
        ax.fill_between([-0.8, 0.5], bench_h - 0.05, bench_h, color="#8B4513", alpha=0.6)

        # Draw body lying on bench (decorative -- not part of dynamics)
        # Shoulder is near the head end (top of torso), not mid-body
        head_x, head_y = -0.40, bench_h + 0.05
        neck_x = -0.30
        shoulder_x = -0.18
        hip_x = 0.30

        # Neck
        ax.plot(
            [head_x + 0.08, neck_x],
            [bench_h + 0.05, bench_h + 0.02],
            "-",
            color="#d4a574",
            lw=5,
            solid_capstyle="round",
        )
        # Head
        ax.add_patch(
            MplCircle(
                (head_x, head_y),
                0.08,
                facecolor="#d4a574",
                edgecolor="#333",
                lw=1.2,
                alpha=0.85,
                zorder=6,
            )
        )
        # Torso (horizontal on bench)
        ax.plot(
            [neck_x, shoulder_x],
            [bench_h + 0.02, bench_h + 0.02],
            "-",
            color=Palette.SEG_COLORS[2],
            lw=12,
            solid_capstyle="round",
        )
        ax.plot(
            [shoulder_x, hip_x],
            [bench_h + 0.02, bench_h + 0.02],
            "-",
            color=Palette.SEG_COLORS[2],
            lw=12,
            solid_capstyle="round",
        )
        # Legs hanging off bench to floor
        ax.plot(
            [hip_x, hip_x + 0.15],
            [bench_h, 0],
            "-",
            color=Palette.SEG_COLORS[1],
            lw=9,
            solid_capstyle="round",
        )
        ax.plot(
            [hip_x + 0.15, hip_x + 0.2],
            [0, 0],
            "-",
            color=Palette.SEG_COLORS[0],
            lw=6,
            solid_capstyle="round",
        )

        # Ground line
        ax.plot([-0.6, 0.8], [0, 0], color=Palette.FG_DIM, lw=2, alpha=0.3)

        # Arm chain from FK (the actual dynamics)
        # FK "ankle" = shoulder joint position, remap to bench shoulder position
        arm_base = np.array([shoulder_x, bench_h + 0.02])
        fk_points = [fk["ankle"], fk["knee"], fk["hip"], fk["shoulder"]]
        # Offset FK relative to arm_base (FK has ankle at origin)
        arm_joints = [arm_base + (pt - fk_points[0]) for pt in fk_points]

        # Draw arm segments: upper arm, forearm, hand/wrist
        colors = [Palette.SEG_COLORS[0], Palette.SEG_COLORS[1], "#b0b0b0"]
        lws = [8, 6, 4]
        for k in range(3):
            ax.plot(
                [arm_joints[k][0], arm_joints[k + 1][0]],
                [arm_joints[k][1], arm_joints[k + 1][1]],
                "-",
                color=colors[k],
                lw=lws[k],
                solid_capstyle="round",
            )

        # Joint markers
        for pt in arm_joints:
            ax.plot(
                pt[0],
                pt[1],
                "o",
                color=Palette.FG,
                ms=6,
                markeredgecolor="#333",
                markeredgewidth=1,
            )

        # Bar at hand position (end of chain)
        bar_pos = arm_joints[-1]
        BarbellRenderer.draw(ax, (bar_pos[0], bar_pos[1]))

        # Bar trace — offset the FK-based trace to bench coordinates
        bar_trace_offset = arm_base - fk_points[0]
        bench_bar_traj = result.bar + bar_trace_offset
        BodyRenderer.draw_bar_trace(ax, bench_bar_traj, fi)

        ax.set_title(
            f"{self.name}  t={t_now:.2f}s  |  "
            f"Shoulder {np.degrees(q[0]):.0f}\u00b0  "
            f"Elbow {np.degrees(q[1]):.0f}\u00b0  "
            f"Wrist {np.degrees(q[2]):.0f}\u00b0",
            color=Palette.FG,
            fontsize=10,
            fontweight="bold",
        )

    def _draw_standing_frame(
        self,
        ax: Any,
        q: Any,
        t_now: float,
        fi: int,
        result: OptimizationResult,
        dynamics: Any,
        body: BodyModel,
        fk: dict[str, Any],
        exercise_type: str,
    ) -> None:
        """Render standing exercises (squat, deadlift, etc.)."""
        ax.set_xlim(-0.9, 0.9)
        ax.set_ylim(-0.15, 1.8)
        ax.set_aspect("equal", adjustable="datalim")

        is_dl = exercise_type == "deadlift"

        BodyRenderer.draw_ground(ax, body.heel_x, body.toe_x)
        BodyRenderer.draw_ghost(ax, dynamics.forward_kinematics(result.q[0]))
        BodyRenderer.draw_ghost(ax, dynamics.forward_kinematics(result.q[-1]))
        BodyRenderer.draw_segments(ax, fk)

        shoulder = fk["shoulder"]
        if is_dl:
            BodyRenderer.draw_arms(ax, shoulder, body.L_arm)
            bar_pos = (shoulder[0], shoulder[1] - body.L_arm)
            ax.axhline(PLATE_RADIUS_STD_M, color=Palette.FG_DIM, ls=":", lw=0.8, alpha=0.3)
        else:
            bar_pos = (shoulder[0], shoulder[1])

        BarbellRenderer.draw(ax, bar_pos)
        BodyRenderer.draw_com_marker(ax, result.com[fi])
        BodyRenderer.draw_bar_trace(ax, result.bar, fi)

        ax.set_title(
            f"{self.name}  t={t_now:.2f}s  |  "
            f"Shin {np.degrees(q[0]):.0f}\u00b0  "
            f"Thigh {np.degrees(q[1]):.0f}\u00b0  "
            f"Torso {np.degrees(q[2]):.0f}\u00b0",
            color=Palette.FG,
            fontsize=10,
            fontweight="bold",
        )


# ==============================================================
# Playback Controls
# ==============================================================


# ==============================================================
# Comparison Dialog
# ==============================================================
