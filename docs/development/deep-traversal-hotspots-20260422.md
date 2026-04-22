# Deep Traversal Hotspot Review - 2026-04-22

Issue: https://github.com/D-sorganization/Movement-Optimizer/issues/272

## Summary

The generated assessment found repeated GUI member-chain access in
`src/movement_optimizer/gui/`. The actionable hotspots were in main-window
mixins that reached into sidebar and playback child widgets. This slice adds
facade methods on those widgets and routes the mixins through those facades.

## Changes

| Area | Resolution |
| --- | --- |
| `animation_control.py` playback label and speed access | Replaced direct child-widget access with `PlaybackControls.set_frame_position()`, `speed_multiplier()`, and `set_speed_multiplier_text()`. |
| `comparison_mixin.py` sidebar slider and button access | Replaced direct slider/button access with `ParameterSidebar.get_comparison_context()` and `set_comparison_available()`. |
| `main_window.py` cancel button access | Replaced direct cancel button access with `ParameterSidebar.set_cancellation_available()`. |
| `main_window.py` signal connection lists | Moved repeated signal wiring behind `connect_action_handlers()` methods on `ParameterSidebar` and `PlaybackControls`. |
| `main_window.py` animation timer connection | Justified as an owned `QTimer` connecting its `timeout` signal to the main window's animation step. |
| `__init__.py`, `file_operations.py`, `optimization_mixin.py`, `widgets.py` | Review found no new issue-specific code changes needed. Existing facade methods already protect the relevant boundaries or the file is a compatibility re-export. |

## Boundary Decision

The GUI still owns widget composition, but callers no longer need to traverse
into sidebar or playback-control internals for frame labels, speed values,
comparison controls, or cancellation state. The remaining one-hop owner access
(`self.sidebar`, `self.controls`) is the intended boundary between
`MainWindow`/mixins and focused GUI widgets.

## Validation

- `python -m pytest tests/test_gui_widgets.py tests/test_main_window.py -q`
- `python -m ruff check src/movement_optimizer/gui/animation_control.py src/movement_optimizer/gui/comparison_mixin.py src/movement_optimizer/gui/main_window.py src/movement_optimizer/gui/parameter_sidebar.py src/movement_optimizer/gui/playback_controls.py tests/test_gui_widgets.py tests/test_main_window.py`
- `python -m ruff format --check src/movement_optimizer/gui/animation_control.py src/movement_optimizer/gui/comparison_mixin.py src/movement_optimizer/gui/main_window.py src/movement_optimizer/gui/parameter_sidebar.py src/movement_optimizer/gui/playback_controls.py tests/test_gui_widgets.py tests/test_main_window.py`
