# Copyright (c) 2026 D-Sorganization. All rights reserved.
import pytest
from PyQt6.QtWidgets import QLabel, QTabWidget, QWidget

from movement_optimizer.gui.ui_builder import build_central_widget
from movement_optimizer.gui.widgets import ParameterSidebar, PlaybackControls


class TestUIBuilder:
    def test_build_central_widget(self, qapp):
        window = QWidget()
        exercise_configs = (
            ("Squat", "squat"),
            ("Deadlift", "deadlift"),
        )
        (
            central,
            sidebar,
            tabs,
            exercise_tabs,
            controls,
            status_label,
            _sidebar_toggle_btn,
        ) = build_central_widget(window, exercise_configs)

        assert isinstance(central, QWidget)
        assert isinstance(sidebar, ParameterSidebar)
        assert isinstance(tabs, QTabWidget)
        assert len(exercise_tabs) == 2
        assert isinstance(controls, PlaybackControls)
        assert isinstance(status_label, QLabel)

        assert tabs.count() == 2
        assert tabs.tabText(0) == "  Squat  "
        assert tabs.tabText(1) == "  Deadlift  "

    def test_playback_controls_expose_frame_and_speed_helpers(self, qapp):
        window = QWidget()
        exercise_configs = (("Squat", "squat"),)
        (
            _central,
            _sidebar,
            _tabs,
            _exercise_tabs,
            controls,
            _status_label,
            _sidebar_toggle_btn,
        ) = build_central_widget(window, exercise_configs)

        controls.speed_slider.setValue(15)
        controls.set_playback_status(4, 12, 1.5)

        assert controls.frame_label.text() == "Frame 4/12"
        assert controls.speed_label.text() == "1.5x"
        assert controls.speed_multiplier() == pytest.approx(1.5)
