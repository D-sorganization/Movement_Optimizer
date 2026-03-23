# Contributing to Movement Optimizer

Thank you for your interest in contributing! This document provides guidelines for contributing to Movement Optimizer.

## Development Setup

```bash
git clone https://github.com/D-sorganization/Movement-Optimizer.git
cd Movement-Optimizer
pip install -e ".[dev]"
```

## Code Style

- **Formatter**: `ruff format` (do not use Black)
- **Linter**: `ruff check`
- **Type checker**: `mypy --ignore-missing-imports`
- **Line length**: 100 characters

Run before committing:

```bash
ruff check src/ tests/ --fix
ruff format src/ tests/
```

## Design Principles

- **DBC (Design by Contract)**: All public methods must check preconditions and raise `ValueError` or `TypeError` on violation. Do not use `assert` for input validation in production code.
- **DRY**: Factor shared logic into helpers. Constants live in `constants.py`.
- **LoD (Law of Demeter)**: Callers interact only through the public API.
- **Logging**: Use `logging.getLogger(__name__)` in `src/`. Never use `print()`.

## Adding a New Exercise

1. Define start/end joint angles in `constants.py` or a new module under `exercises/`.
2. Create a config factory function (see existing examples in `models.py`).
3. Add a test in `tests/` that optimizes the exercise and asserts convergence.
4. Wire the exercise into the GUI in `gui/main_window.py`.
5. Run the full test suite.

## Testing

```bash
python3 -m pytest tests/ -v --tb=short
```

- Use fixtures from `conftest.py` for shared body model instances.
- Seed all RNGs for determinism.
- Optimizer tests use loose tolerances since L-BFGS-B results vary across platforms.

## Pull Requests

1. Create a feature branch from `main`.
2. Make your changes with clear, atomic commits.
3. Ensure all tests pass and linting is clean.
4. Open a PR with a description of what changed and why.

## Reporting Issues

Open a GitHub issue with:
- A clear title and description
- Steps to reproduce (if applicable)
- Expected vs. actual behavior
- Python version and OS
