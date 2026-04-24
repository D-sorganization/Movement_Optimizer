## 2026-04-24 - Fix B101: assert_used vulnerability
**Vulnerability:** Use of `assert` for data validation in `src/movement_optimizer/constants.py`
**Learning:** Python `assert` statements are stripped out when the interpreter is run with optimization flags (e.g., `python -O`). This means security or data validation checks relying on `assert` will be bypassed, potentially leading to undefined behavior or security issues.
**Prevention:** Use explicit `if` conditions and raise domain-specific exceptions (like `ValueError`) instead of using `assert` for critical logic or data validation.
