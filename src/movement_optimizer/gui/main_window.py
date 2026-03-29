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
import json
import logging
import os
import threading
import traceback
from collections.abc import Callable
from typing import Any

import matplotlib
import numpy as np
from PyQt6.QtCore import QSettings, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..cli import EXERCISE_FACTORIES
from ..comparison import ComparisonStore
from ..constants import trapezoid
from ..export import export_animation_gif, export_plots_pdf, export_plots_png
from ..models import BodyModel
from ..persistence import load_app_state, load_solution, save_app_state, save_solution
from ..rendering import (
    Palette,
)
from ..trajectory import (
    CancelledError,
    OptimizationResult,
    ProgressReport,
    SolutionCache,
    TrajectoryOptimizer,
)
from .comparison_dialog import ComparisonDialog
from .exercise_tab import ExerciseTab
from .session_state import collect_results, collect_slider_values, restore_slider_values
from .widgets import ParameterSidebar, PlaybackControls

try:
    matplotlib.use("QtAgg")
except ImportError:
    matplotlib.use("Agg")

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


# ==============================================================
# Comparison Dialog
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
        self._opt_lock = threading.Lock()
        self._cache = SolutionCache()
        self._comparison_store = ComparisonStore()

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
        self.sidebar.save_solution_requested.connect(self._save_solution)
        self.sidebar.load_solution_requested.connect(self._load_solution)
        self.sidebar.export_video_requested.connect(self._export_video)
        self.sidebar.export_plots_requested.connect(self._export_plots)
        self.sidebar.add_comparison_requested.connect(self._add_comparison)
        self.sidebar.compare_trials_requested.connect(self._compare_trials)
        self.sidebar.clear_comparison_requested.connect(self._clear_comparison)
        self.controls.play_toggled.connect(self._toggle_play)
        self.controls.step_fwd.connect(self._step_fwd)
        self.controls.step_back.connect(self._step_back)
        self.controls.rewind.connect(self._rewind)
        self.controls.speed_changed.connect(self._on_speed)

    def closeEvent(self, event: Any) -> None:
        self._save_layout()
        self._save_session_state()
        self._stop_anim()
        self._cancel_event.set()
        event.accept()

    def _save_session_state(self) -> None:
        """Persist current results and slider values on close."""
        try:
            save_app_state(collect_results(self), collect_slider_values(self.sidebar))
        except (OSError, TypeError, ValueError):
            logger.warning("Failed to save session state: %s", traceback.format_exc())

    def try_restore_session(self) -> None:
        """Check for a saved session and offer to restore it."""
        state = load_app_state()
        if state is None:
            return
        reply = QMessageBox.question(
            self,
            "Restore Session",
            "Restore previous session?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            restore_slider_values(self.sidebar, state.get("slider_values", {}))
            self.status_label.setText("Previous session restored (slider values).")
        except (OSError, KeyError, TypeError, ValueError):
            logger.warning("Failed to restore session: %s", traceback.format_exc())

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

        with self._opt_lock:
            if self._opt_running:
                logger.warning("Optimization already running")
                return
            self._opt_running = True

        self.sidebar.show_optimizing()
        name = self.EXERCISE_CONFIGS[idx][0]
        self.status_label.setText(f"Optimizing {name}...")

        threading.Thread(
            target=self._opt_worker,
            args=(idx, then_chain),
            daemon=True,
        ).start()

    def _build_exercise_config(
        self, idx: int
    ) -> tuple[Any, Any, Any, Any, Any, str, float, float, float, dict[str, float]]:
        """Build the dynamics, poses, and parameters for an exercise.

        Returns:
            (dyn, qs, qe, qb, q_via, etype, bar, dur, smoothness, seg_mults)
        """
        body = self.sidebar.get_body_model()
        bar = self.sidebar.bar_slider.value()
        dur = self.sidebar.dur_slider.value()
        smoothness = self.sidebar.smooth_slider.value()
        _, etype = self.EXERCISE_CONFIGS[idx]

        factory = EXERCISE_FACTORIES[etype]
        config = factory(body, bar)
        if len(config) == 5:
            dyn, qs, qe, qb, q_via = config  # type: ignore[misc]
        else:
            dyn, qs, qe, qb = config  # type: ignore[misc]
            q_via = None

        # Enforce minimum duration for multi-phase exercises
        _min_durations = {
            "full_squat": 3.0,
            "bench_press": 3.0,
            "clean": 2.5,
            "jerk": 2.0,
            "snatch": 3.0,
        }
        if etype in _min_durations:
            dur = max(dur, _min_durations[etype])

        self.dynamics_list[idx] = dyn
        self.bodies_list[idx] = body

        seg_mults = {
            "lower_leg": self.sidebar.ll_slider.value(),
            "upper_leg": self.sidebar.ul_slider.value(),
            "torso": self.sidebar.to_slider.value(),
        }
        return dyn, qs, qe, qb, q_via, etype, bar, dur, smoothness, seg_mults

    def _run_optimizer(
        self,
        idx: int,
        body: BodyModel,
        dyn: Any,
        qs: Any,
        qe: Any,
        qb: Any,
        q_via: Any,
        etype: str,
        bar: float,
        dur: float,
        smoothness: float,
        seg_mults: dict[str, float],
    ) -> OptimizationResult:
        """Run the trajectory optimizer (or return a cached result).

        Raises CancelledError if the user cancels mid-run.
        """
        cached = self._cache.get(
            etype, body.body_mass, body.height, seg_mults, bar, dur, smoothness
        )
        if cached is not None:
            logger.info("Cache hit for %s", etype)
            return cached

        logger.info(
            "Starting %s optimisation: mass=%.0f, height=%.2f, bar=%.0f",
            etype,
            body.body_mass,
            body.height,
            bar,
        )

        opt = TrajectoryOptimizer(
            body,
            dyn,  # type: ignore[arg-type]
            etype,
            bar,
            qs,  # type: ignore[arg-type]
            qe,  # type: ignore[arg-type]
            qb,  # type: ignore[arg-type]
            q_via=q_via,  # type: ignore[arg-type]
            duration=dur,
            n_waypoints=12,
            smoothness=smoothness,
            progress_cb=self._make_progress_cb(),
            cancel_event=self._cancel_event,
        )
        result = opt.optimize()

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
        return result

    def _opt_worker(self, idx: int, then_chain: list[int] | None) -> None:
        try:
            body = self.sidebar.get_body_model()
            dyn, qs, qe, qb, q_via, etype, bar, dur, smoothness, seg_mults = (
                self._build_exercise_config(idx)
            )

            result = self._run_optimizer(
                idx, body, dyn, qs, qe, qb, q_via, etype, bar, dur, smoothness, seg_mults
            )

            with self._opt_lock:
                self.results[idx] = result
                self.anim_frames[idx] = 0

            self._sig_done.emit(idx, result, body, bar, then_chain)
        except CancelledError:
            self._sig_cancelled.emit()
        except NotImplementedError as exc:
            tb = traceback.format_exc()
            logger.error("Optimisation failed (feature not implemented):\n%s", tb)
            self._sig_error.emit(f"Feature not yet implemented: {exc}")
        except (ValueError, RuntimeError, OSError, np.linalg.LinAlgError) as exc:
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

            _, etype = self.EXERCISE_CONFIGS[idx]
            self._update_result_summary(name, result, exercise_type=etype)
            tab = self.exercise_tabs[idx]
            tab.draw_all_plots(result, body, bar, exercise_type=etype)
            tab.draw_anim_frame(0, result, self.dynamics_list[idx], body, etype)

            elapsed = result.elapsed_s
            t_str = (
                f"{elapsed:.1f}s" if elapsed < 60 else f"{int(elapsed // 60)}m {elapsed % 60:.0f}s"
            )
            self.sidebar.prog_label.setText(f"Done in {t_str} ({result.n_evals} evals)")
            self.sidebar.export_btn.setEnabled(True)
            self.sidebar.save_btn.setEnabled(True)
            self.sidebar.export_video_btn.setEnabled(True)
            self.sidebar.export_plots_btn.setEnabled(True)
            self.sidebar.add_compare_btn.setEnabled(True)

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
                next_idx = then_chain[0]
                remaining = then_chain[1:] if len(then_chain) > 1 else None
                self._run_exercise(next_idx, remaining)
            else:
                with self._opt_lock:
                    self._opt_running = False
                self.sidebar.show_idle()
                self.status_label.setText(status_msg)
        except (ValueError, RuntimeError, OSError, AttributeError) as exc:
            with self._opt_lock:
                self._opt_running = False
            tb = traceback.format_exc()
            logger.error("Error in _on_done:\n%s", tb)
            self.sidebar.show_idle()
            self.status_label.setText(f"Render error: {exc}")

    def _on_cancelled(self) -> None:
        with self._opt_lock:
            self._opt_running = False
        self.sidebar.show_idle()
        self.sidebar.prog_label.setText("Cancelled")
        self.status_label.setText("Optimization cancelled by user.")
        self.sidebar.cancel_btn.setEnabled(True)

    def _update_result_summary(
        self, name: str, r: OptimizationResult, exercise_type: str = "squat"
    ) -> None:
        pk = np.max(np.abs(r.torques), axis=0)
        work = trapezoid(np.sum(np.abs(r.power), axis=1), r.t)

        if exercise_type == "bench_press":
            joint_lines = (
                f"  Shoulder: {pk[0]:>6.0f} N\u00b7m\n"
                f"  Elbow:    {pk[1]:>6.0f} N\u00b7m\n"
                f"  Wrist:    {pk[2]:>6.0f} N\u00b7m"
            )
        else:
            balance_ok = "BALANCED" if r.success else "OUT OF BOUNDS"
            joint_lines = (
                f"  Ankle: {pk[0]:>6.0f} N\u00b7m\n"
                f"  Knee:  {pk[1]:>6.0f} N\u00b7m\n"
                f"  Hip:   {pk[2]:>6.0f} N\u00b7m\n"
                f"  COM sway: {r.com_horizontal_range_cm:.1f} cm\n"
                f"  Balance: {balance_ok}"
            )

        self.sidebar.result_label.setText(f"{name} results:\n{joint_lines}\n  Work: {work:>6.0f} J")

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
        body = self.bodies_list[idx]
        if body is None:
            raise ValueError("DbC Blocked: Precondition failed.")
        self.exercise_tabs[idx].draw_anim_frame(
            fi,
            r,
            self.dynamics_list[idx],
            body,
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

    def _draw_current_frame(self, idx: int) -> None:
        """Render the current animation frame for the given exercise tab."""
        r = self.results[idx]
        if r is None:
            return
        fi = self.anim_frames[idx]
        _, etype = self.EXERCISE_CONFIGS[idx]
        self.exercise_tabs[idx].draw_anim_frame(
            fi,
            r,
            self.dynamics_list[idx],
            self.bodies_list[idx],  # type: ignore[arg-type]
            etype,
        )
        n = len(r.t)
        self.controls.frame_label.setText(f"Frame {fi + 1}/{n}")

    def _step_fwd(self) -> None:
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return
        self._stop_anim()
        n = len(r.t)
        self.anim_frames[idx] = (self.anim_frames[idx] + 1) % n
        self._draw_current_frame(idx)

    def _step_back(self) -> None:
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return
        self._stop_anim()
        n = len(r.t)
        self.anim_frames[idx] = (self.anim_frames[idx] - 1) % n
        self._draw_current_frame(idx)

    def _rewind(self) -> None:
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return
        self._stop_anim()
        self.anim_frames[idx] = 0
        self._draw_current_frame(idx)

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
            with open(path, "w", newline="", encoding="utf-8") as f:
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
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _save_solution(self) -> None:
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return
        name = self.EXERCISE_CONFIGS[idx][0].lower().replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Solution",
            f"{name}_solution.json",
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            body_params = {
                "body_mass": self.sidebar.mass_slider.value(),
                "height": self.sidebar.height_slider.value(),
                "seg_multipliers": {
                    "lower_leg": self.sidebar.ll_slider.value(),
                    "upper_leg": self.sidebar.ul_slider.value(),
                    "torso": self.sidebar.to_slider.value(),
                },
            }
            _, etype = self.EXERCISE_CONFIGS[idx]
            bar = self.sidebar.bar_slider.value()
            save_solution(path, r, body_params, etype, bar)
            self.status_label.setText(f"Saved: {os.path.basename(path)}")
        except (OSError, TypeError, ValueError) as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _load_solution(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Solution",
            "",
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            data = load_solution(path)
            self.status_label.setText(
                f"Loaded solution: {data.get('exercise_type', 'unknown')} "
                f"from {os.path.basename(path)}"
            )
            QMessageBox.information(
                self,
                "Solution Loaded",
                f"Exercise: {data.get('exercise_type')}\n"
                f"Bar mass: {data.get('bar_mass')} kg\n"
                f"Cost: {data.get('metadata', {}).get('cost', 'N/A')}",
            )
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
            QMessageBox.critical(self, "Load Error", str(e))

    def _export_video(self) -> None:
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return
        name = self.EXERCISE_CONFIGS[idx][0].lower().replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Animation GIF",
            f"{name}_animation.gif",
            "GIF Files (*.gif)",
        )
        if not path:
            return
        try:
            tab = self.exercise_tabs[idx]
            _, etype = self.EXERCISE_CONFIGS[idx]
            body = self.bodies_list[idx]
            dyn = self.dynamics_list[idx]
            n_frames = len(r.t)

            if body is None:
                raise ValueError("DbC Blocked: Precondition failed.")

            def draw_frame(fi: int) -> None:
                tab.draw_anim_frame(fi, r, dyn, body, etype)

            export_animation_gif(tab.fig, draw_frame, n_frames, path, fps=15)
            self.status_label.setText(f"Exported GIF: {os.path.basename(path)}")
            QMessageBox.information(self, "Exported", f"Animation saved to:\n{path}")
        except (OSError, ValueError, RuntimeError) as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _export_plots(self) -> None:
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return
        name = self.EXERCISE_CONFIGS[idx][0].lower().replace(" ", "_")
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Plots",
            f"{name}_plots.png",
            "PNG Files (*.png);;PDF Files (*.pdf)",
        )
        if not path:
            return
        try:
            tab = self.exercise_tabs[idx]
            if path.lower().endswith(".pdf"):
                export_plots_pdf(tab.fig, path)
            else:
                export_plots_png(tab.fig, path)
            self.status_label.setText(f"Exported: {os.path.basename(path)}")
            QMessageBox.information(self, "Exported", f"Plots saved to:\n{path}")
        except (OSError, ValueError, RuntimeError) as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _add_comparison(self) -> None:
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return
        display_name, _etype = self.EXERCISE_CONFIGS[idx]
        bar = self.sidebar.bar_slider.value()
        body_params = {
            "body_mass": self.sidebar.mass_slider.value(),
            "height": self.sidebar.height_slider.value(),
        }
        n = len(self._comparison_store.get_trials()) + 1
        trial_name = f"{display_name} #{n} ({bar:.0f}kg)"
        self._comparison_store.add_trial(trial_name, r, body_params, bar)
        self.sidebar.compare_btn.setEnabled(True)
        self.status_label.setText(f"Added '{trial_name}' to comparison list.")

    def _compare_trials(self) -> None:
        trials = self._comparison_store.get_trials()
        if not trials:
            QMessageBox.information(self, "No Trials", "Add trials to compare first.")
            return
        dlg = ComparisonDialog(trials, self)
        dlg.exec()

    def _clear_comparison(self) -> None:
        self._comparison_store.clear()
        self.sidebar.compare_btn.setEnabled(False)
        self.status_label.setText("Comparison list cleared.")

    def _reset(self) -> None:
        self._stop_anim()
        self.sidebar.reset_defaults()
        self._cache.clear()
        self.status_label.setText("Defaults restored. Cache cleared.")
