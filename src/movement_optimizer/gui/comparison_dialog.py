"""ComparisonDialog -- display side-by-side metrics."""

from __future__ import annotations

import logging

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..comparison import comparison_metrics
from ..rendering import Palette, style_axis

logger = logging.getLogger(__name__)


class ComparisonDialog(QWidget):
    """Dialog showing overlaid plots and metrics table for trial comparison."""

    # Distinct colors for up to 10 trials
    TRIAL_COLORS = (
        "#569cd6",
        "#f44747",
        "#4ec9b0",
        "#ffb74d",
        "#ffd54f",
        "#c678dd",
        "#e06c75",
        "#98c379",
        "#61afef",
        "#d19a66",
    )

    def __init__(self, trials: list[dict], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Trial Comparison")
        self.setMinimumSize(900, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.trials = trials
        layout = QVBoxLayout(self)

        # Metrics table
        metrics = comparison_metrics(trials)
        header = QLabel("Trial Metrics")
        header.setProperty("class", "title")
        layout.addWidget(header)

        table_text = self._build_metrics_table(metrics)
        table_label = QLabel(table_text)
        table_label.setProperty("class", "result")
        table_label.setWordWrap(True)
        layout.addWidget(table_label)

        # Overlaid plots
        self.fig = Figure(figsize=(10, 6), facecolor=Palette.BG)
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas, stretch=1)

        self._draw_comparison_plots()
        self.show()

    def exec(self) -> None:
        """Show the dialog (non-modal)."""
        self.show()

    def _build_metrics_table(self, metrics: list[dict]) -> str:
        lines = [f"{'Trial':<30} {'Ankle':>8} {'Knee':>8} {'Hip':>8} {'Work':>10} {'COM sway':>10}"]
        lines.append("-" * 80)
        for m in metrics:
            pt = m["peak_torques"]
            lines.append(
                f"{m['name']:<30} {pt[0]:>8.1f} {pt[1]:>8.1f} {pt[2]:>8.1f} "
                f"{m['total_work']:>10.1f} {m['com_sway_cm']:>10.2f} cm"
            )
        return "\n".join(lines)

    def _plot_trial_angles(
        self, ax: object, trial: dict, color: str, joint_labels: list[str]
    ) -> None:
        """Overlay joint-angle traces for one trial onto *ax*."""
        r = trial["result"]
        label = trial["name"]
        for j in range(3):
            ax.plot(  # type: ignore[attr-defined]
                r.t,
                np.degrees(r.q[:, j]),
                color=color,
                lw=1.5,
                alpha=0.7,
                label=f"{label} - {joint_labels[j]}" if j == 0 else None,
                linestyle=["-", "--", ":"][j],
            )

    def _plot_trial_torques(self, ax: object, trial: dict, color: str) -> None:
        """Overlay joint-torque traces for one trial onto *ax*."""
        r = trial["result"]
        label = trial["name"]
        for j in range(3):
            ax.plot(  # type: ignore[attr-defined]
                r.t,
                r.torques[:, j],
                color=color,
                lw=1.5,
                alpha=0.7,
                label=label if j == 0 else None,
                linestyle=["-", "--", ":"][j],
            )

    def _plot_trial_com(self, ax: object, trial: dict, color: str) -> None:
        """Overlay the COM path for one trial onto *ax*."""
        r = trial["result"]
        ax.plot(  # type: ignore[attr-defined]
            r.com[:, 0],
            r.com[:, 1],
            color=color,
            lw=2,
            alpha=0.8,
            label=trial["name"],
        )

    def _draw_comparison_plots(self) -> None:
        """Build the three-panel comparison figure (angles, torques, COM path)."""
        gs = self.fig.add_gridspec(1, 3, hspace=0.3, wspace=0.35)
        ax_angles = self.fig.add_subplot(gs[0, 0])
        ax_torques = self.fig.add_subplot(gs[0, 1])
        ax_com = self.fig.add_subplot(gs[0, 2])

        for ax in (ax_angles, ax_torques, ax_com):
            style_axis(ax)

        joint_labels = ["Ankle", "Knee", "Hip"]

        for i, trial in enumerate(self.trials):
            color = self.TRIAL_COLORS[i % len(self.TRIAL_COLORS)]
            self._plot_trial_angles(ax_angles, trial, color, joint_labels)
            self._plot_trial_torques(ax_torques, trial, color)
            self._plot_trial_com(ax_com, trial, color)

        self._label_angles_axis(ax_angles)
        self._label_torques_axis(ax_torques)
        self._label_com_axis(ax_com)

        self.fig.tight_layout()
        self.canvas.draw()

    def _label_angles_axis(self, ax: object) -> None:
        """Apply titles and legend to the joint-angles subplot."""
        ax.set_title("Joint Angles", color=Palette.FG, fontsize=9)  # type: ignore[attr-defined]
        ax.set_xlabel("Time (s)", color=Palette.FG_DIM, fontsize=8)  # type: ignore[attr-defined]
        ax.set_ylabel("Angle (deg)", color=Palette.FG_DIM, fontsize=8)  # type: ignore[attr-defined]
        ax.legend(fontsize=6, loc="best")  # type: ignore[attr-defined]

    def _label_torques_axis(self, ax: object) -> None:
        """Apply titles and legend to the joint-torques subplot."""
        ax.set_title("Joint Torques", color=Palette.FG, fontsize=9)  # type: ignore[attr-defined]
        ax.set_xlabel("Time (s)", color=Palette.FG_DIM, fontsize=8)  # type: ignore[attr-defined]
        ax.set_ylabel("Torque (Nm)", color=Palette.FG_DIM, fontsize=8)  # type: ignore[attr-defined]
        ax.legend(fontsize=6, loc="best")  # type: ignore[attr-defined]

    def _label_com_axis(self, ax: object) -> None:
        """Apply titles, legend, and aspect ratio to the COM-path subplot."""
        ax.set_title("COM Path", color=Palette.FG, fontsize=9)  # type: ignore[attr-defined]
        ax.set_xlabel("X (m)", color=Palette.FG_DIM, fontsize=8)  # type: ignore[attr-defined]
        ax.set_ylabel("Y (m)", color=Palette.FG_DIM, fontsize=8)  # type: ignore[attr-defined]
        ax.legend(fontsize=6, loc="best")  # type: ignore[attr-defined]
        ax.set_aspect("equal", adjustable="datalim")  # type: ignore[attr-defined]


# ==============================================================
# Main Window
# ==============================================================
