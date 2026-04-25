## 2025-02-23 - Added tooltips and accessible names to playback buttons
**Learning:** Found that the PyQt6 playback controls (icon-only buttons) were lacking tooltips and accessible names which are important for screen readers.
**Action:** When adding icon-only widgets, always set their `setToolTip` and `setAccessibleName` attributes in PyQt6 for accessibility.

## 2025-02-25 - Contextual Tooltips for Disabled States
**Learning:** In desktop GUI apps (PyQt6), disabled buttons without explanation create user frustration. Unlike web apps which can use ARIA descriptions, `setToolTip` is the primary built-in mechanism to convey state information and prerequisites (like "Run optimization first to enable...").
**Action:** Always provide descriptive tooltips for interactive elements, explicitly stating *why* a button is disabled and *what* it does when enabled. Update tooltips dynamically when states change to simulate web-like accessible helper text.

## 2024-05-24 - Map UI focus states to screen-readers for PyQt6 Widgets
**Learning:** I discovered that when using custom widgets in PyQt6 (like `LabelledSlider` and grouped custom layouts), standard accessibility mechanisms may fail. Not explicitly associating label text with the interactive controls means that screen readers will encounter silent failures (an input without a label).
**Action:** Always use Qt's `QLabel.setBuddy(target_widget)` to map focus states and explicit `widget.setAccessibleName("...")` strings to properly surface form controls to assistive technologies.
