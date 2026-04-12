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

import logging
import threading
import traceback
from typing import Any

import matplotlib
import numpy as np
from PyQt6.QtCore import QSettings, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow,
    QMessageBox,
)

from ..comparison import ComparisonStore
from ..constants import trapezoid
from ..models import BodyModel
from ..persistence import load_app_state, save_app_state
from ..trajectory import (
    OptimizationResult,
    SolutionCache,
)
from .animation_control import AnimationControlMixin
from .comparison_mixin import ComparisonMixin
from .file_operations import FileOperationsMixin
from .optimization_mixin import OptimizationMixin
from .session_state import collect_results, collect_slider_values, restore_slider_values
from .stylesheet import QSS
from .ui_builder import build_central_widget

try:
    matplotlib.use("QtAgg")
except ImportError:
    matplotlib.use("Agg")

logger = logging.getLogger(__name__)


# ==============================================================
# Labelled Slider Widget
# ==============================================================


# ==============================================================
# Comparison Dialog
# ==============================================================


class MainWindow(
    FileOperationsMixin,
    AnimationControlMixin,
    ComparisonMixin,
    OptimizationMixin,
    QMainWindow,
):
    """Top-level application window.

    File I/O, animation playback, optimization, and comparison actions are provided
    by mixin classes in their respective submodules.
    """

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
        self._last_config: tuple[Any, ...] = ()

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
        (
            central,
            self.sidebar,
            self.tabs,
            self.exercise_tabs,
            self.controls,
            self.status_label,
        ) = build_central_widget(self, self.EXERCISE_CONFIGS)
        self.setCentralWidget(central)
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

    # Animation, file I/O, and comparison methods are provided by the
    # mixin classes: AnimationControlMixin, FileOperationsMixin, and
    # ComparisonMixin.  See animation_control.py, file_operations.py,
    # and comparison_mixin.py.

    def _reset(self) -> None:
        self._stop_anim()
        self.sidebar.reset_defaults()
        self._cache.clear()
        self.status_label.setText("Defaults restored. Cache cleared.")
