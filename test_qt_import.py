# Copyright (c) 2026 D-Sorganization. All rights reserved.
import traceback

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:
    print("IMPORT ERROR:")
    traceback.print_exc()
