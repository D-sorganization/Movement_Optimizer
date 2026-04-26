"""UI construction helpers for the main window."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .exercise_tab import ExerciseTab
from .widgets import ParameterSidebar, PlaybackControls


def build_central_widget(
    window: QWidget,
    exercise_configs: tuple[tuple[str, str], ...],
) -> tuple[QWidget, ParameterSidebar, QTabWidget, list[ExerciseTab], PlaybackControls, QLabel]:
    """Build the central widget and top-level layout components."""
    central = QWidget()
    outer = QVBoxLayout(central)
    outer.setContentsMargins(8, 8, 8, 8)

    title = QLabel("Movement Optimizer")
    title.setProperty("class", "title")
    outer.addWidget(title)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    outer.addWidget(splitter, stretch=1)

    sidebar = ParameterSidebar()
    splitter.addWidget(sidebar)

    right = QWidget()
    right_lay = QVBoxLayout(right)
    right_lay.setContentsMargins(0, 0, 0, 0)

    tabs = QTabWidget()
    exercise_tabs: list[ExerciseTab] = []
    for i, (display_name, _) in enumerate(exercise_configs):
        tab = ExerciseTab(display_name)
        tabs.addTab(tab, f"  {display_name}  ")
        tabs.setTabToolTip(i, f"View and optimize {display_name} trajectory")
        exercise_tabs.append(tab)
    right_lay.addWidget(tabs)

    controls = PlaybackControls()
    right_lay.addWidget(controls)

    splitter.addWidget(right)
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)

    status_label = QLabel("Ready")
    status_label.setProperty("class", "dim")
    outer.addWidget(status_label)

    return central, sidebar, tabs, exercise_tabs, controls, status_label
