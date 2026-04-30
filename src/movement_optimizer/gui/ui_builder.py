# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""UI construction helpers for the main window."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
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
) -> tuple[
    QWidget,
    ParameterSidebar,
    QTabWidget,
    list[ExerciseTab],
    PlaybackControls,
    QLabel,
    QPushButton,
]:
    """Build the central widget and top-level layout components.

    Returns a tuple of:
        (central, sidebar, tabs, exercise_tabs, controls, status_label,
         sidebar_toggle_btn)

    The caller is responsible for connecting ``sidebar_toggle_btn.clicked``
    to the appropriate handler.
    """
    central = QWidget()
    outer = QVBoxLayout(central)
    outer.setContentsMargins(8, 8, 8, 8)

    title = QLabel("Movement Optimizer")
    title.setProperty("class", "title")
    outer.addWidget(title)

    # Horizontal area: toggle button + splitter (sidebar | right panel).
    content_row = QHBoxLayout()
    content_row.setContentsMargins(0, 0, 0, 0)
    content_row.setSpacing(0)
    outer.addLayout(content_row, stretch=1)

    # Sidebar collapse / expand toggle button.
    sidebar_toggle_btn = QPushButton("◀")
    sidebar_toggle_btn.setToolTip("Collapse/expand sidebar")
    sidebar_toggle_btn.setFixedWidth(20)
    sidebar_toggle_btn.setMinimumHeight(36)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    content_row.addWidget(splitter, stretch=1)
    content_row.addWidget(sidebar_toggle_btn)

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

    return central, sidebar, tabs, exercise_tabs, controls, status_label, sidebar_toggle_btn
