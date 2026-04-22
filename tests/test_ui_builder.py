import pytest
from PyQt6.QtWidgets import QApplication, QLabel, QTabWidget, QWidget

from movement_optimizer.gui.ui_builder import build_central_widget
from movement_optimizer.gui.widgets import ParameterSidebar, PlaybackControls


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


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

    def test_sidebar_exposes_comparison_trial_data(self, qapp):
        window = QWidget()
        exercise_configs = (("Squat", "squat"),)
        (
            _central,
            sidebar,
            _tabs,
            _exercise_tabs,
            _controls,
            _status_label,
        ) = build_central_widget(window, exercise_configs)

        sidebar.mass_slider.set_value(82.0)
        sidebar.height_slider.set_value(1.83)
        sidebar.ll_slider.set_value(1.08)
        sidebar.ul_slider.set_value(0.97)
        sidebar.to_slider.set_value(1.04)
        sidebar.bar_slider.set_value(92.0)

        body_params, bar_mass = sidebar.get_comparison_trial_data()

        assert body_params["body_mass"] == pytest.approx(sidebar.mass_slider.value())
        assert body_params["height"] == pytest.approx(sidebar.height_slider.value())
        assert body_params["seg_multipliers"]["lower_leg"] == pytest.approx(
            sidebar.ll_slider.value()
        )
        assert body_params["seg_multipliers"]["upper_leg"] == pytest.approx(
            sidebar.ul_slider.value()
        )
        assert body_params["seg_multipliers"]["torso"] == pytest.approx(sidebar.to_slider.value())
        assert bar_mass == pytest.approx(sidebar.bar_slider.value())
