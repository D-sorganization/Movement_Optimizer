"""GUI package for the Movement Optimizer.

The original monolithic ``gui.py`` has been split into a package with
focused sub-modules:

- ``main_window``  -- :class:`MainWindow`
- ``exercise_tab`` -- :class:`ExerciseTab`
- ``comparison_dialog`` -- :class:`ComparisonDialog`
- ``widgets`` -- :class:`LabelledSlider`, :class:`ParameterSidebar`,
  :class:`PlaybackControls`

All public names are re-exported here for backward compatibility so that
``from movement_optimizer.gui import MainWindow`` continues to work.
"""

from __future__ import annotations

from .comparison_dialog import ComparisonDialog as ComparisonDialog
from .exercise_tab import ExerciseTab as ExerciseTab
from .main_window import MainWindow as MainWindow
from .widgets import LabelledSlider as LabelledSlider
from .widgets import ParameterSidebar as ParameterSidebar
from .widgets import PlaybackControls as PlaybackControls

__all__ = [
    "ComparisonDialog",
    "ExerciseTab",
    "LabelledSlider",
    "MainWindow",
    "ParameterSidebar",
    "PlaybackControls",
]
