# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""PyQt6 tabs for swingset policy search and chain dynamics analysis."""

from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise

import numpy as np
from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from movement_optimizer.models.chain_dynamics import (
    ChainConfig,
    ChainRollout,
    ChainState,
    initial_catenary_angles,
    simulate_chain,
)
from movement_optimizer.models.swingset import (
    DEFAULT_POLICY_DT_S,
    CyclicPolicySearchResult,
    HumanSegmentSpec,
    SwingPose,
    SwingRollout,
    SwingSetConfig,
    build_swingset_snapshot,
    optimize_cyclic_policy,
)

ACCENT = QColor("#4ec9b0")
CHAIN = QColor("#c8d1df")
BODY = QColor("#7aa2f7")
LEG = QColor("#f3c969")
ARM = QColor("#d386f2")
SURFACE = QColor("#1f242d")
GRID = QColor("#3a4252")


class NumericControl(QWidget):
    """Slider plus typed value field without spin-box arrows."""

    valueChanged = pyqtSignal(float)  # noqa: N815 - Qt signal naming convention.

    def __init__(
        self,
        lower: float,
        upper: float,
        value: float,
        *,
        integer: bool = False,
        decimals: int = 3,
        steps: int = 1000,
    ) -> None:
        super().__init__()
        if upper <= lower:
            raise ValueError("upper must be greater than lower")
        self._lower = lower
        self._upper = upper
        self._integer = integer
        self._decimals = 0 if integer else decimals
        self._steps = max(1, int(upper - lower) if integer else steps)
        self._value = self._coerce(value)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, self._steps)
        self.slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.edit = QLineEdit()
        self.edit.setFixedWidth(72)
        self.edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.slider, stretch=1)
        layout.addWidget(self.edit)

        self.slider.valueChanged.connect(self._on_slider_changed)
        self.edit.editingFinished.connect(self._on_text_changed)
        self._sync_widgets()

    def value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        new_value = self._coerce(value)
        if new_value == self._value:
            self._sync_widgets()
            return
        self._value = new_value
        self._sync_widgets()
        self.valueChanged.emit(self._value)

    def _coerce(self, value: float) -> float:
        bounded = min(max(float(value), self._lower), self._upper)
        return float(round(bounded)) if self._integer else bounded

    def _value_to_slider(self, value: float) -> int:
        ratio = (value - self._lower) / (self._upper - self._lower)
        return round(ratio * self._steps)

    def _slider_to_value(self, position: int) -> float:
        ratio = position / self._steps
        return self._coerce(self._lower + ratio * (self._upper - self._lower))

    def _sync_widgets(self) -> None:
        slider_value = self._value_to_slider(self._value)
        if self.slider.value() != slider_value:
            self.slider.blockSignals(True)
            self.slider.setValue(slider_value)
            self.slider.blockSignals(False)
        text = f"{int(self._value)}" if self._integer else f"{self._value:.{self._decimals}f}"
        if self.edit.text() != text:
            self.edit.setText(text)

    def _on_slider_changed(self, position: int) -> None:
        self._value = self._slider_to_value(position)
        self._sync_widgets()
        self.valueChanged.emit(self._value)

    def _on_text_changed(self) -> None:
        try:
            parsed = float(self.edit.text())
        except ValueError:
            self._sync_widgets()
            return
        self.set_value(parsed)


class MotionCanvas(QWidget):
    """Side-view renderer for chain and articulated rider snapshots."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(360)
        self._chain_nodes: list[tuple[float, float]] = []
        self._body_points: dict[str, tuple[float, float]] = {}

    def set_scene(
        self,
        chain_nodes: list[tuple[float, float]],
        body_points: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        self._chain_nodes = chain_nodes
        self._body_points = body_points or {}
        self.update()

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), SURFACE)
        if not self._chain_nodes:
            return
        projector = self._projector()
        chain_points = [projector(point) for point in self._chain_nodes]
        self._draw_grid(painter)
        self._draw_polyline(painter, chain_points, CHAIN, 3)
        self._draw_body(painter, projector)
        painter.setBrush(ACCENT)
        painter.setPen(QPen(ACCENT, 1))
        for point in chain_points[:1] + chain_points[-1:]:
            painter.drawEllipse(point, 5, 5)

    def _projector(self) -> Callable[[tuple[float, float]], QPointF]:
        all_points = self._chain_nodes + list(self._body_points.values())
        anchor_x, anchor_y = self._chain_nodes[0]
        span_x = max(max(abs(point[0] - anchor_x) for point in all_points) * 2.0, 0.5)
        span_y = max(max(abs(point[1] - anchor_y) for point in all_points), 0.5)
        scale = 0.84 * min(self.width() / span_x, self.height() / span_y)
        offset_x = 0.5 * self.width() - scale * anchor_x
        offset_y = 32.0 - scale * anchor_y

        def _project(point: tuple[float, float]) -> QPointF:
            x, y = point
            return QPointF(offset_x + scale * x, offset_y + scale * y)

        return _project

    def _draw_grid(self, painter: QPainter) -> None:
        painter.setPen(QPen(GRID, 1))
        step = 40
        for x in range(0, self.width(), step):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), step):
            painter.drawLine(0, y, self.width(), y)

    def _draw_polyline(
        self,
        painter: QPainter,
        points: list[QPointF],
        color: QColor,
        width: int,
    ) -> None:
        painter.setPen(QPen(color, width))
        for start, end in pairwise(points):
            painter.drawLine(start, end)

    def _draw_body(
        self,
        painter: QPainter,
        projector: Callable[[tuple[float, float]], QPointF],
    ) -> None:
        if not self._body_points:
            return
        pairs = [
            ("hand", "elbow", ARM, 4),
            ("elbow", "shoulder", ARM, 4),
            ("shoulder", "waist", BODY, 5),
            ("waist", "hip", BODY, 5),
            ("hip", "knee", LEG, 4),
            ("knee", "foot", LEG, 4),
        ]
        for start, end, color, width in pairs:
            painter.setPen(QPen(color, width))
            painter.drawLine(
                projector(self._body_points[start]),
                projector(self._body_points[end]),
            )


class SwingsetTab(QWidget):
    """Interactive swingset model tab with cyclic policy optimization."""

    def __init__(self) -> None:
        super().__init__()
        self.canvas = MotionCanvas()
        self.metric_label = QLabel()
        self._controls: dict[str, NumericControl] = {}
        self._rollout: SwingRollout | None = None
        self._frame_index = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_frame)
        self._build_ui()
        self._refresh_static()

    def _build_ui(self) -> None:
        layout = QGridLayout(self)
        layout.addWidget(self.canvas, 0, 0, 4, 1)
        layout.addWidget(self._build_chain_group(), 0, 1)
        layout.addWidget(self._build_body_group(), 1, 1)
        layout.addWidget(self._build_policy_group(), 2, 1)
        layout.addWidget(self.metric_label, 4, 0, 1, 2)
        layout.setColumnStretch(0, 1)

    def _build_chain_group(self) -> QGroupBox:
        group = QGroupBox("Swingset")
        form = QFormLayout(group)
        self._add_control(form, "segments", "Chain segments", 3, 40, 14, integer=True)
        self._add_control(form, "chain_length", "Chain length m", 1.0, 5.0, 2.4)
        self._add_control(form, "link_mass", "Link mass kg", 0.01, 2.0, 0.16)
        self._add_control(form, "seat_mass", "Seat mass kg", 0.5, 25.0, 4.5)
        self._add_control(form, "seat_placement", "Seat placement %", 1.0, 100.0, 35.0)
        return group

    def _build_body_group(self) -> QGroupBox:
        group = QGroupBox("Rider")
        form = QFormLayout(group)
        self._add_control(form, "torso_len", "Torso length m", 0.2, 1.2, 0.62)
        self._add_control(form, "torso_mass", "Torso mass kg", 5.0, 80.0, 28.0)
        self._add_control(form, "thigh_len", "Thigh length m", 0.15, 0.9, 0.46)
        self._add_control(form, "thigh_mass", "Thigh mass kg", 1.0, 25.0, 8.0)
        self._add_control(form, "shank_len", "Shank length m", 0.15, 0.9, 0.45)
        self._add_control(form, "shank_mass", "Shank mass kg", 1.0, 20.0, 5.5)
        self._add_control(form, "arm_len", "Arm segment m", 0.1, 0.8, 0.30)
        self._add_control(form, "arm_mass", "Arm segment kg", 0.2, 10.0, 2.0)
        return group

    def _build_policy_group(self) -> QGroupBox:
        group = QGroupBox("Policy")
        layout = QVBoxLayout(group)
        form = QFormLayout()
        self._add_control(form, "policy_steps", "Search steps", 60, 500, 220, integer=True)
        self._add_control(form, "speed", "Playback speed", 0.25, 4.0, 1.0, refresh=False)
        layout.addLayout(form)
        row = QHBoxLayout()
        optimize_button = QPushButton("Optimize Cyclic Policy")
        optimize_button.clicked.connect(self._optimize_policy)
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self._toggle_playback)
        row.addWidget(optimize_button)
        row.addWidget(self.play_button)
        layout.addLayout(row)
        return group

    def _add_control(
        self,
        form: QFormLayout,
        key: str,
        label: str,
        lower: float,
        upper: float,
        value: float,
        *,
        integer: bool = False,
        refresh: bool = True,
    ) -> None:
        control = NumericControl(lower, upper, value, integer=integer)
        if refresh:
            control.valueChanged.connect(self._refresh_static)
        self._controls[key] = control
        form.addRow(label, control)

    def _config(self) -> SwingSetConfig:
        arm = HumanSegmentSpec(self._value("arm_len"), self._value("arm_mass"))
        return SwingSetConfig(
            chain_segments=int(self._value("segments")),
            chain_length_m=self._value("chain_length"),
            chain_link_mass_kg=self._value("link_mass"),
            seat_mass_kg=self._value("seat_mass"),
            seat_placement_thigh_fraction=self._value("seat_placement") / 100.0,
            torso=HumanSegmentSpec(self._value("torso_len"), self._value("torso_mass")),
            thigh=HumanSegmentSpec(self._value("thigh_len"), self._value("thigh_mass")),
            shank=HumanSegmentSpec(self._value("shank_len"), self._value("shank_mass")),
            upper_arm=arm,
            forearm=arm,
        )

    def _value(self, key: str) -> float:
        return self._controls[key].value()

    def _refresh_static(self) -> None:
        self._timer.stop()
        self.play_button.setText("Play")
        self._rollout = None
        config = self._config()
        pose = SwingPose(
            swing_angle_rad=0.12,
            torso_lean_rad=0.1,
            hip_angle_rad=0.2,
            knee_angle_rad=-0.2,
            shoulder_angle_rad=-0.35,
            elbow_angle_rad=0.45,
        )
        snapshot = build_swingset_snapshot(config, pose)
        self._render_snapshot(snapshot)
        self.metric_label.setText(
            f"Rider mass {config.rider_mass_kg:.1f} kg | "
            f"hand constraint {snapshot.hand_chain_error_m:.3f} m | "
            f"seat constraint {snapshot.seat_chain_error_m:.3f} m"
        )

    def _optimize_policy(self) -> None:
        result = optimize_cyclic_policy(
            self._config(),
            steps=int(self._value("policy_steps")),
            dt_s=DEFAULT_POLICY_DT_S,
        )
        self._set_policy_result(result)

    def _set_policy_result(self, result: CyclicPolicySearchResult) -> None:
        self._rollout = result.rollout
        self._frame_index = 0
        self._render_snapshot(result.rollout.snapshots[0])
        params = result.parameters
        self.metric_label.setText(
            f"Best height {result.objective_height_m:.3f} m | "
            f"peak angle {np.rad2deg(result.rollout.metrics.max_abs_swing_angle_rad):.1f} deg | "
            f"freq {params.frequency_hz:.2f} Hz"
        )

    def _render_snapshot(self, snapshot) -> None:
        self.canvas.set_scene(
            [tuple(point) for point in snapshot.chain_nodes],
            {key: tuple(value) for key, value in snapshot.points.items()},
        )

    def _toggle_playback(self) -> None:
        if self._rollout is None:
            self._optimize_policy()
        if self._timer.isActive():
            self._timer.stop()
            self.play_button.setText("Play")
            return
        self.play_button.setText("Pause")
        self._timer.start(self._playback_interval_ms(DEFAULT_POLICY_DT_S))

    def playback_toggle(self) -> None:
        self._toggle_playback()

    def playback_step_forward(self) -> None:
        self._ensure_rollout()
        if self._rollout is None:
            return
        self._timer.stop()
        self.play_button.setText("Play")
        self._frame_index = min(self._frame_index + 1, len(self._rollout.snapshots) - 1)
        self._render_snapshot(self._rollout.snapshots[self._frame_index])

    def playback_step_back(self) -> None:
        self._ensure_rollout()
        if self._rollout is None:
            return
        self._timer.stop()
        self.play_button.setText("Play")
        self._frame_index = max(self._frame_index - 1, 0)
        self._render_snapshot(self._rollout.snapshots[self._frame_index])

    def playback_rewind(self) -> None:
        self._ensure_rollout()
        if self._rollout is None:
            return
        self._timer.stop()
        self.play_button.setText("Play")
        self._frame_index = 0
        self._render_snapshot(self._rollout.snapshots[self._frame_index])

    def playback_jump_to_end(self) -> None:
        self._ensure_rollout()
        if self._rollout is None:
            return
        self._timer.stop()
        self.play_button.setText("Play")
        self._frame_index = len(self._rollout.snapshots) - 1
        self._render_snapshot(self._rollout.snapshots[self._frame_index])

    def set_playback_speed(self, speed: float) -> None:
        self._controls["speed"].set_value(speed)
        if self._timer.isActive():
            self._timer.start(self._playback_interval_ms(DEFAULT_POLICY_DT_S))

    def playback_status(self) -> tuple[int, int, bool]:
        total = len(self._rollout.snapshots) if self._rollout is not None else 0
        return self._frame_index + 1 if total else 0, total, self._timer.isActive()

    def _ensure_rollout(self) -> None:
        if self._rollout is None:
            self._optimize_policy()

    def _advance_frame(self) -> None:
        if self._rollout is None:
            return
        self._frame_index = (self._frame_index + 1) % len(self._rollout.snapshots)
        self._render_snapshot(self._rollout.snapshots[self._frame_index])
        self._timer.start(self._playback_interval_ms(DEFAULT_POLICY_DT_S))

    def _playback_interval_ms(self, dt_s: float) -> int:
        speed = max(0.05, self._value("speed"))
        return max(10, round(1000.0 * dt_s / speed))


class ChainDynamicsTab(QWidget):
    """Interactive chain whip-motion analysis tab."""

    def __init__(self) -> None:
        super().__init__()
        self.canvas = MotionCanvas()
        self.metric_label = QLabel()
        self.angle_edit = QLineEdit()
        self.tie_segments = QCheckBox("Tie segment starts with sag profile")
        self.tie_segments.setChecked(True)
        self.use_degrees = QCheckBox("Use degrees for typed segment angles")
        self._controls: dict[str, NumericControl] = {}
        self._rollout: ChainRollout | None = None
        self._frame_index = 0
        self._dt_s = 0.01
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_frame)
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)
        controls = QGroupBox("Chain")
        form = QFormLayout(controls)
        self._add_control(form, "segments", "Segments", 2, 60, 16, integer=True)
        self._add_control(form, "length", "Link length m", 0.03, 1.0, 0.18)
        self._add_control(form, "mass", "Link mass kg", 0.01, 4.0, 0.12)
        self._add_control(form, "sag", "Tied sag", 0.0, 180.0, 0.35)
        self._add_control(form, "kick", "Initial velocity", 0.0, 2.0, 0.6)
        self._add_control(form, "steps", "Simulation steps", 30, 600, 180, integer=True)
        self._add_control(form, "dt", "Time step s", 0.002, 0.05, 0.01)
        self._add_control(form, "speed", "Playback speed", 0.25, 4.0, 1.0, refresh=False)
        self.tie_segments.stateChanged.connect(self._refresh)
        form.addRow("", self.tie_segments)
        self.use_degrees.stateChanged.connect(self._refresh_angle_placeholder)
        self.use_degrees.stateChanged.connect(self._refresh)
        form.addRow("", self.use_degrees)
        self._refresh_angle_placeholder()
        self.angle_edit.editingFinished.connect(self._refresh)
        form.addRow("Segment angles", self.angle_edit)
        layout.addWidget(controls)
        row = QHBoxLayout()
        simulate_button = QPushButton("Simulate Whip")
        simulate_button.clicked.connect(self._simulate)
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self._toggle_playback)
        row.addWidget(simulate_button)
        row.addWidget(self.play_button)
        layout.addLayout(row)
        layout.addWidget(self.metric_label)

    def _add_control(
        self,
        form: QFormLayout,
        key: str,
        label: str,
        lower: float,
        upper: float,
        value: float,
        *,
        integer: bool = False,
        refresh: bool = True,
    ) -> None:
        control = NumericControl(lower, upper, value, integer=integer)
        if refresh:
            control.valueChanged.connect(self._refresh)
        self._controls[key] = control
        form.addRow(label, control)

    def _config(self) -> ChainConfig:
        return ChainConfig(
            segment_count=int(self._value("segments")),
            segment_length_m=self._value("length"),
            link_mass_kg=self._value("mass"),
        )

    def _state(self) -> ChainState:
        config = self._config()
        angles = (
            initial_catenary_angles(config.segment_count, self._angle_to_rad(self._value("sag")))
            if self.tie_segments.isChecked()
            else self._typed_angles(config.segment_count)
        )
        velocities = self._value("kick") * np.sin(np.linspace(0.0, np.pi, config.segment_count))
        return ChainState(angles, velocities)

    def _typed_angles(self, segment_count: int) -> np.ndarray:
        raw = self.angle_edit.text().strip()
        if not raw:
            return np.zeros(segment_count, dtype=np.float64)
        values = np.asarray([float(part.strip()) for part in raw.split(",")], dtype=np.float64)
        if values.size != segment_count:
            raise ValueError(f"Expected {segment_count} segment angles")
        return np.deg2rad(values) if self.use_degrees.isChecked() else values

    def _angle_to_rad(self, value: float) -> float:
        return float(np.deg2rad(value)) if self.use_degrees.isChecked() else value

    def _refresh_angle_placeholder(self) -> None:
        unit = "degrees" if self.use_degrees.isChecked() else "radians"
        self._controls["sag"].set_value(20.0 if self.use_degrees.isChecked() else 0.35)
        self.angle_edit.setPlaceholderText(f"comma-separated {unit}, one per segment")

    def _value(self, key: str) -> float:
        return self._controls[key].value()

    def _refresh(self) -> None:
        self._timer.stop()
        self.play_button.setText("Play")
        self._rollout = None
        try:
            config = self._config()
            state = self._state()
            positions = state.node_positions(config)
            self.canvas.set_scene([tuple(point) for point in positions])
            metrics = state.metrics(config)
            curvature = (
                np.rad2deg(metrics.max_curvature_rad)
                if self.use_degrees.isChecked()
                else metrics.max_curvature_rad
            )
            unit = "deg" if self.use_degrees.isChecked() else "rad"
            self.metric_label.setText(
                f"Tip speed {metrics.tip_speed_m_s:.3f} m/s | curvature {curvature:.3f} {unit}"
            )
        except ValueError as exc:
            self.metric_label.setText(str(exc))

    def _simulate(self) -> None:
        try:
            self._dt_s = self._value("dt")
            self._rollout = simulate_chain(
                self._config(),
                self._state(),
                steps=int(self._value("steps")),
                dt_s=self._dt_s,
            )
        except ValueError as exc:
            self.metric_label.setText(str(exc))
            return
        self._frame_index = 0
        self._render_chain_frame()
        self.metric_label.setText(
            f"Frames {len(self._rollout.states)} | "
            f"peak tip speed {self._rollout.tip_speed_m_s.max():.3f} m/s | "
            f"real time {self._dt_s * (len(self._rollout.states) - 1):.2f} s"
        )

    def _toggle_playback(self) -> None:
        if self._rollout is None:
            self._simulate()
        if self._rollout is None:
            return
        if self._timer.isActive():
            self._timer.stop()
            self.play_button.setText("Play")
            return
        self.play_button.setText("Pause")
        self._timer.start(self._playback_interval_ms())

    def playback_toggle(self) -> None:
        self._toggle_playback()

    def playback_step_forward(self) -> None:
        self._ensure_rollout()
        if self._rollout is None:
            return
        self._timer.stop()
        self.play_button.setText("Play")
        self._frame_index = min(self._frame_index + 1, self._rollout.positions.shape[0] - 1)
        self._render_chain_frame()

    def playback_step_back(self) -> None:
        self._ensure_rollout()
        if self._rollout is None:
            return
        self._timer.stop()
        self.play_button.setText("Play")
        self._frame_index = max(self._frame_index - 1, 0)
        self._render_chain_frame()

    def playback_rewind(self) -> None:
        self._ensure_rollout()
        if self._rollout is None:
            return
        self._timer.stop()
        self.play_button.setText("Play")
        self._frame_index = 0
        self._render_chain_frame()

    def playback_jump_to_end(self) -> None:
        self._ensure_rollout()
        if self._rollout is None:
            return
        self._timer.stop()
        self.play_button.setText("Play")
        self._frame_index = self._rollout.positions.shape[0] - 1
        self._render_chain_frame()

    def set_playback_speed(self, speed: float) -> None:
        self._controls["speed"].set_value(speed)
        if self._timer.isActive():
            self._timer.start(self._playback_interval_ms())

    def playback_status(self) -> tuple[int, int, bool]:
        total = self._rollout.positions.shape[0] if self._rollout is not None else 0
        return self._frame_index + 1 if total else 0, total, self._timer.isActive()

    def _ensure_rollout(self) -> None:
        if self._rollout is None:
            self._simulate()

    def _advance_frame(self) -> None:
        if self._rollout is None:
            return
        self._frame_index = (self._frame_index + 1) % self._rollout.positions.shape[0]
        self._render_chain_frame()
        self._timer.start(self._playback_interval_ms())

    def _render_chain_frame(self) -> None:
        if self._rollout is None:
            return
        self.canvas.set_scene(
            [tuple(point) for point in self._rollout.positions[self._frame_index]]
        )

    def _playback_interval_ms(self) -> int:
        speed = max(0.05, self._value("speed"))
        return max(10, round(1000.0 * self._dt_s / speed))


def create_swingset_tab() -> QWidget:
    return SwingsetTab()


def create_chain_tab() -> QWidget:
    return ChainDynamicsTab()
