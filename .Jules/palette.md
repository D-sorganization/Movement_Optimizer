
## 2024-05-18 - Added ARIA labels and tooltips to icon-only playback buttons
**Learning:** PyQt6 `QPushButton` widgets using only Unicode icons (like `\u23ee` for rewind) are inaccessible to screen readers without an explicit `accessibleName`. Tooltips (`setToolTip`) also greatly enhance mouse/visual usability, particularly since users might not recognize all unicode symbol conventions intuitively.
**Action:** Always set `setAccessibleName()` and `setToolTip()` on icon-only PyQt6 buttons, and ensure dynamically updated buttons (like Play/Pause toggles) update their tooltips and accessible names alongside their text/icons.
