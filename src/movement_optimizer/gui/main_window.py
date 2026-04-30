# Copyright (c) 2026 D-Sorganization. All rights reserved.
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
from PyQt6.QtCore import QSettings, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QMainWindow,
    QMessageBox,
)

from ..comparison import ComparisonStore
from ..models import BodyModel
from ..persistence import InvalidStateFileError, load_app_state, save_app_state
from ..trajectory import (
    OptimizationResult,
    SolutionCache,
)
from .animation_control import AnimationControlMixin
from .commands import SliderChangeCommand, UndoStack
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
    _sig_error = pyqtSignal(object)  # MovementOptimizerError or str
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
        # RLock so the same thread may re-enter critical sections without
        # deadlocking when one locked helper calls another locked helper.
        self._opt_lock = threading.RLock()
        self._cache = SolutionCache()
        self._comparison_store = ComparisonStore()
        self._last_config: tuple[Any, ...] = ()

        # Connect thread-safe signals
        self._sig_done.connect(self._on_done)
        self._sig_cancelled.connect(self._on_cancelled)
        self._sig_error.connect(self._on_err)
        self._sig_progress.connect(self._update_progress)

        self._settings = QSettings("D-sorganization", "Movement-Optimizer")

        self._undo_stack = UndoStack()

        self._build_ui()
        self.setStyleSheet(QSS)
        self._restore_layout()
        self._connect_slider_undo()
        self._install_shortcuts()

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
        # Window-level Escape shortcut for cancel — works even when the cancel
        # button is hidden (QPushButton.setShortcut is inactive for hidden buttons).
        self._esc_shortcut = QShortcut(QKeySequence("Escape"), self)
        self._esc_shortcut.activated.connect(self._cancel_optimization)

        self.sidebar.connect_action_handlers(
            {
                "optimize_current": self._run_current,
                "optimize_both": self._run_all,
                "cancel_requested": self._cancel_optimization,
                "export_requested": self._export,
                "reset_requested": self._reset,
                "save_solution_requested": self._save_solution,
                "load_solution_requested": self._load_solution,
                "export_video_requested": self._export_video,
                "export_plots_requested": self._export_plots,
                "add_comparison_requested": self._add_comparison,
                "compare_trials_requested": self._compare_trials,
                "clear_comparison_requested": self._clear_comparison,
            }
        )
        self.controls.connect_action_handlers(
            {
                "play_toggled": self._toggle_play,
                "step_fwd": self._step_fwd,
                "step_back": self._step_back,
                "rewind": self._rewind,
                "speed_changed": self._on_speed,
            }
        )

    def _install_shortcuts(self) -> None:
        """Install Ctrl+Z / Ctrl+Y undo/redo keyboard shortcuts."""
        QShortcut(QKeySequence.StandardKey.Undo, self).activated.connect(self._undo)
        QShortcut(QKeySequence.StandardKey.Redo, self).activated.connect(self._redo)

    def _connect_slider_undo(self) -> None:
        """Wire sidebar sliders so value changes are recorded on the undo stack."""
        slider_names = [
            "mass_slider",
            "height_slider",
            "ll_slider",
            "ul_slider",
            "to_slider",
            "bar_slider",
            "bar_depth_slider",
            "bar_height_slider",
            "dur_slider",
            "smooth_slider",
        ]
        for name in slider_names:
            labelled = getattr(self.sidebar, name, None)
            if labelled is None:
                logger.warning("_connect_slider_undo: sidebar has no attribute %r", name)
                continue
            raw = labelled.slider

            def _make_handler(raw_slider):
                prev: list[int] = [raw_slider.value()]

                def _on_press():
                    prev[0] = raw_slider.value()

                def _on_release():
                    new_val = raw_slider.value()
                    old_val = prev[0]
                    if new_val != old_val:
                        cmd = SliderChangeCommand(raw_slider, old_val, new_val)
                        # The slider is already at new_val; append directly without
                        # calling execute() to avoid a redundant setValue round-trip.
                        self._undo_stack._undo.append(cmd)
                        self._undo_stack._redo.clear()
                        logger.debug(
                            "Slider %s: %d -> %d recorded",
                            raw_slider.accessibleName(),
                            old_val,
                            new_val,
                        )

                return _on_press, _on_release

            on_press, on_release = _make_handler(raw)
            raw.sliderPressed.connect(on_press)
            raw.sliderReleased.connect(on_release)

    def _undo(self) -> None:
        """Undo the last slider change via the undo stack."""
        if self._undo_stack.undo():
            logger.debug("Undo triggered")

    def _redo(self) -> None:
        """Redo the last undone slider change via the undo stack."""
        if self._undo_stack.redo():
            logger.debug("Redo triggered")

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
        try:
            state = load_app_state()
        except InvalidStateFileError as exc:
            logger.warning("Saved session failed schema validation: %s", exc)
            QMessageBox.warning(
                self,
                "Session State Invalid",
                f"Saved session could not be restored:\n{exc}",
            )
            return
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
        with self._opt_lock:
            if not self._opt_running:
                return
        self._cancel_event.set()
        self.status_label.setText("Cancelling...")
        self.sidebar.set_cancelling()

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

    # _on_done, _on_cancelled, _update_result_summary, _on_err, and _reset are
    # provided by OptimizationMixin (optimization_mixin.py).
    # Animation, file I/O, and comparison methods are provided by the
    # mixin classes: AnimationControlMixin, FileOperationsMixin, and
    # ComparisonMixin.  See animation_control.py, file_operations.py,
    # and comparison_mixin.py.
