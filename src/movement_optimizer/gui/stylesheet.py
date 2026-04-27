# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""Application stylesheet."""

from ..rendering import Palette

QSS = f"""
QMainWindow {{
    background-color: {Palette.BG};
}}
QWidget {{
    background-color: {Palette.BG};
    color: {Palette.FG};
    font-family: 'Segoe UI', 'Ubuntu', sans-serif;
    font-size: 10pt;
}}
QGroupBox {{
    background-color: {Palette.BG_PANEL};
    border: 1px solid {Palette.BG_INPUT};
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 16px;
    font-weight: bold;
    font-size: 10pt;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {Palette.FG};
}}
QLabel {{
    background-color: transparent;
    color: {Palette.FG};
}}
QLabel[class="dim"] {{
    color: {Palette.FG_DIM};
    font-size: 8pt;
}}
QLabel[class="result"] {{
    color: {Palette.GREEN};
    font-family: 'Consolas', 'Ubuntu Mono', monospace;
    font-size: 9pt;
}}
QLabel[class="title"] {{
    font-size: 14pt;
    font-weight: bold;
}}
QLabel[class="stall-warn"] {{
    color: {Palette.RED};
    font-size: 8pt;
    font-weight: bold;
}}
QPushButton {{
    background-color: {Palette.BG_INPUT};
    color: {Palette.FG};
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 9pt;
}}
QPushButton:hover {{
    background-color: {Palette.ACCENT};
}}
QPushButton[class="primary"] {{
    background-color: {Palette.ACCENT};
    color: white;
    font-weight: bold;
    font-size: 10pt;
    padding: 8px 16px;
}}
QPushButton[class="primary"]:hover {{
    background-color: {Palette.ACCENT2};
}}
QPushButton[class="cancel"] {{
    background-color: {Palette.RED};
    color: white;
    font-weight: bold;
    font-size: 9pt;
    padding: 6px 14px;
}}
QPushButton[class="cancel"]:hover {{
    background-color: #ff6666;
}}
QSlider::groove:horizontal {{
    background: {Palette.BG_INPUT};
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {Palette.ACCENT};
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: {Palette.ACCENT2};
}}
QTabWidget::pane {{
    border: 1px solid {Palette.BG_INPUT};
    border-radius: 4px;
}}
QTabBar::tab {{
    background: {Palette.BG_INPUT};
    color: {Palette.FG};
    padding: 6px 18px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background: {Palette.ACCENT};
    color: white;
}}
QProgressBar {{
    background-color: {Palette.BG_INPUT};
    border: none;
    border-radius: 3px;
    height: 8px;
    text-align: center;
    font-size: 7pt;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {Palette.ACCENT};
    border-radius: 3px;
}}
QScrollArea {{
    border: none;
}}
"""
