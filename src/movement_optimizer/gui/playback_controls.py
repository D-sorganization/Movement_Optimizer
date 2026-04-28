# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 D-sorganization
"""PlaybackControls: transport bar widget for animation playback."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QWidget


class PlaybackControls(QWidget):
    play_toggled = pyqtSignal()
    step_fwd = pyqtSignal()
    step_back = pyqtSignal()
    rewind = pyqtSignal()
    speed_changed = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.btn_rewind = QPushButton("\u23ee")
        self.btn_rewind.setToolTip("Rewind to beginning")
        self.btn_rewind.setAccessibleName("Rewind to beginning")

        self.btn_back = QPushButton("\u25c0")
        self.btn_back.setToolTip("Step backward one frame")
        self.btn_back.setAccessibleName("Step backward one frame")

        self.btn_play = QPushButton("\u25b6 Play")
        self.btn_play.setProperty("class", "primary")
        self.btn_play.setToolTip("Play or pause animation")
        self.btn_play.setAccessibleName("Play or pause animation")

        self.btn_fwd = QPushButton("\u25b6")
        self.btn_fwd.setToolTip("Step forward one frame")
        self.btn_fwd.setAccessibleName("Step forward one frame")

        self.btn_rewind.clicked.connect(self.rewind.emit)
        self.btn_back.clicked.connect(self.step_back.emit)
        self.btn_play.clicked.connect(self.play_toggled.emit)
        self.btn_fwd.clicked.connect(self.step_fwd.emit)

        for btn in (self.btn_rewind, self.btn_back, self.btn_play, self.btn_fwd):
            layout.addWidget(btn)

        layout.addSpacing(12)
        speed_label_widget = QLabel("Speed:")
        layout.addWidget(speed_label_widget)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setAccessibleName("Speed")
        speed_label_widget.setBuddy(self.speed_slider)
        self.speed_slider.setRange(1, 30)
        self.speed_slider.setValue(10)
        self.speed_slider.setFixedWidth(100)
        self.speed_slider.valueChanged.connect(lambda v: self.speed_changed.emit(v / 10.0))
        layout.addWidget(self.speed_slider)

        self.speed_label = QLabel("1.0x")
        self.speed_label.setFixedWidth(40)
        layout.addWidget(self.speed_label)

        layout.addStretch()
        self.frame_label = QLabel("")
        layout.addWidget(self.frame_label)

    def connect_action_handlers(self, handlers: Mapping[str, Callable[..., None]]) -> None:
        """Connect playback signals to handlers supplied by the owning window."""
        self.play_toggled.connect(handlers["play_toggled"])
        self.step_fwd.connect(handlers["step_fwd"])
        self.step_back.connect(handlers["step_back"])
        self.rewind.connect(handlers["rewind"])
        self.speed_changed.connect(handlers["speed_changed"])

    def set_playing(self, playing: bool) -> None:
        if playing:
            self.btn_play.setText("\u23f8 Pause")
            self.btn_play.setToolTip("Pause animation")
            self.btn_play.setAccessibleName("Pause animation")
        else:
            self.btn_play.setText("\u25b6 Play")
            self.btn_play.setToolTip("Play animation")
            self.btn_play.setAccessibleName("Play animation")

    def set_frame_position(self, current_frame: int, total_frames: int) -> None:
        """Display the current animation frame as one-based progress text."""
        self.frame_label.setText(f"Frame {current_frame}/{total_frames}")

    def speed_multiplier(self) -> float:
        """Return the current playback speed multiplier."""
        return self.speed_slider.value() / 10.0

    def set_speed_multiplier_text(self, speed: float) -> None:
        """Display the current playback speed multiplier."""
        self.speed_label.setText(f"{speed:.1f}x")

    def set_playback_status(self, current_frame: int, total_frames: int, speed: float) -> None:
        """Update the frame and speed labels together."""
        self.set_frame_position(current_frame, total_frames)
        self.set_speed_multiplier_text(speed)
