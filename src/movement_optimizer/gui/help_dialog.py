# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""ParameterHelpDialog: scrollable parameter-guide dialog for the Help menu."""

from __future__ import annotations

import logging
from typing import ClassVar

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class ParameterHelpDialog(QDialog):
    """Shows a scrollable list of parameter descriptions with units and ranges.

    Precondition: parent must be a QWidget or None.
    """

    PARAMETERS: ClassVar[dict[str, tuple[str, str, str]]] = {
        "Body Mass": (
            "Total body mass of the lifter",
            "kg",
            "50-150",
        ),
        "Height": (
            "Standing height of the lifter",
            "m",
            "1.40-2.10",
        ),
        "Lower Leg": (
            "Multiplier on the base lower-leg segment length (shank). "
            "Values above 1.0 lengthen the segment; below 1.0 shorten it.",
            "x",
            "0.70-1.30",
        ),
        "Upper Leg": (
            "Multiplier on the base upper-leg segment length (thigh). "
            "Values above 1.0 lengthen the segment; below 1.0 shorten it.",
            "x",
            "0.70-1.30",
        ),
        "Torso": (
            "Multiplier on the base torso segment length. "
            "Values above 1.0 lengthen the segment; below 1.0 shorten it.",
            "x",
            "0.70-1.30",
        ),
        "Total Bar + Plates": (
            "Combined mass of the barbell and any loaded plates. An Olympic bar alone is 20 kg.",
            "kg",
            "0-300",
        ),
        "Bar Back Offset": (
            "Horizontal distance by which the bar is displaced behind the "
            "shoulder contact point. Positive values shift the bar rearward.",
            "m",
            "0.00-0.40",
        ),
        "Bar Drop Offset": (
            "Vertical distance by which the bar sits below the default "
            "shoulder height. Positive values lower the bar.",
            "m",
            "0.00-0.40",
        ),
        "Duration": (
            "Total time allowed for the movement from start to end position. "
            "Shorter durations produce faster, more dynamic trajectories.",
            "s",
            "0.5-5.0",
        ),
        "Smoothness": (
            "Penalty weight on joint-torque rate of change. Higher values "
            "encourage smoother, slower torque transitions at the cost of "
            "slightly higher peak torques.",
            "x",
            "0.1-5.0",
        ),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Parameter Guide")
        self.setMinimumWidth(560)
        self.setMinimumHeight(480)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        header = QLabel(
            "Each parameter below controls a physical property of the model. "
            "Adjust sliders on the left-hand sidebar to change their values."
        )
        header.setWordWrap(True)
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setSpacing(6)
        grid.setColumnStretch(1, 1)

        # Column headers
        for col, heading in enumerate(("Parameter", "Description", "Unit", "Range")):
            lbl = QLabel(f"<b>{heading}</b>")
            grid.addWidget(lbl, 0, col)

        for row, (name, (desc, unit, rng)) in enumerate(self.PARAMETERS.items(), start=1):
            name_lbl = QLabel(name)
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)

            desc_lbl = QLabel(desc)
            desc_lbl.setWordWrap(True)
            desc_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)

            unit_lbl = QLabel(unit)
            unit_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

            rng_lbl = QLabel(rng)
            rng_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

            grid.addWidget(name_lbl, row, 0)
            grid.addWidget(desc_lbl, row, 1)
            grid.addWidget(unit_lbl, row, 2)
            grid.addWidget(rng_lbl, row, 3)

        content.setLayout(grid)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        outer.addWidget(buttons)
