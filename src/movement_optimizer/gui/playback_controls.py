"""PlaybackControls: transport bar widget for animation playback."""

from __future__ import annotations

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
        self.btn_rewind.setToolTip("Rewind to start")
        self.btn_rewind.setAccessibleName("Rewind to start")
        self.btn_back = QPushButton("\u25c0")
        self.btn_back.setToolTip("Step backward")
        self.btn_back.setAccessibleName("Step backward")
        self.btn_play = QPushButton("\u25b6 Play")
        self.btn_play.setToolTip("Play animation")
        self.btn_play.setAccessibleName("Play animation")
        self.btn_play.setProperty("class", "primary")
        self.btn_fwd = QPushButton("\u25b6")
        self.btn_fwd.setToolTip("Step forward")
        self.btn_fwd.setAccessibleName("Step forward")

        self.btn_rewind.clicked.connect(self.rewind.emit)
        self.btn_back.clicked.connect(self.step_back.emit)
        self.btn_play.clicked.connect(self.play_toggled.emit)
        self.btn_fwd.clicked.connect(self.step_fwd.emit)

        for btn in (self.btn_rewind, self.btn_back, self.btn_play, self.btn_fwd):
            layout.addWidget(btn)

        layout.addSpacing(12)
        layout.addWidget(QLabel("Speed:"))

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 30)
        self.speed_slider.setValue(10)
        self.speed_slider.setFixedWidth(100)
        self.speed_slider.setAccessibleName("Playback speed")
        self.speed_slider.valueChanged.connect(lambda v: self.speed_changed.emit(v / 10.0))
        layout.addWidget(self.speed_slider)

        self.speed_label = QLabel("1.0x")
        self.speed_label.setFixedWidth(40)
        layout.addWidget(self.speed_label)

        layout.addStretch()
        self.frame_label = QLabel("")
        layout.addWidget(self.frame_label)

    def set_playing(self, playing: bool) -> None:
        self.btn_play.setText("\u23f8 Pause" if playing else "\u25b6 Play")
        self.btn_play.setToolTip("Pause animation" if playing else "Play animation")
        self.btn_play.setAccessibleName("Pause animation" if playing else "Play animation")
