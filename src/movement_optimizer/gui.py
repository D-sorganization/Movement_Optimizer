"""PyQt6 GUI for the Movement Optimizer.

Layout:
    Left sidebar  -- body parameters, segment multipliers, barbell,
                     optimisation controls, smoothness slider, results.
    Right area    -- tabbed exercise views (Squat, Full Squat, Deadlift)
                     with matplotlib animation + analysis plots.
    Bottom bar    -- playback controls and status.

Design Principles:
    LoD  -- each widget class manages its own state and signals.
    DRY  -- shared helpers (style_axis, Palette) imported from rendering.
    DBC  -- methods document and check their preconditions.
"""

from __future__ import annotations

import csv
import logging
import os
import sys
import threading
import traceback
from collections.abc import Callable
from typing import Any

import matplotlib
import matplotlib.cm as cm
import numpy as np
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.backends.backend_qtagg import (
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
from PyQt6.QtCore import QSettings, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .constants import BAR_MASS_KG, PLATE_RADIUS_STD_M, trapezoid
from .exercises import make_clean_config, make_jerk_config, make_snatch_config
from .models import (
    BodyModel,
    make_bench_press_config,
    make_deadlift_config,
    make_full_squat_config,
    make_squat_config,
)
from .rendering import (
    BarbellRenderer,
    BodyRenderer,
    Palette,
    style_axis,
)
from .spine_loads import NIOSH_COMPRESSION_LIMIT, spinal_compression, spinal_shear
from .trajectory import (
    CancelledError,
    OptimizationResult,
    ProgressReport,
    SolutionCache,
    TrajectoryOptimizer,
)

matplotlib.use("QtAgg")

logger = logging.getLogger(__name__)


# ==============================================================
# QSS Stylesheet
# ==============================================================

QSS = f"""
QMainWindow {{
    background-color: {Palette.BG};
}}
QWidget {{
    background-color: {Palette.BG};
    color: {Palette.FG};
    font-family: 'Segoe UI', 'Ubuntu', sans-serif;
    font-size: 10pt;
}}
QGroupBox {{
    background-color: {Palette.BG_PANEL};
    border: 1px solid {Palette.BG_INPUT};
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 16px;
    font-weight: bold;
    font-size: 10pt;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {Palette.FG};
}}
QLabel {{
    background-color: transparent;
    color: {Palette.FG};
}}
QLabel[class="dim"] {{
    color: {Palette.FG_DIM};
    font-size: 8pt;
}}
QLabel[class="result"] {{
    color: {Palette.GREEN};
    font-family: 'Consolas', 'Ubuntu Mono', monospace;
    font-size: 9pt;
}}
QLabel[class="title"] {{
    font-size: 14pt;
    font-weight: bold;
}}
QLabel[class="stall-warn"] {{
    color: {Palette.RED};
    font-size: 8pt;
    font-weight: bold;
}}
QPushButton {{
    background-color: {Palette.BG_INPUT};
    color: {Palette.FG};
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 9pt;
}}
QPushButton:hover {{
    background-color: {Palette.ACCENT};
}}
QPushButton[class="primary"] {{
    background-color: {Palette.ACCENT};
    color: white;
    font-weight: bold;
    font-size: 10pt;
    padding: 8px 16px;
}}
QPushButton[class="primary"]:hover {{
    background-color: {Palette.ACCENT2};
}}
QPushButton[class="cancel"] {{
    background-color: {Palette.RED};
    color: white;
    font-weight: bold;
    font-size: 9pt;
    padding: 6px 14px;
}}
QPushButton[class="cancel"]:hover {{
    background-color: #ff6666;
}}
QSlider::groove:horizontal {{
    background: {Palette.BG_INPUT};
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {Palette.ACCENT};
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: {Palette.ACCENT2};
}}
QTabWidget::pane {{
    border: 1px solid {Palette.BG_INPUT};
    border-radius: 4px;
}}
QTabBar::tab {{
    background: {Palette.BG_INPUT};
    color: {Palette.FG};
    padding: 6px 18px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background: {Palette.ACCENT};
    color: white;
}}
QProgressBar {{
    background-color: {Palette.BG_INPUT};
    border: none;
    border-radius: 3px;
    height: 8px;
    text-align: center;
    font-size: 7pt;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {Palette.ACCENT};
    border-radius: 3px;
}}
QScrollArea {{
    border: none;
}}
"""


# ==============================================================
# Labelled Slider Widget
# ==============================================================


class LabelledSlider(QWidget):
    """Slider with label and formatted value display."""

    value_changed = pyqtSignal(float)

    def __init__(
        self,
        label: str,
        lo: float,
        hi: float,
        default: float,
        unit: str,
        decimals: int = 1,
        steps: int = 200,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        assert lo < hi, f"lo ({lo}) must be < hi ({hi})"
        self.lo = lo
        self.hi = hi
        self.decimals = decimals
        self.unit = unit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)

        row = QHBoxLayout()
        self.name_label = QLabel(label)
        self.val_label = QLabel(self._fmt(default))
        self.val_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.name_label)
        row.addStretch()
        row.addWidget(self.val_label)
        layout.addLayout(row)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, steps)
        self.slider.setValue(self._to_tick(default))
        self.slider.valueChanged.connect(self._on_change)
        layout.addWidget(self.slider)

    def _fmt(self, val: float) -> str:
        return f"{val:.{self.decimals}f} {self.unit}"

    def _to_tick(self, val: float) -> int:
        frac = (val - self.lo) / (self.hi - self.lo)
        return int(frac * self.slider.maximum())

    def _from_tick(self, tick: int) -> float:
        frac = tick / self.slider.maximum()
        return self.lo + frac * (self.hi - self.lo)

    def _on_change(self, tick: int) -> None:
        val = self._from_tick(tick)
        self.val_label.setText(self._fmt(val))
        self.value_changed.emit(val)

    def value(self) -> float:
        return self._from_tick(self.slider.value())

    def set_value(self, val: float) -> None:
        self.slider.setValue(self._to_tick(val))


# ==============================================================
# Parameter Sidebar
# ==============================================================


class ParameterSidebar(QScrollArea):
    """Left-hand sidebar with all tuneable parameters."""

    optimize_current = pyqtSignal()
    optimize_both = pyqtSignal()
    cancel_requested = pyqtSignal()
    export_requested = pyqtSignal()
    reset_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFixedWidth(270)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        self.main_layout = QVBoxLayout(container)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(4)
        self.setWidget(container)

        self._build_body_params()
        self._build_segment_lengths()
        self._build_barbell()
        self._build_optimization()
        self._build_buttons()
        self._build_progress_panel()
        self._build_results()
        self.main_layout.addStretch()

    def _build_body_params(self) -> None:
        grp = QGroupBox("Body Parameters")
        lay = QVBoxLayout(grp)
        self.mass_slider = LabelledSlider("Body Mass", 40, 150, 75, "kg", 0)
        self.height_slider = LabelledSlider("Height", 1.40, 2.10, 1.75, "m", 2)
        lay.addWidget(self.mass_slider)
        lay.addWidget(self.height_slider)
        self.main_layout.addWidget(grp)

    def _build_segment_lengths(self) -> None:
        grp = QGroupBox("Segment Lengths")
        lay = QVBoxLayout(grp)
        hint = QLabel("Multipliers on base length")
        hint.setProperty("class", "dim")
        lay.addWidget(hint)
        self.ll_slider = LabelledSlider("Lower Leg", 0.70, 1.30, 1.00, "x", 2)
        self.ul_slider = LabelledSlider("Upper Leg", 0.70, 1.30, 1.00, "x", 2)
        self.to_slider = LabelledSlider("Torso", 0.70, 1.30, 1.00, "x", 2)
        lay.addWidget(self.ll_slider)
        lay.addWidget(self.ul_slider)
        lay.addWidget(self.to_slider)
        self.main_layout.addWidget(grp)

    def _build_barbell(self) -> None:
        grp = QGroupBox("Barbell")
        lay = QVBoxLayout(grp)
        hint = QLabel(f"Olympic bar = {BAR_MASS_KG:.0f} kg")
        hint.setProperty("class", "dim")
        lay.addWidget(hint)
        self.bar_slider = LabelledSlider("Total Bar + Plates", 0, 300, 60, "kg", 0)
        lay.addWidget(self.bar_slider)
        self.main_layout.addWidget(grp)

    def _build_optimization(self) -> None:
        grp = QGroupBox("Optimization")
        lay = QVBoxLayout(grp)
        self.dur_slider = LabelledSlider("Duration", 0.5, 5.0, 2.0, "s", 1)
        self.smooth_slider = LabelledSlider("Smoothness", 0.1, 5.0, 1.0, "x", 1)
        hint = QLabel("Higher = smoother torques")
        hint.setProperty("class", "dim")
        lay.addWidget(self.dur_slider)
        lay.addWidget(self.smooth_slider)
        lay.addWidget(hint)
        self.main_layout.addWidget(grp)

    def _build_buttons(self) -> None:
        self.opt_btn = QPushButton("\u25b6  Optimize Current Tab")
        self.opt_btn.setProperty("class", "primary")
        self.opt_btn.clicked.connect(self.optimize_current.emit)
        self.main_layout.addWidget(self.opt_btn)

        self.both_btn = QPushButton("Optimize All Tabs")
        self.both_btn.clicked.connect(self.optimize_both.emit)
        self.main_layout.addWidget(self.both_btn)

        self.cancel_btn = QPushButton("\u2716  Cancel")
        self.cancel_btn.setProperty("class", "cancel")
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        self.cancel_btn.setVisible(False)
        self.main_layout.addWidget(self.cancel_btn)

    def _build_progress_panel(self) -> None:
        grp = QGroupBox("Progress")
        lay = QVBoxLayout(grp)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        lay.addWidget(self.progress)

        self.prog_label = QLabel("")
        self.prog_label.setProperty("class", "dim")
        lay.addWidget(self.prog_label)

        self.iter_label = QLabel("")
        self.iter_label.setProperty("class", "dim")
        lay.addWidget(self.iter_label)

        self.cost_label = QLabel("")
        self.cost_label.setProperty("class", "dim")
        lay.addWidget(self.cost_label)

        self.improve_label = QLabel("")
        self.improve_label.setProperty("class", "dim")
        lay.addWidget(self.improve_label)

        self.elapsed_label = QLabel("")
        self.elapsed_label.setProperty("class", "dim")
        lay.addWidget(self.elapsed_label)

        self.stall_label = QLabel("")
        self.stall_label.setProperty("class", "stall-warn")
        self.stall_label.setWordWrap(True)
        self.stall_label.setVisible(False)
        lay.addWidget(self.stall_label)

        self.conv_fig = Figure(figsize=(2.4, 1.2), facecolor=Palette.BG_PANEL)
        self.conv_canvas = FigureCanvas(self.conv_fig)
        self.conv_canvas.setFixedHeight(90)
        self.conv_ax = self.conv_fig.add_subplot(111)
        self._style_conv_ax()
        lay.addWidget(self.conv_canvas)

        self.main_layout.addWidget(grp)

    def _style_conv_ax(self) -> None:
        ax = self.conv_ax
        ax.set_facecolor(Palette.BG_PLOT)
        ax.tick_params(colors=Palette.FG_DIM, which="both", labelsize=6)
        for sp in ("bottom", "left"):
            ax.spines[sp].set_color(Palette.FG_DIM)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.set_xlabel("eval", fontsize=6, color=Palette.FG_DIM)
        ax.set_ylabel("cost", fontsize=6, color=Palette.FG_DIM)
        self.conv_fig.tight_layout(pad=0.3)

    def _build_results(self) -> None:
        grp = QGroupBox("Results")
        lay = QVBoxLayout(grp)
        self.result_label = QLabel("(none)")
        self.result_label.setProperty("class", "result")
        self.result_label.setWordWrap(True)
        lay.addWidget(self.result_label)
        self.main_layout.addWidget(grp)

        self.export_btn = QPushButton("Export CSV")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_requested.emit)
        self.main_layout.addWidget(self.export_btn)

        self.reset_btn = QPushButton("Reset Defaults")
        self.reset_btn.clicked.connect(self.reset_requested.emit)
        self.main_layout.addWidget(self.reset_btn)

    def show_optimizing(self) -> None:
        self.opt_btn.setEnabled(False)
        self.both_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.stall_label.setVisible(False)
        self.stall_label.setText("")
        self.progress.setValue(0)
        self._clear_progress_labels()

    def show_idle(self) -> None:
        self.opt_btn.setEnabled(True)
        self.both_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)

    def update_progress(self, report: ProgressReport) -> None:
        n_evals = report.iteration
        pct = min(95, int(95 * (1 - 1 / (1 + n_evals / 500))))
        self.progress.setValue(pct)
        phase = "Converging" if n_evals > 200 else "Exploring"
        self.prog_label.setText(f"{phase}...")
        self.iter_label.setText(f"Evaluations: {report.iteration}")
        self.cost_label.setText(f"Cost: {report.cost:.1f}  (best: {report.best_cost:.1f})")
        self.improve_label.setText(f"Improvement: {report.improvement_pct:+.3f}%")
        elapsed = report.elapsed_s
        if elapsed < 60:
            time_str = f"{elapsed:.1f}s"
        else:
            time_str = f"{int(elapsed // 60)}m {elapsed % 60:.0f}s"
        self.elapsed_label.setText(f"Elapsed: {time_str}")

        if report.is_stalled:
            self.stall_label.setText(f"\u26a0 STALLED: {report.stall_reason}")
            self.stall_label.setVisible(True)
        elif elapsed > 120:
            self.stall_label.setText(
                "\u26a0 Taking longer than expected. Consider cancelling and adjusting parameters."
            )
            self.stall_label.setVisible(True)
        else:
            self.stall_label.setVisible(False)

        self._update_conv_plot(report.cost_history)

    def _update_conv_plot(self, history: list[float]) -> None:
        ax = self.conv_ax
        ax.clear()
        self._style_conv_ax()
        if len(history) > 1:
            clean = [c for c in history if c < 1e30]
            if len(clean) > 1:
                ax.plot(range(len(clean)), clean, color=Palette.ACCENT, lw=1.2)
                ax.set_yscale("log")
        self.conv_canvas.draw_idle()

    def _clear_progress_labels(self) -> None:
        self.prog_label.setText("")
        self.iter_label.setText("")
        self.cost_label.setText("")
        self.improve_label.setText("")
        self.elapsed_label.setText("")
        self.conv_ax.clear()
        self._style_conv_ax()
        self.conv_canvas.draw_idle()

    def get_body_model(self) -> BodyModel:
        return BodyModel(
            body_mass=self.mass_slider.value(),
            height=self.height_slider.value(),
            seg_multipliers={
                "lower_leg": self.ll_slider.value(),
                "upper_leg": self.ul_slider.value(),
                "torso": self.to_slider.value(),
            },
        )

    def reset_defaults(self) -> None:
        self.mass_slider.set_value(75.0)
        self.height_slider.set_value(1.75)
        self.ll_slider.set_value(1.00)
        self.ul_slider.set_value(1.00)
        self.to_slider.set_value(1.00)
        self.bar_slider.set_value(60.0)
        self.dur_slider.set_value(2.0)
        self.smooth_slider.set_value(1.0)


# ==============================================================
# Exercise Tab
# ==============================================================


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
    ) -> None:
        for k in self.axes:
            if k != "anim":
                self.axes[k].clear()
                style_axis(self.axes[k])

        self._plot_angles(result)
        self._plot_torques(result)
        self._plot_power(result)
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

    def _plot_angles(self, r: OptimizationResult) -> None:
        ax = self.axes["angles"]
        for j in range(3):
            ax.plot(
                r.t,
                np.degrees(r.q[:, j]),
                color=Palette.SEG_COLORS[j],
                lw=2,
                label=Palette.SEG_LABELS[j],
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

    def _plot_torques(self, r: OptimizationResult) -> None:
        ax = self.axes["torques"]
        for j in range(3):
            ax.plot(
                r.t,
                r.torques[:, j],
                color=Palette.SEG_COLORS[j],
                lw=2,
                label=Palette.SEG_LABELS[j],
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

    def _plot_power(self, r: OptimizationResult) -> None:
        ax = self.axes["power"]
        for j in range(3):
            ax.plot(
                r.t,
                r.power[:, j],
                color=Palette.SEG_COLORS[j],
                lw=2,
                label=Palette.SEG_LABELS[j],
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
        colors_t = cm.viridis(np.linspace(0.2, 0.95, len(r.t)))
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
            where=comp > NIOSH_COMPRESSION_LIMIT,
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
        ax.set_xlim(-0.9, 0.9)
        ax.set_ylim(-0.15, 1.8)
        ax.set_aspect("equal", adjustable="datalim")

        q = result.q[fi]
        t_now = result.t[fi]
        fk = dynamics.forward_kinematics(q)
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
        self.canvas.draw()


# ==============================================================
# Playback Controls
# ==============================================================


class PlaybackControls(QWidget):
    play_toggled = pyqtSignal()
    step_fwd = pyqtSignal()
    step_back = pyqtSignal()
    rewind = pyqtSignal()
    speed_changed = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.btn_rewind = QPushButton("\u23ee")
        self.btn_back = QPushButton("\u25c0")
        self.btn_play = QPushButton("\u25b6 Play")
        self.btn_play.setProperty("class", "primary")
        self.btn_fwd = QPushButton("\u25b6")

        self.btn_rewind.clicked.connect(self.rewind.emit)
        self.btn_back.clicked.connect(self.step_back.emit)
        self.btn_play.clicked.connect(self.play_toggled.emit)
        self.btn_fwd.clicked.connect(self.step_fwd.emit)

        for btn in (self.btn_rewind, self.btn_back, self.btn_play, self.btn_fwd):
            layout.addWidget(btn)

        layout.addSpacing(12)
        layout.addWidget(QLabel("Speed:"))

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 30)
        self.speed_slider.setValue(10)
        self.speed_slider.setFixedWidth(100)
        self.speed_slider.valueChanged.connect(lambda v: self.speed_changed.emit(v / 10.0))
        layout.addWidget(self.speed_slider)

        self.speed_label = QLabel("1.0x")
        self.speed_label.setFixedWidth(40)
        layout.addWidget(self.speed_label)

        layout.addStretch()
        self.frame_label = QLabel("")
        layout.addWidget(self.frame_label)

    def set_playing(self, playing: bool) -> None:
        self.btn_play.setText("\u23f8 Pause" if playing else "\u25b6 Play")


# ==============================================================
# Main Window
# ==============================================================


class MainWindow(QMainWindow):
    """Top-level application window."""

    # Signals for thread-safe GUI updates from the optimizer worker.
    # Using signals instead of QTimer.singleShot is the Qt-correct way
    # to communicate from a background thread to the main thread.
    _sig_done = pyqtSignal(int, object, object, float, object)  # idx, result, body, bar, then_chain
    _sig_cancelled = pyqtSignal()
    _sig_error = pyqtSignal(str)
    _sig_progress = pyqtSignal(object)  # ProgressReport

    EXERCISE_CONFIGS = (
        ("Bottoms Up Squat", "squat"),
        ("Full Squat", "full_squat"),
        ("Deadlift", "deadlift"),
        ("Bench Press", "bench_press"),
        ("Clean", "clean"),
        ("Jerk", "jerk"),
        ("Snatch", "snatch"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Movement Optimizer")
        self.setMinimumSize(1280, 830)

        self.results: list[OptimizationResult | None] = [None] * len(self.EXERCISE_CONFIGS)
        self.dynamics_list: list[Any] = [None] * len(self.EXERCISE_CONFIGS)
        self.bodies_list: list[BodyModel | None] = [None] * len(self.EXERCISE_CONFIGS)
        self.anim_frames = [0] * len(self.EXERCISE_CONFIGS)
        self.is_playing = False
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._anim_step)

        self._cancel_event = threading.Event()
        self._opt_running = False
        self._cache = SolutionCache()

        # Connect thread-safe signals
        self._sig_done.connect(self._on_done)
        self._sig_cancelled.connect(self._on_cancelled)
        self._sig_error.connect(self._on_err)
        self._sig_progress.connect(self._update_progress)

        self._settings = QSettings("D-sorganization", "Movement-Optimizer")

        self._build_ui()
        self.setStyleSheet(QSS)
        self._restore_layout()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(8, 8, 8, 8)

        title = QLabel("Movement Optimizer")
        title.setProperty("class", "title")
        outer.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter, stretch=1)

        self.sidebar = ParameterSidebar()
        splitter.addWidget(self.sidebar)

        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.exercise_tabs: list[ExerciseTab] = []
        for display_name, _ in self.EXERCISE_CONFIGS:
            tab = ExerciseTab(display_name)
            self.tabs.addTab(tab, f"  {display_name}  ")
            self.exercise_tabs.append(tab)
        right_lay.addWidget(self.tabs)

        self.controls = PlaybackControls()
        right_lay.addWidget(self.controls)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.status_label = QLabel("Ready")
        self.status_label.setProperty("class", "dim")
        outer.addWidget(self.status_label)

        self._connect_signals()

    def _connect_signals(self) -> None:
        self.sidebar.optimize_current.connect(self._run_current)
        self.sidebar.optimize_both.connect(self._run_all)
        self.sidebar.cancel_requested.connect(self._cancel_optimization)
        self.sidebar.export_requested.connect(self._export)
        self.sidebar.reset_requested.connect(self._reset)
        self.controls.play_toggled.connect(self._toggle_play)
        self.controls.step_fwd.connect(self._step_fwd)
        self.controls.step_back.connect(self._step_back)
        self.controls.rewind.connect(self._rewind)
        self.controls.speed_changed.connect(self._on_speed)

    def closeEvent(self, event: Any) -> None:
        self._save_layout()
        self._stop_anim()
        self._cancel_event.set()
        event.accept()
        sys.exit(0)

    def _save_layout(self) -> None:
        """Persist window geometry and active tab to QSettings."""
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("activeTab", self.tabs.currentIndex())

    def _restore_layout(self) -> None:
        """Restore window geometry and active tab from QSettings."""
        geom = self._settings.value("geometry")
        if geom is not None:
            self.restoreGeometry(geom)
        tab_idx = self._settings.value("activeTab", 0, type=int)
        if 0 <= tab_idx < self.tabs.count():
            self.tabs.setCurrentIndex(tab_idx)

    def _cancel_optimization(self) -> None:
        self._cancel_event.set()
        self.status_label.setText("Cancelling...")
        self.sidebar.cancel_btn.setEnabled(False)

    def _run_current(self) -> None:
        self._run_exercise(self.tabs.currentIndex())

    def _run_all(self) -> None:
        self._run_exercise(0, then_chain=list(range(1, len(self.EXERCISE_CONFIGS))))

    def _run_exercise(self, idx: int, then_chain: list[int] | None = None) -> None:
        self._stop_anim()
        self._cancel_event.clear()
        self._opt_running = True
        self.sidebar.show_optimizing()
        name = self.EXERCISE_CONFIGS[idx][0]
        self.status_label.setText(f"Optimizing {name}...")

        threading.Thread(
            target=self._opt_worker,
            args=(idx, then_chain),
            daemon=True,
        ).start()

    def _opt_worker(self, idx: int, then_chain: list[int] | None) -> None:
        try:
            body = self.sidebar.get_body_model()
            bar = self.sidebar.bar_slider.value()
            dur = self.sidebar.dur_slider.value()
            smoothness = self.sidebar.smooth_slider.value()
            _, etype = self.EXERCISE_CONFIGS[idx]

            q_via = None
            if etype == "squat":
                dyn, qs, qe, qb = make_squat_config(body, bar)
            elif etype == "full_squat":
                dyn, qs, qe, qb, q_via = make_full_squat_config(body, bar)
                dur = max(dur, 3.0)
            elif etype == "bench_press":
                dyn, qs, qe, qb = make_bench_press_config(body, bar)
            elif etype == "clean":
                dyn, qs, qe, qb, q_via = make_clean_config(body, bar)
                dur = max(dur, 2.5)
            elif etype == "jerk":
                dyn, qs, qe, qb, q_via = make_jerk_config(body, bar)
                dur = max(dur, 2.0)
            elif etype == "snatch":
                dyn, qs, qe, qb, q_via = make_snatch_config(body, bar)
                dur = max(dur, 3.0)
            else:
                dyn, qs, qe, qb = make_deadlift_config(body, bar)

            self.dynamics_list[idx] = dyn
            self.bodies_list[idx] = body

            seg_mults = {
                "lower_leg": self.sidebar.ll_slider.value(),
                "upper_leg": self.sidebar.ul_slider.value(),
                "torso": self.sidebar.to_slider.value(),
            }
            cached = self._cache.get(
                etype, body.body_mass, body.height, seg_mults, bar, dur, smoothness
            )
            if cached is not None:
                logger.info("Cache hit for %s", etype)
                result = cached
                self.results[idx] = result
                self.anim_frames[idx] = 0
                self._sig_done.emit(idx, result, body, bar, then_chain)
                return

            logger.info(
                "Starting %s optimisation: mass=%.0f, height=%.2f, bar=%.0f",
                etype,
                body.body_mass,
                body.height,
                bar,
            )

            opt = TrajectoryOptimizer(
                body,
                dyn,
                etype,
                bar,
                qs,
                qe,
                qb,
                q_via=q_via,
                duration=dur,
                n_waypoints=12,
                smoothness=smoothness,
                progress_cb=self._make_progress_cb(),
                cancel_event=self._cancel_event,
            )
            result = opt.optimize()
            self.results[idx] = result
            self.anim_frames[idx] = 0

            self._cache.put(
                etype,
                body.body_mass,
                body.height,
                seg_mults,
                bar,
                dur,
                smoothness,
                result,
            )

            self._sig_done.emit(idx, result, body, bar, then_chain)
        except CancelledError:
            self._sig_cancelled.emit()
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("Optimisation failed:\n%s", tb)
            self._sig_error.emit(str(exc))

    # _ensure_idle removed: signals guarantee delivery to the main thread,
    # so _on_done / _on_cancelled / _on_err always fire reliably.

    def _make_progress_cb(self) -> Callable[[ProgressReport], None]:
        def cb(report: ProgressReport) -> None:
            self._sig_progress.emit(report)

        return cb

    def _update_progress(self, report: ProgressReport) -> None:
        self.sidebar.update_progress(report)

    def _on_done(
        self,
        idx: int,
        result: OptimizationResult,
        body: BodyModel,
        bar: float,
        then_chain: list[int] | None,
    ) -> None:
        try:
            self.sidebar.progress.setValue(100)
            name = self.EXERCISE_CONFIGS[idx][0]

            self._update_result_summary(name, result)

            _, etype = self.EXERCISE_CONFIGS[idx]
            tab = self.exercise_tabs[idx]
            tab.draw_all_plots(result, body, bar)
            tab.draw_anim_frame(0, result, self.dynamics_list[idx], body, etype)

            elapsed = result.elapsed_s
            t_str = (
                f"{elapsed:.1f}s" if elapsed < 60 else f"{int(elapsed // 60)}m {elapsed % 60:.0f}s"
            )
            self.sidebar.prog_label.setText(f"Done in {t_str} ({result.n_evals} evals)")
            self.sidebar.export_btn.setEnabled(True)

            if result.success:
                self.sidebar.stall_label.setVisible(False)
                status_msg = f"{name} optimization complete in {t_str}!"
            else:
                self.sidebar.stall_label.setText(
                    "\u26a0 COM went outside the inner 60% BOS zone. "
                    "Try increasing smoothness or adjusting body parameters."
                )
                self.sidebar.stall_label.setVisible(True)
                status_msg = f"{name} done in {t_str} -- WARNING: COM balance violated"

            if then_chain:
                next_idx = then_chain.pop(0)
                self._run_exercise(next_idx, then_chain or None)
            else:
                self._opt_running = False
                self.sidebar.show_idle()
                self.status_label.setText(status_msg)
        except Exception:
            self._opt_running = False
            tb = traceback.format_exc()
            logger.error("Error in _on_done:\n%s", tb)
            print(f"ERROR in _on_done:\n{tb}", flush=True)
            self.sidebar.show_idle()
            self.status_label.setText(f"Render error: {tb.splitlines()[-1]}")

    def _on_cancelled(self) -> None:
        self._opt_running = False
        self.sidebar.show_idle()
        self.sidebar.prog_label.setText("Cancelled")
        self.status_label.setText("Optimization cancelled by user.")
        self.sidebar.cancel_btn.setEnabled(True)

    def _update_result_summary(self, name: str, r: OptimizationResult) -> None:
        pk = np.max(np.abs(r.torques), axis=0)
        work = trapezoid(np.sum(np.abs(r.power), axis=1), r.t)
        balance_ok = "BALANCED" if r.success else "OUT OF BOUNDS"
        self.sidebar.result_label.setText(
            f"{name} results:\n"
            f"  Ankle: {pk[0]:>6.0f} N\u00b7m\n"
            f"  Knee:  {pk[1]:>6.0f} N\u00b7m\n"
            f"  Hip:   {pk[2]:>6.0f} N\u00b7m\n"
            f"  Work:  {work:>6.0f} J\n"
            f"  COM sway: {r.com_horizontal_range_cm:.1f} cm\n"
            f"  Balance: {balance_ok}"
        )

    def _on_err(self, msg: str) -> None:
        self._opt_running = False
        self.sidebar.show_idle()
        self.status_label.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Error", msg)

    def _toggle_play(self) -> None:
        idx = self.tabs.currentIndex()
        if self.results[idx] is None:
            return
        if self.is_playing:
            self._stop_anim()
        else:
            self.is_playing = True
            self.controls.set_playing(True)
            self._anim_step()

    def _stop_anim(self) -> None:
        self.is_playing = False
        self.anim_timer.stop()
        self.controls.set_playing(False)

    def _anim_step(self) -> None:
        if not self.is_playing:
            return
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return

        fi = self.anim_frames[idx]
        _, etype = self.EXERCISE_CONFIGS[idx]
        self.exercise_tabs[idx].draw_anim_frame(
            fi,
            r,
            self.dynamics_list[idx],
            self.bodies_list[idx],
            etype,
        )

        n = len(r.t)
        self.anim_frames[idx] = (fi + 1) % n
        self.controls.frame_label.setText(f"Frame {fi + 1}/{n}")

        speed = self.controls.speed_slider.value() / 10.0
        delay = max(15, int(40 / max(0.1, speed)))
        if self.anim_frames[idx] == 0:
            delay = 700
        self.anim_timer.start(delay)

    def _step_fwd(self) -> None:
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return
        self._stop_anim()
        n = len(r.t)
        self.anim_frames[idx] = (self.anim_frames[idx] + 1) % n
        _, etype = self.EXERCISE_CONFIGS[idx]
        self.exercise_tabs[idx].draw_anim_frame(
            self.anim_frames[idx],
            r,
            self.dynamics_list[idx],
            self.bodies_list[idx],
            etype,
        )
        self.controls.frame_label.setText(f"Frame {self.anim_frames[idx] + 1}/{n}")

    def _step_back(self) -> None:
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return
        self._stop_anim()
        n = len(r.t)
        self.anim_frames[idx] = (self.anim_frames[idx] - 1) % n
        _, etype = self.EXERCISE_CONFIGS[idx]
        self.exercise_tabs[idx].draw_anim_frame(
            self.anim_frames[idx],
            r,
            self.dynamics_list[idx],
            self.bodies_list[idx],
            etype,
        )

    def _rewind(self) -> None:
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return
        self._stop_anim()
        self.anim_frames[idx] = 0
        _, etype = self.EXERCISE_CONFIGS[idx]
        self.exercise_tabs[idx].draw_anim_frame(
            0,
            r,
            self.dynamics_list[idx],
            self.bodies_list[idx],
            etype,
        )

    def _on_speed(self, speed: float) -> None:
        self.controls.speed_label.setText(f"{speed:.1f}x")

    def _export(self) -> None:
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return
        name = self.EXERCISE_CONFIGS[idx][0].lower().replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            f"{name}_trajectory.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return
        self._write_csv(path, r)

    def _write_csv(self, path: str, r: OptimizationResult) -> None:
        try:
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(
                    [
                        "time_s",
                        "shin_angle_deg",
                        "thigh_angle_deg",
                        "torso_angle_deg",
                        "shin_vel_deg_s",
                        "thigh_vel_deg_s",
                        "torso_vel_deg_s",
                        "ankle_torque_Nm",
                        "knee_torque_Nm",
                        "hip_torque_Nm",
                        "ankle_power_W",
                        "knee_power_W",
                        "hip_power_W",
                        "com_x_m",
                        "com_y_m",
                        "bar_x_m",
                        "bar_y_m",
                    ]
                )
                for i in range(len(r.t)):
                    w.writerow(
                        [
                            f"{r.t[i]:.4f}",
                            *[f"{np.degrees(r.q[i, j]):.2f}" for j in range(3)],
                            *[f"{np.degrees(r.qd[i, j]):.2f}" for j in range(3)],
                            *[f"{r.torques[i, j]:.2f}" for j in range(3)],
                            *[f"{r.power[i, j]:.2f}" for j in range(3)],
                            f"{r.com[i, 0]:.4f}",
                            f"{r.com[i, 1]:.4f}",
                            f"{r.bar[i, 0]:.4f}",
                            f"{r.bar[i, 1]:.4f}",
                        ]
                    )
            self.status_label.setText(f"Exported: {os.path.basename(path)}")
            QMessageBox.information(self, "Exported", f"Saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _reset(self) -> None:
        self._stop_anim()
        self.sidebar.reset_defaults()
        self._cache.clear()
        self.status_label.setText("Defaults restored. Cache cleared.")
