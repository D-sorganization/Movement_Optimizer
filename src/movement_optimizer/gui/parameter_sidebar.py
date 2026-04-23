"""ParameterSidebar: left-hand parameter panel for the main window."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..constants import BAR_MASS_KG
from ..models import BodyModel
from ..rendering import Palette
from ..trajectory import ProgressReport
from .labelled_slider import LabelledSlider

logger = logging.getLogger(__name__)


class ParameterSidebar(QScrollArea):
    """Left-hand sidebar with all tuneable parameters."""

    optimize_current = pyqtSignal()
    optimize_both = pyqtSignal()
    cancel_requested = pyqtSignal()
    export_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    save_solution_requested = pyqtSignal()
    load_solution_requested = pyqtSignal()
    export_video_requested = pyqtSignal()
    export_plots_requested = pyqtSignal()
    add_comparison_requested = pyqtSignal()
    compare_trials_requested = pyqtSignal()
    clear_comparison_requested = pyqtSignal()

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

        self.bar_depth_slider = LabelledSlider("Bar Back Offset", 0.0, 0.4, 0.0, "m", 2)
        lay.addWidget(self.bar_depth_slider)
        self.bar_height_slider = LabelledSlider("Bar Drop Offset", 0.0, 0.4, 0.0, "m", 2)
        lay.addWidget(self.bar_height_slider)

        self.main_layout.addWidget(grp)

    def _build_optimization(self) -> None:
        grp = QGroupBox("Optimization")
        lay = QVBoxLayout(grp)

        # 2D/3D model selector
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["2D Sagittal", "3D Bilateral"])
        # 3D Bilateral: forward-kinematics only (MVP); optimisation still
        # runs in the 2D sagittal model and the 3D pose is rendered for
        # visualisation. See issue #225.
        idx_3d = self.model_combo.findText("3D Bilateral")
        if idx_3d >= 0:
            from PyQt6.QtGui import QStandardItemModel

            model = self.model_combo.model()
            if isinstance(model, QStandardItemModel):
                item = model.item(idx_3d)
                if item is not None:
                    item.setToolTip(
                        "3D Bilateral: renders the optimised 2D trajectory "
                        "in a bilateral (two-leg) 3D pose."
                    )
        model_row.addWidget(self.model_combo)
        lay.addLayout(model_row)

        self.dur_slider = LabelledSlider("Duration", 0.5, 5.0, 2.0, "s", 1)
        self.smooth_slider = LabelledSlider("Smoothness", 0.1, 5.0, 1.0, "x", 1)
        hint = QLabel("Higher = smoother torques")
        hint.setProperty("class", "dim")
        lay.addWidget(self.dur_slider)
        lay.addWidget(self.smooth_slider)
        lay.addWidget(hint)
        self.main_layout.addWidget(grp)

    def is_3d_mode(self) -> bool:
        """Return True if the 3D model is selected."""
        return self.model_combo.currentIndex() == 1

    def _build_buttons(self) -> None:
        self.opt_btn = QPushButton("\u25b6  Optimize Current Tab")
        self.opt_btn.setProperty("class", "primary")
        self.opt_btn.setToolTip(
            "Start trajectory optimization for the currently selected exercise tab"
        )
        self.opt_btn.clicked.connect(self.optimize_current.emit)
        self.main_layout.addWidget(self.opt_btn)

        self.both_btn = QPushButton("Optimize All Tabs")
        self.both_btn.setToolTip("Start trajectory optimization sequentially for all exercise tabs")
        self.both_btn.clicked.connect(self.optimize_both.emit)
        self.main_layout.addWidget(self.both_btn)

        self.cancel_btn = QPushButton("\u2716  Cancel")
        self.cancel_btn.setProperty("class", "cancel")
        self.cancel_btn.setToolTip("Cancel the currently running optimization")
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
        self.export_btn.setToolTip("Run optimization first to enable exporting kinematics to CSV")
        self.export_btn.clicked.connect(self.export_requested.emit)
        self.main_layout.addWidget(self.export_btn)

        self.reset_btn = QPushButton("Reset Defaults")
        self.reset_btn.setToolTip("Reset all parameters to default values")
        self.reset_btn.clicked.connect(self.reset_requested.emit)
        self.main_layout.addWidget(self.reset_btn)

        self._build_persistence_buttons()
        self._build_export_buttons()
        self._build_comparison_buttons()

    def _build_persistence_buttons(self) -> None:
        grp = QGroupBox("Solution Files")
        lay = QVBoxLayout(grp)
        self.save_btn = QPushButton("Save Solution")
        self.save_btn.setEnabled(False)
        self.save_btn.setToolTip("Run optimization first to enable saving the trajectory solution")
        self.save_btn.clicked.connect(self.save_solution_requested.emit)
        lay.addWidget(self.save_btn)
        self.load_btn = QPushButton("Load Solution")
        self.load_btn.setToolTip("Load a previously saved trajectory solution file")
        self.load_btn.clicked.connect(self.load_solution_requested.emit)
        lay.addWidget(self.load_btn)
        self.main_layout.addWidget(grp)

    def _build_export_buttons(self) -> None:
        grp = QGroupBox("Export Media")
        lay = QVBoxLayout(grp)
        self.export_video_btn = QPushButton("Export Animation GIF")
        self.export_video_btn.setEnabled(False)
        self.export_video_btn.setToolTip("Run optimization first to enable exporting animation GIF")
        self.export_video_btn.clicked.connect(self.export_video_requested.emit)
        lay.addWidget(self.export_video_btn)
        self.export_plots_btn = QPushButton("Export Plots (PNG/PDF)")
        self.export_plots_btn.setEnabled(False)
        self.export_plots_btn.setToolTip("Run optimization first to enable exporting plots")
        self.export_plots_btn.clicked.connect(self.export_plots_requested.emit)
        lay.addWidget(self.export_plots_btn)
        self.main_layout.addWidget(grp)

    def _build_comparison_buttons(self) -> None:
        grp = QGroupBox("Trial Comparison")
        lay = QVBoxLayout(grp)
        self.add_compare_btn = QPushButton("Add to Comparison")
        self.add_compare_btn.setEnabled(False)
        self.add_compare_btn.setToolTip("Run optimization first to add current trial to comparison")
        self.add_compare_btn.clicked.connect(self.add_comparison_requested.emit)
        lay.addWidget(self.add_compare_btn)
        self.compare_btn = QPushButton("Compare Trials")
        self.compare_btn.setEnabled(False)
        self.compare_btn.setToolTip("Add multiple trials to comparison first")
        self.compare_btn.clicked.connect(self.compare_trials_requested.emit)
        lay.addWidget(self.compare_btn)
        self.clear_compare_btn = QPushButton("Clear Comparison")
        self.clear_compare_btn.setToolTip("Clear all trials currently saved for comparison")
        self.clear_compare_btn.clicked.connect(self.clear_comparison_requested.emit)
        lay.addWidget(self.clear_compare_btn)
        self.main_layout.addWidget(grp)

    def connect_action_handlers(self, handlers: Mapping[str, Callable[..., None]]) -> None:
        """Connect sidebar action signals to handlers supplied by the main window."""
        self.optimize_current.connect(handlers["optimize_current"])
        self.optimize_both.connect(handlers["optimize_both"])
        self.cancel_requested.connect(handlers["cancel_requested"])
        self.export_requested.connect(handlers["export_requested"])
        self.reset_requested.connect(handlers["reset_requested"])
        self.save_solution_requested.connect(handlers["save_solution_requested"])
        self.load_solution_requested.connect(handlers["load_solution_requested"])
        self.export_video_requested.connect(handlers["export_video_requested"])
        self.export_plots_requested.connect(handlers["export_plots_requested"])
        self.add_comparison_requested.connect(handlers["add_comparison_requested"])
        self.compare_trials_requested.connect(handlers["compare_trials_requested"])
        self.clear_comparison_requested.connect(handlers["clear_comparison_requested"])

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
            squat_bar_depth=self.bar_depth_slider.value(),
            squat_bar_height=self.bar_height_slider.value(),
        )

    def reset_defaults(self) -> None:
        self.mass_slider.set_value(75.0)
        self.height_slider.set_value(1.75)
        self.ll_slider.set_value(1.00)
        self.ul_slider.set_value(1.00)
        self.to_slider.set_value(1.00)
        self.bar_slider.set_value(60.0)
        self.bar_depth_slider.set_value(0.0)
        self.bar_height_slider.set_value(0.0)
        self.dur_slider.set_value(2.0)
        self.smooth_slider.set_value(1.0)

    # ------------------------------------------------------------------
    # Façade methods — encapsulate widget-chain access so callers do not
    # need to traverse into individual child widgets (issue #263 — Law of
    # Demeter / deep object traversal).
    # ------------------------------------------------------------------

    def get_optimization_params(self) -> tuple[float, float, float]:
        """Return ``(bar_kg, duration_s, smoothness)`` from the current slider state."""
        return (
            self.bar_slider.value(),
            self.dur_slider.value(),
            self.smooth_slider.value(),
        )

    def get_segment_multipliers(self) -> dict[str, float]:
        """Return the segment-length multiplier dict from the current slider state."""
        return {
            "lower_leg": self.ll_slider.value(),
            "upper_leg": self.ul_slider.value(),
            "torso": self.to_slider.value(),
        }

    def set_progress_done(self, elapsed_str: str, n_evals: int) -> None:
        """Mark the progress bar as complete and update the label."""
        self.progress.setValue(100)
        self.prog_label.setText(f"Done in {elapsed_str} ({n_evals} evals)")

    def set_cancelled(self) -> None:
        """Update UI to the cancelled state."""
        self.prog_label.setText("Cancelled")
        self.cancel_btn.setEnabled(True)

    def set_stall_message(self, msg: str) -> None:
        """Show *msg* in the stall label."""
        self.stall_label.setText(msg)
        self.stall_label.setVisible(True)

    def clear_stall_message(self) -> None:
        """Hide the stall label."""
        self.stall_label.setVisible(False)

    def set_result_label(self, text: str) -> None:
        """Set the result summary text."""
        self.result_label.setText(text)

    def enable_post_run_buttons(self) -> None:
        """Enable export/save/compare buttons after a successful run."""
        self.export_btn.setEnabled(True)
        self.export_btn.setToolTip("Export kinematics and forces to CSV")

        self.save_btn.setEnabled(True)
        self.save_btn.setToolTip("Save the current trajectory solution to file")

        self.export_video_btn.setEnabled(True)
        self.export_video_btn.setToolTip("Export the current animation to a GIF file")

        self.export_plots_btn.setEnabled(True)
        self.export_plots_btn.setToolTip("Export the current plots to PNG/PDF files")

        self.add_compare_btn.setEnabled(True)
        self.add_compare_btn.setToolTip("Add current trial to the comparison set")

    def get_body_params_dict(self) -> dict[str, object]:
        """Return the current body parameter dict suitable for JSON serialisation."""
        return {
            "body_mass": self.mass_slider.value(),
            "height": self.height_slider.value(),
            "seg_multipliers": self.get_segment_multipliers(),
        }

    def get_comparison_trial_data(self) -> tuple[dict[str, object], float]:
        """Return the comparison payload without exposing widget internals."""
        return self.get_body_params_dict(), self.bar_slider.value()

    def get_comparison_context(self) -> tuple[float, dict[str, object]]:
        """Return bar mass and body parameters for trial comparison records."""
        body_params, bar_mass = self.get_comparison_trial_data()
        return bar_mass, body_params

    def set_comparison_available(self, available: bool) -> None:
        """Enable or disable the comparison action."""
        self.compare_btn.setEnabled(available)
        if available:
            self.compare_btn.setToolTip("Open dialog to compare saved trials")
        else:
            self.compare_btn.setToolTip("Add multiple trials to comparison first")

    def set_cancellation_available(self, available: bool) -> None:
        """Enable or disable the cancellation action."""
        self.cancel_btn.setEnabled(available)
