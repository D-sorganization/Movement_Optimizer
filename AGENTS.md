# AGENTS.md -- Movement-Optimizer

Fleet-standard quality directives for all AI coding agents working on this repository.

## Safety & Security

- NEVER commit secrets, API keys, or credentials.
- NEVER disable security checks (bandit, pre-commit hooks) without explicit approval.
- NEVER force-push to `main`.
- All file I/O must use `pathlib` or context managers -- no bare `open()` without `with`.
- Subprocess calls must use list form (`subprocess.run([...])`) -- never shell=True with user input.

## Python Coding Standards

### Logging (not print)
- `src/` code MUST use `logging` -- no `print()` statements.
- Obtain loggers via `logger = logging.getLogger(__name__)`.
- Use appropriate levels: `debug` for internals, `info` for user-facing milestones, `warning`/`error` for problems.

### Imports
- No wildcard imports (`from x import *`) in `src/`.
- Prefer explicit imports; group as: stdlib, third-party, local.
- Use `from __future__ import annotations` in every module for PEP 604 style hints.

### Exceptions
- Catch specific exceptions -- never bare `except:` or `except Exception:` without re-raising.
- Raise domain-specific errors with clear messages.
- Use `ValueError` for precondition violations (DBC).

### Type Hints
- All public function signatures MUST have type hints.
- Use `numpy.typing.NDArray` for array parameters.
- Private helpers should have hints where non-obvious.

## TDD -- Red-Green-Refactor

1. **Red**: Write a failing test that captures the requirement.
2. **Green**: Write the minimum code to make it pass.
3. **Refactor**: Clean up while keeping tests green.

Every PR that adds or changes functionality MUST include corresponding tests.
Test files live in `tests/` and follow the `test_<module>.py` naming convention.

## DRY -- Don't Repeat Yourself

- Factor shared logic into private helpers or utility modules.
- Constants live in `src/movement_optimizer/constants.py` -- never hard-code magic numbers.
- If you copy-paste more than 3 lines, extract a function.

## DBC -- Design by Contract

- Public methods document preconditions in their docstring.
- Preconditions are enforced at construction (`__init__`) and method entry with explicit checks.
- Raise `ValueError` or `TypeError` immediately on violation -- fail fast.

## LoD -- Law of Demeter

- Callers interact only through the public API of each class.
- Do not reach through an object to access its internals (e.g., `obj._private_field`).
- Minimize coupling between modules; prefer dependency injection.

## Architecture Overview

Movement-Optimizer is a biomechanics trajectory optimizer for barbell exercises.
It uses Lagrangian inverse dynamics in the sagittal plane to compute optimal joint-angle
trajectories that minimize torque while respecting balance constraints.

| Module | Responsibility |
|---|---|
| `backend.py` | Abstract physics backend interface |
| `models.py` | Anthropometric body model, 3-link planar dynamics |
| `trajectory/` | Multi-start parallel trajectory optimizer (SLSQP) |
| `exercises/` | Exercise configuration factories (clean, snatch, jerk, gait, sit-to-stand) |
| `constants.py` | Physical constants, segment fractions, BOS parameters |
| `gui/` | PyQt6 interactive GUI package with real-time visualization |
| `rendering.py` | Matplotlib-based figure rendering |
| `rust_core/` | Optional Rust extension (PyO3/maturin) for hot-path acceleration |

### Key Concepts
- **Inner BOS constraint**: The center of mass must stay within the middle 60% of the foot
  (inner_heel to inner_toe). This is stricter than full base-of-support and produces
  realistic, stable movement patterns.
- **Multi-start parallelism**: Multiple perturbed initial guesses run concurrently via
  `ThreadPoolExecutor`. scipy's Fortran SLSQP releases the GIL for true thread parallelism.
- **Torque smoothing**: Torque-rate weighting + total-variation regularization eliminates
  oscillatory torque profiles.

## Testing Standards

- Framework: `pytest`
- Run: `PYTHONPATH=src py -m pytest tests/ -v`
- Minimum 80% coverage on touched files.
- Tests must be deterministic -- seed RNGs, mock I/O.
- Use `conftest.py` fixtures for shared setup (body model instances, etc.).
- No network calls in unit tests -- mock external dependencies.

## Tool Chain

| Tool | Command | Stage |
|---|---|---|
| Lint | `ruff check --fix` | pre-commit |
| Format | `ruff format` | pre-commit |
| Type check | `mypy --ignore-missing-imports src/` | pre-push |
| Security | `bandit -ll -ii src/` | pre-push |
| Tests | `pytest tests/ -x -q` | pre-push |
