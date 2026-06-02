# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""GUI tests for swingset and chain analysis tabs."""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QAbstractSpinBox, QLabel, QLineEdit, QSlider, QSplitter

from movement_optimizer.gui.app_icon import movement_optimizer_icon, movement_optimizer_icon_path
from movement_optimizer.gui.main_window import MainWindow
from movement_optimizer.gui.motion_tabs import ChainDynamicsTab, NumericControl, SwingsetTab


def test_main_window_preserves_barbell_tabs_and_adds_motion_tabs(qapp) -> None:
    window = MainWindow()

    tab_names = [window.tabs.tabText(index).strip() for index in range(window.tabs.count())]

    assert tab_names[:7] == [
        "Bottoms Up Squat",
        "Full Squat",
        "Deadlift",
        "Bench Press",
        "Clean",
        "Jerk",
        "Snatch",
    ]
    assert tab_names[-2:] == ["Swingset Model", "Chain Dynamics"]


def test_main_window_uses_packaged_launcher_icon(qapp) -> None:
    qapp.setWindowIcon(movement_optimizer_icon())
    window = MainWindow()

    assert movement_optimizer_icon_path().name == "project_map.svg"
    assert not qapp.windowIcon().isNull()
    assert not window.windowIcon().isNull()


def test_analysis_tabs_disable_barbell_only_controls(qapp) -> None:
    window = MainWindow()
    window.tabs.setCurrentIndex(0)
    window._sync_motion_tab_controls()
    window.sidebar.opt_btn.setEnabled(True)
    window.sidebar.export_btn.setEnabled(True)

    window.tabs.setCurrentIndex(window.tabs.count() - 1)

    assert not window.sidebar.opt_btn.isEnabled()
    assert not window.sidebar.export_btn.isEnabled()
    assert window.controls.isEnabled()

    window.tabs.setCurrentIndex(0)

    assert window.sidebar.opt_btn.isEnabled()
    assert window.sidebar.export_btn.isEnabled()
    assert window.controls.isEnabled()


def test_layout_header_status_and_splitter_use_full_height(qapp) -> None:
    window = MainWindow()
    window.resize(1600, 900)
    window.show()
    qapp.processEvents()

    title = next(
        label
        for label in window.centralWidget().findChildren(QLabel)
        if label.text() == "Movement Optimizer"
    )
    splitter = window.centralWidget().findChild(QSplitter)

    assert title.geometry().y() <= 12
    assert window.status_label.geometry().height() <= 24
    assert splitter is not None
    assert splitter.geometry().height() > 700


def test_swingset_and_chain_tabs_run_local_simulations(qapp) -> None:
    swingset = SwingsetTab()
    chain = ChainDynamicsTab()

    swingset._controls["policy_steps"].set_value(30)
    swingset._optimize_policy()
    chain._simulate()

    assert "Best height" in swingset.metric_label.text()
    assert "peak tip speed" in chain.metric_label.text()


def test_swingset_tab_configures_seat_placement_percent(qapp) -> None:
    swingset = SwingsetTab()

    swingset._controls["seat_placement"].set_value(62.5)
    config = swingset._config()

    assert config.seat_placement_thigh_fraction == pytest.approx(0.625)


def test_bottom_playback_controls_drive_analysis_tabs(qapp) -> None:
    window = MainWindow()
    window.tabs.setCurrentIndex(window.tabs.count() - 2)
    swing_tab = window.tabs.currentWidget()
    swing_tab._controls["policy_steps"].set_value(30)

    window._toggle_play()

    assert swing_tab.playback_status()[2]
    assert window.controls.btn_play.text() == "Pause"

    window._step_fwd()

    assert swing_tab.playback_status()[2] is False
    assert swing_tab.playback_status()[0] == 2

    window.tabs.setCurrentIndex(window.tabs.count() - 1)
    window._toggle_play()
    chain_tab = window.tabs.currentWidget()

    assert chain_tab.playback_status()[2]
    window._jump_to_end()
    assert chain_tab.playback_status()[2] is False
    assert chain_tab.playback_status()[0] == chain_tab.playback_status()[1]


def test_motion_tabs_use_slider_text_controls_without_spinbox_arrows(qapp) -> None:
    swingset = SwingsetTab()
    chain = ChainDynamicsTab()

    assert not swingset.findChildren(QAbstractSpinBox)
    assert not chain.findChildren(QAbstractSpinBox)
    assert swingset.findChildren(QSlider)
    assert swingset.findChildren(QLineEdit)
    assert chain.findChildren(QSlider)
    assert chain.findChildren(QLineEdit)


def test_numeric_control_accepts_typed_values(qapp) -> None:
    control = NumericControl(0.0, 10.0, 1.0)

    control.edit.setText("4.25")
    control.edit.editingFinished.emit()

    assert control.value() == 4.25


def test_chain_tab_supports_free_segment_angles_and_realtime_speed(qapp) -> None:
    chain = ChainDynamicsTab()
    chain.tie_segments.setChecked(False)
    chain._controls["segments"].set_value(3)
    chain.angle_edit.setText("9999.0, 0.1, -9999.0")
    chain._controls["dt"].set_value(0.02)
    chain._controls["speed"].set_value(2.0)

    chain._simulate()

    assert chain._rollout is not None
    assert chain._playback_interval_ms() == 10


def test_chain_tab_converts_typed_degrees(qapp) -> None:
    chain = ChainDynamicsTab()
    chain.tie_segments.setChecked(False)
    chain.use_degrees.setChecked(True)
    chain._controls["segments"].set_value(2)
    chain.angle_edit.setText("180, -90")

    state = chain._state()

    assert state.angles_rad[0] == pytest.approx(np.pi)
    assert state.angles_rad[1] == pytest.approx(-np.pi / 2.0)
    assert "degrees" in chain.angle_edit.placeholderText()


def test_canvas_keeps_anchor_projection_fixed(qapp) -> None:
    from movement_optimizer.gui.motion_tabs import MotionCanvas

    canvas = MotionCanvas()
    canvas.resize(500, 400)
    canvas.set_scene([(0.0, 0.0), (0.2, 1.0)])
    first_anchor = canvas._projector()((0.0, 0.0))
    canvas.set_scene([(0.0, 0.0), (-0.8, 2.0), (0.7, 3.0)])
    second_anchor = canvas._projector()((0.0, 0.0))

    assert second_anchor.x() == pytest.approx(first_anchor.x())
    assert second_anchor.y() == pytest.approx(first_anchor.y())


def test_chain_rollout_keeps_physical_anchor_fixed(qapp) -> None:
    chain = ChainDynamicsTab()
    chain._simulate()

    assert chain._rollout is not None
    np.testing.assert_allclose(chain._rollout.positions[:, 0, :], 0.0)
