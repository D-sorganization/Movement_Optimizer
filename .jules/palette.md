## 2025-02-23 - Added tooltips and accessible names to playback buttons
**Learning:** Found that the PyQt6 playback controls (icon-only buttons) were lacking tooltips and accessible names which are important for screen readers.
**Action:** When adding icon-only widgets, always set their `setToolTip` and `setAccessibleName` attributes in PyQt6 for accessibility.

## 2025-02-25 - Contextual Tooltips for Disabled States
**Learning:** In desktop GUI apps (PyQt6), disabled buttons without explanation create user frustration. Unlike web apps which can use ARIA descriptions, `setToolTip` is the primary built-in mechanism to convey state information and prerequisites (like "Run optimization first to enable...").
**Action:** Always provide descriptive tooltips for interactive elements, explicitly stating *why* a button is disabled and *what* it does when enabled. Update tooltips dynamically when states change to simulate web-like accessible helper text.## 2026-04-24 - Accessible Slider Components
**Learning:** PyQt6 slider components (QSlider) lack an implicit accessible name link to adjacent labels, making them opaque to screen readers. Relying solely on a visual QLabel is insufficient for accessibility.
**Action:** Always apply `setAccessibleName()` to the QSlider component directly, matching the text of its associated label to ensure screen reader compatibility.

## 2026-04-24 - Dynamic Tooltips for Disabled States
**Learning:** Users often get frustrated when UI elements are disabled without explanation. For long-running operations (like trajectory optimization), disabling buttons prevents duplicate actions but leaves the interface feeling unresponsive if context isn't provided.
**Action:** When toggling `setEnabled(False)` on action buttons, simultaneously update `setToolTip()` to explain the current system state (e.g., 'Optimization is currently running'). Restore the original tooltip when re-enabling.
