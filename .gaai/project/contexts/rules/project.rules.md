# Movement-Optimizer GAAI Project Rules

## Quality Standards
- Linter: ruff (v0.14.10)
- Formatter: ruff format (canonical - no Black)
- Test framework: pytest
- Type checking: mypy (non-blocking)
- Security: bandit
- Min coverage: 80% on touched files

## Code Principles (MANDATORY)
- DRY: Don't Repeat Yourself
- DBC: Design by Contract (preconditions checked at construction and method entry)
- LOD: Law of Demeter (callers interact only through public API)
- TDD: Test-Driven Development (Red-Green-Refactor)

## Acceptance Criteria (Auto-included in all stories)
1. Code passes: ruff check, ruff format --check, pytest -x
2. No print() in src/ (use logging module)
3. No TODO/FIXME without issue number
4. Type hints on function signatures
5. Docstrings on public functions
6. Tests for new functionality

## Issue Filters
- Include labels: bug, feature, enhancement, critical, P1, P2, P3, gaai:deliver
- Exclude labels: wontfix, manual-only, epic, documentation
- Min body length: 20 chars

## Concurrency Settings
- Max parallel agents: 2
- Max story retries: 3
- Agent timeout: 60 minutes per story

## Architecture Notes
- Physics backend: src/movement_optimizer/backend.py (abstract)
- Body model + dynamics: src/movement_optimizer/models.py
- Optimizer: src/movement_optimizer/trajectory.py
- GUI: src/movement_optimizer/gui.py (PyQt6)
- Rust extension: rust_core/ (optional, PyO3/maturin)
- Tests: tests/ (pytest)
