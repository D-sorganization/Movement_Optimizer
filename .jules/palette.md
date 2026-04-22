## 2025-02-23 - Added tooltips and accessible names to playback buttons
**Learning:** Found that the PyQt6 playback controls (icon-only buttons) were lacking tooltips and accessible names which are important for screen readers.
**Action:** When adding icon-only widgets, always set their `setToolTip` and `setAccessibleName` attributes in PyQt6 for accessibility.
