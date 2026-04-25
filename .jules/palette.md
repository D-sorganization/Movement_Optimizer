## 2025-02-23 - Added tooltips and accessible names to playback buttons
**Learning:** Found that the PyQt6 playback controls (icon-only buttons) were lacking tooltips and accessible names which are important for screen readers.
**Action:** When adding icon-only widgets, always set their `setToolTip` and `setAccessibleName` attributes in PyQt6 for accessibility.

## 2025-02-25 - Contextual Tooltips for Disabled States
**Learning:** In desktop GUI apps (PyQt6), disabled buttons without explanation create user frustration. Unlike web apps which can use ARIA descriptions, `setToolTip` is the primary built-in mechanism to convey state information and prerequisites (like "Run optimization first to enable...").
**Action:** Always provide descriptive tooltips for interactive elements, explicitly stating *why* a button is disabled and *what* it does when enabled. Update tooltips dynamically when states change to simulate web-like accessible helper text.

## 2025-02-24 - Accessibility and Focus Routing in PyQt6
**Learning:** PyQt6 components often lack explicit linkages for screen readers out of the box, functioning differently from HTML's `for` and `aria-label` attributes. Missing these leaves inputs disconnected from labels for assistive technologies.
**Action:** Consistently extract implicit labels to explicitly associate them using `QLabel.setBuddy(input_widget)` (focus routing) and `input_widget.setAccessibleName("Label")` (screen readers).
