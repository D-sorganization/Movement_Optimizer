# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""Entry point: ``python -m movement_optimizer``."""

from __future__ import annotations

import logging
import sys

from PyQt6.QtWidgets import QApplication

from .gui import MainWindow
from .i18n import setup_translations


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    app = QApplication(sys.argv)
    # Block mouse wheel on value-input widgets (audit scroll-wheel policy)
            from PyQt6.QtCore import QEvent, QObject
            from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QSlider, QSpinBox
    
            class _WheelBlockFilter(QObject):
                def eventFilter(self, obj, event):
                    if event is not None and event.type() == QEvent.Type.Wheel:
                        if isinstance(obj, (QComboBox, QDoubleSpinBox, QSpinBox, QSlider)):
                            event.ignore()
                            return True
                    return False
    
            app.installEventFilter(_WheelBlockFilter(app))
    setup_translations()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
