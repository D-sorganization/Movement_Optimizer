## 2025-02-23 - Added tooltips and accessible names to playback buttons
**Learning:** Found that the PyQt6 playback controls (icon-only buttons) were lacking tooltips and accessible names which are important for screen readers.
**Action:** When adding icon-only widgets, always set their `setToolTip` and `setAccessibleName` attributes in PyQt6 for accessibility.

## 2025-02-25 - Contextual Tooltips for Disabled States
**Learning:** In desktop GUI apps (PyQt6), disabled buttons without explanation create user frustration. Unlike web apps which can use ARIA descriptions, `setToolTip` is the primary built-in mechanism to convey state information and prerequisites (like "Run optimization first to enable...").
**Action:** Always provide descriptive tooltips for interactive elements, explicitly stating *why* a button is disabled and *what* it does when enabled. Update tooltips dynamically when states change to simulate web-like accessible helper text.

## 2025-02-25 - Mapping HTML Forms/ARIA to PyQt6 Accessibility
**Learning:** In PyQt6, mapping typical web accessibility standards requires using Qt-specific methods. HTML's `<label for="inputId">` equivalent is `label.setBuddy(input_widget)`, which establishes focus routing and relationship mapping for screen readers. Similarly, providing an equivalent to `aria-label` uses `widget.setAccessibleName("Description")`.
**Action:** When implementing new custom interactive widgets (like labelled sliders or form elements) in PyQt, always set `setBuddy()` on the corresponding `QLabel` and use `setAccessibleName()` directly on the interactive control to ensure full screen reader support.
