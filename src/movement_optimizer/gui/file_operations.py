# Copyright (c) 2026 D-Sorganization. All rights reserved.
# mypy: disable-error-code="misc,arg-type"
# Mixin pattern: methods annotate self as MainWindow to access its attributes.
"""File I/O helpers extracted from MainWindow.

Provides CSV export, solution save/load, GIF export, and plot export
as a mixin class so MainWindow stays focused on layout and coordination.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from typing import TYPE_CHECKING, Any

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ..export import export_animation_gif, export_plots_pdf, export_plots_png
from ..export_excel import export_to_excel
from ..import_results import import_result_from_json
from ..persistence import InvalidStateFileError, load_solution, save_solution
from ..trajectory import OptimizationResult

if TYPE_CHECKING:
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class FileOperationsMixin:
    """Mixin providing file I/O actions for MainWindow."""

    def _export(self: MainWindow) -> None:  # type: ignore[misc]
        idx = self.tabs.currentIndex()
        r, _fi, _body, _dyn = self._snapshot_idx_state(idx)
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
        _write_csv(self, path, r)

    def _save_solution(self: MainWindow) -> None:  # type: ignore[misc]
        idx = self.tabs.currentIndex()
        r, _fi, _body, _dyn = self._snapshot_idx_state(idx)
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
            body_params = self.sidebar.get_body_params_dict()
            _, etype = self.EXERCISE_CONFIGS[idx]
            bar, _dur, _smooth = self.sidebar.get_optimization_params()
            save_solution(path, r, body_params, etype, bar)
            self.status_label.setText(f"Saved: {os.path.basename(path)}")
        except (OSError, TypeError, ValueError) as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _load_solution(self: MainWindow) -> None:  # type: ignore[misc]
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
        except InvalidStateFileError as e:
            QMessageBox.critical(self, "Invalid Solution File", str(e))
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
            QMessageBox.critical(self, "Load Error", str(e))

    def _export_video(self: MainWindow) -> None:  # type: ignore[misc]
        idx = self.tabs.currentIndex()
        r, _fi, body, dyn = self._snapshot_idx_state(idx)
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

    def _export_plots(self: MainWindow) -> None:  # type: ignore[misc]
        idx = self.tabs.currentIndex()
        r, _fi, _body, _dyn = self._snapshot_idx_state(idx)
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

    def _export_excel(self: MainWindow) -> None:  # type: ignore[misc]
        idx = self.tabs.currentIndex()
        r, _fi, body, _dyn = self._snapshot_idx_state(idx)
        if r is None:
            return
        exercise_name = self.EXERCISE_CONFIGS[idx][0]
        name = exercise_name.lower().replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save as Excel (.xlsx)",
            f"{name}_results.xlsx",
            "Excel Files (*.xlsx)",
        )
        if not path:
            return
        try:
            mass = getattr(body, "mass", None)
            height = getattr(body, "height", None)
            export_to_excel(r, path, exercise_name=exercise_name, body_mass_kg=mass, body_height_m=height)
            self.status_label.setText(f"Exported: {os.path.basename(path)}")
            QMessageBox.information(self, "Exported", f"Excel workbook saved to:\n{path}")
        except ImportError as e:
            QMessageBox.critical(self, "Missing Dependency", str(e))
        except (OSError, ValueError, RuntimeError) as e:
            QMessageBox.critical(self, "Export Error", str(e))


def _write_csv(win: Any, path: str, r: OptimizationResult) -> None:
    """Write trajectory data to a CSV file."""
    import numpy as np

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
        win.status_label.setText(f"Exported: {os.path.basename(path)}")
        QMessageBox.information(win, "Exported", f"Saved to:\n{path}")
    except (OSError, ValueError) as e:
        QMessageBox.critical(win, "Export Error", str(e))
