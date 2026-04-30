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
    setup_translations()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
