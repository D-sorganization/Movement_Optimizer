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
