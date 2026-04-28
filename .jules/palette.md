## 2025-02-23 - Added tooltips and accessible names to playback buttons
**Learning:** Found that the PyQt6 playback controls (icon-only buttons) were lacking tooltips and accessible names which are important for screen readers.
**Action:** When adding icon-only widgets, always set their `setToolTip` and `setAccessibleName` attributes in PyQt6 for accessibility.

## 2025-02-25 - Contextual Tooltips for Disabled States
**Learning:** In desktop GUI apps (PyQt6), disabled buttons without explanation create user frustration. Unlike web apps which can use ARIA descriptions, `setToolTip` is the primary built-in mechanism to convey state information and prerequisites (like "Run optimization first to enable...").
**Action:** Always provide descriptive tooltips for interactive elements, explicitly stating *why* a button is disabled and *what* it does when enabled. Update tooltips dynamically when states change to simulate web-like accessible helper text.

## 2025-02-24 - Accessibility and Focus Routing in PyQt6
**Learning:** PyQt6 components often lack explicit linkages for screen readers out of the box, functioning differently from HTML's `for` and `aria-label` attributes. Missing these leaves inputs disconnected from labels for assistive technologies.
**Action:** Consistently extract implicit labels to explicitly associate them using `QLabel.setBuddy(input_widget)` (focus routing) and `input_widget.setAccessibleName("Label")` (screen readers).

## 2025-02-26 - Dynamic Tooltips for Long-Running Processes
**Learning:** Disabling primary action buttons (like 'Optimize') during a background process without updating their tooltips leaves users wondering if the app is frozen or why they can't interact.
**Action:** Always dynamically update tooltips on buttons when their `setEnabled` state changes. Use `setToolTip("Process currently in progress. Please wait...")` when disabled, and restore the original tooltip when re-enabled.

## 2025-02-26 - Contextual Tooltips for QTabWidget
**Learning:** Tabs in `QTabWidget` can benefit from descriptive tooltips, especially when the tab labels are short or act as primary navigation.
**Action:** Use `QTabWidget.setTabToolTip(index, "Description")` during UI construction to add helpful hover context to individual tabs.

## 2024-04-27 - Contextual Tooltips for Disabled States
**Learning:** In PyQt6 UIs, disabling buttons during long-running tasks without explaining *why* they are disabled (or what state the system is currently in) creates user confusion. Standard tooltips describing the action often feel contradictory when the action is disabled.
**Action:** Always dynamically update `setToolTip()` alongside `setEnabled()` state changes (e.g. on `cancel_btn` when cancellation is already in progress, or `clear_compare_btn` when there is nothing to clear).
