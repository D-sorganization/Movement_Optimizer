import sys
import traceback
try:
    from PyQt6.QtWidgets import QApplication
except ImportError as e:
    print("IMPORT ERROR:")
    traceback.print_exc()
