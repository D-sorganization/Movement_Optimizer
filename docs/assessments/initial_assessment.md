# Movement-Optimizer: Initial A-O and Pragmatic Programmer Assessment

**Date:** 2026-03-22
**Assessor:** Claude Opus 4.6 (1M context)
**Repo:** D-sorganization/Movement-Optimizer
**Commit:** b2c82f2 (main)

---

## Repository Overview

Movement-Optimizer is a biomechanics trajectory optimizer for barbell exercises using Lagrangian inverse dynamics in the sagittal plane. The body is modeled as a 3-link planar chain (shank, thigh, trunk) with a barbell load. The optimizer uses multi-start parallel SLSQP with hard COM constraints, a Hill-type torque model, and a PyQt6 GUI with real-time animation.

**Codebase Size:**
- Source: ~4,735 lines across 16 Python files + 184 lines Rust
- Tests: ~2,017 lines across 10 test files
- Total: ~6,752 lines Python + 184 lines Rust

---

## A-O Category Grades

### A - Project Structure & Organization: B+

**Strengths:**
- Clean `src/` layout with `pyproject.toml` (PEP 621 compliant)
- Logical module separation: `backend.py`, `models.py`, `trajectory.py`, `constants.py`, `gui.py`, `rendering.py`
- Exercise configs factored into `exercises/` sub-package with clean `__init__.py` re-exports
- Constants centralized in `constants.py` (no magic numbers elsewhere)
- `rust_core/` cleanly separated with its own `Cargo.toml` and `pyproject.toml`

**Issues:**
- `gui.py` is 1,851 lines -- a single monolithic file containing widget classes, styling, layout, optimization orchestration, and event handling. Should be split into sub-modules (widgets, orchestration, styling)
- `models.py` is 973 lines and contains BodyModel, LagrangianDynamics, BenchPressModel, HillTorqueModel, JointTorqueSet, exercise config factories, balance utilities, and compute_max_load -- too many responsibilities
- No `README.md` file exists at the repository root
- No `py.typed` marker for PEP 561

### B - Documentation: C+

**Strengths:**
- Excellent `AGENTS.md` and `CLAUDE.md` with architecture overview, design principles, and testing standards
- Good module-level docstrings in every source file
- Public methods generally have docstrings with preconditions documented
- Constants have inline comments with academic citations (Winter 2009, Norkin & White 2016, Anderson 2007)

**Issues:**
- No `README.md` -- the most critical documentation file is missing entirely
- No API reference documentation
- No user guide or installation instructions (the `.bat` launcher exists but no Linux equivalent or general docs)
- Some private helper functions lack docstrings (e.g., `_compute_masses`, `_compute_com_distances` in BodyModel)
- `CLAUDE.md` uses `py` command (Windows py launcher) instead of `python3` in its examples
- No CONTRIBUTING.md or CODE_OF_CONDUCT.md

### C - Testing: B+

**Strengths:**
- Comprehensive test suite: 10 test files, ~2,017 lines covering models, trajectory, joint limits, exercises, persistence, export, comparison, spine loads, bench press
- Tests are well-organized with class-based grouping and descriptive names
- Good fixture usage in `conftest.py`
- Tests seed RNGs for determinism (`np.random.default_rng(42)`)
- Edge cases covered: NaN/inf joint angles, negative parameters, wrong shapes
- Batch vs loop consistency tests ensure vectorized code matches scalar
- Balance constraints tested at endpoints for all exercises

**Issues:**
- No test coverage enforcement in CI (the `--cov` flag is used but no `--cov-fail-under` minimum)
- No tests for `gui.py` (1,851 lines completely untested)
- No tests for `rendering.py` (196 lines untested)
- No property-based (Hypothesis) tests
- `test_bench_press.py` uses `default_body` fixture from `conftest.py` but also redefines it locally in `test_exercises.py` (duplication)
- No integration tests that exercise the full pipeline (optimize -> export -> load)

### D - Security: B

**Strengths:**
- Bandit security scanning in both pre-commit and CI
- No secrets, API keys, or credentials in the codebase
- File I/O uses `os.makedirs` with `exist_ok=True` for safe directory creation
- JSON serialization for persistence (no pickle/eval)
- Pre-commit hooks block debug statements

**Issues:**
- `persistence.py` uses `open(path, "w")` without explicit encoding parameter (should specify `encoding="utf-8"`)
- No input sanitization on file paths passed to `save_solution`/`load_solution` (path traversal possible if user-controlled)
- The `.bat` launcher runs `pip install` without `--require-hashes` (supply chain risk)
- `gui.py` uses `os.path.expanduser("~")` implicitly via `_DEFAULT_STATE_DIR` -- no sandboxing of state directory
- Dependency versions use minimum bounds (`>=`) without upper caps, allowing potentially breaking major versions

### E - Performance: A-

**Strengths:**
- Vectorized batch methods (`inverse_dynamics_batch`, `com_x_batch`) avoid Python loops over timesteps
- Multi-start parallelism via `ThreadPoolExecutor` -- scipy's L-BFGS-B/SLSQP releases the GIL
- Pre-computed coupling coefficients in `LagrangianDynamics.__init__` avoid redundant computation
- Optional Rust extension (`rust_core/`) with rayon parallelism for hot-path dynamics
- `SolutionCache` prevents redundant re-optimization
- Numpy `trapezoid` compat shim handles numpy 1.x/2.x gracefully

**Issues:**
- `_package_results` uses a Python loop over all eval points for COM and bar trajectories instead of batch computation
- `_bar_knee_clearance` recomputes full forward kinematics instead of reusing existing computation
- No benchmarking suite or performance regression tests

### F - Code Quality: B

**Strengths:**
- Consistent `from __future__ import annotations` across all modules
- Ruff linting with comprehensive rule set (E, W, F, I, N, UP, B, SIM, RUF)
- Pre-commit hooks enforce formatting, linting, no wildcards, no debug, no print in src
- Type hints on all public function signatures using `numpy.typing.NDArray`
- Consistent logging via `logging.getLogger(__name__)`

**Issues:**
- 21 `assert` statements used for precondition checking in production code (`models.py`, `trajectory.py`, `gui.py`) -- these are disabled with `python3 -O` and should be `if/raise ValueError`
- `gui.py` has 9 bare `except Exception:` catches that swallow errors (violates AGENTS.md directive)
- One `print()` statement in `gui.py:1517` (violates AGENTS.md logging requirement)
- `models.py` exports private function `_balance_pose` which is imported by exercise modules
- mypy check in CI uses `|| true` (always passes) -- effectively disabled
- Black is listed in dev dependencies despite CLAUDE.md saying "No Black"

### G - Error Handling: C+

**Strengths:**
- Custom `CancelledError` exception for clean optimization cancellation
- Persistence module handles `FileNotFoundError`, `json.JSONDecodeError`, and `OSError` gracefully
- `load_app_state` returns `None` instead of crashing on corrupt state files
- `_detect_stall` handles zero-cost edge case

**Issues:**
- 9 bare `except Exception:` blocks in `gui.py` that catch and log but don't distinguish between recoverable and unrecoverable errors
- `assert` used instead of `ValueError`/`TypeError` for precondition violations -- assertions can be optimized away
- No custom exception hierarchy (all domain errors are `AssertionError` or generic `ValueError`)
- `_run_single_start` returns `None` silently on cancellation -- callers must check
- No retry logic for transient optimization failures
- `compute_max_load` silently returns 0 if no load is feasible instead of a clear error

### H - Dependencies: B+

**Strengths:**
- Minimal runtime dependencies: numpy, scipy, matplotlib, PyQt6
- Dev dependencies properly separated in optional `[dev]` group
- Rust extension is optional (graceful fallback to pure Python)
- `requires-python = ">=3.10"` properly specified
- CI tests across Python 3.10, 3.11, 3.12

**Issues:**
- No upper bounds on dependency versions (e.g., `numpy>=1.24` could pull numpy 3.x)
- Black is in dev deps but CLAUDE.md says "No Black" -- contradictory
- No `requirements.txt` or lockfile for reproducible dev environments
- `mypy` additional deps in pre-commit include `types-requests` and `types-PyYAML` which aren't actual dependencies

### I - CI/CD: B

**Strengths:**
- Solid CI pipeline: lint, format check, type check, security scan, then tests
- Multi-Python matrix testing (3.10, 3.11, 3.12)
- Separate Rust quality gate with rustfmt + clippy + tests
- Concurrency control with `cancel-in-progress`
- Coverage artifact upload on 3.12
- Auto-labeler, stale cleanup, and Jules integration workflows

**Issues:**
- mypy step uses `|| true` -- type errors are silently ignored
- No coverage threshold enforcement (`--cov-fail-under` missing)
- `paths-ignore` excludes `.github/**` from CI triggers -- workflow file changes won't trigger CI
- No branch protection rules visible (could merge without CI)
- CI doesn't run the Rust build for PRs that touch Python files (separate job, not required)
- No release/deployment workflow

### J - Deployment: C

**Strengths:**
- `pyproject.toml` with proper `[project.scripts]` entry point
- Windows `.bat` launcher with thorough Python discovery logic
- Rust extension build integrated into the launcher

**Issues:**
- No Dockerfile
- No Linux/macOS launch script (only Windows `.bat`)
- No PyPI publishing workflow
- No versioning strategy (hardcoded `1.0.0` in both `__init__.py` and `pyproject.toml`)
- No `MANIFEST.in` or explicit package data configuration
- The `.bat` launcher installs packages globally -- no virtual environment

### K - Maintainability: B

**Strengths:**
- DRY adherence: constants centralized, mass/inertia setup factored into private helpers
- Exercise config factories follow consistent pattern (factories return tuple of dynamics + angles + bounds)
- Clean backend abstraction (`PhysicsBackend` ABC) allows swapping physics engines
- Thread-safe caching and progress reporting
- Dataclasses for result containers (`OptimizationResult`, `ProgressReport`)

**Issues:**
- `gui.py` (1,851 lines) is a maintainability burden -- widget classes, orchestration, and state management all in one file
- `models.py` (973 lines) has too many responsibilities -- should be split into body_model, dynamics, torque_model, exercise_configs
- Exercise modules import private `_balance_pose` from `models.py` -- tight coupling across module boundary
- `ComparisonStore` claims to be "thread-safe" in docstring but uses no locks (only `list` operations which are thread-unsafe for mutations)

### L - Accessibility & UX: B-

**Strengths:**
- Well-designed PyQt6 GUI with dark theme, labeled sliders, progress bar, and real-time animation
- Export capabilities: GIF, PNG, PDF, CSV, JSON solutions
- Solution save/load and trial comparison features
- Cancel button for long-running optimizations

**Issues:**
- No CLI interface -- GUI is the only way to interact
- No headless/batch mode for scripting or automation
- No keyboard shortcuts documented
- No accessibility features (screen reader support, high contrast mode)
- Slider ranges are hardcoded (e.g., body mass 40-150 kg) with no way to customize
- No undo/redo support

### M - Compliance & Standards: C+

**Strengths:**
- MIT license specified in `pyproject.toml`
- Good `AGENTS.md` with coding standards

**Issues:**
- No `LICENSE` file at repository root (only license field in pyproject.toml)
- No `README.md`
- No `CONTRIBUTING.md`
- No `CODE_OF_CONDUCT.md`
- No `CHANGELOG.md`
- No issue templates or PR templates

### N - Architecture: B+

**Strengths:**
- Clean separation: `PhysicsBackend` ABC decouples optimizer from dynamics implementation
- Rendering separated from GUI logic
- Persistence layer cleanly separated
- Exercise configuration factories allow easy addition of new exercises
- Constants module prevents magic numbers
- Rust extension follows the same interface as Python, swappable at runtime

**Issues:**
- `gui.py` mixes presentation, business logic, and state management (not MVC/MVP)
- Exercise modules import private `_balance_pose` from `models.py` -- should be a public API
- `trajectory.py` has a circular-ish dependency: imports from `models.py`, while `models.py`'s `compute_max_load` imports from `trajectory.py` (deferred import)
- No event bus or message passing pattern -- GUI communicates via direct method calls and Qt signals

### O - Technical Debt: B

**Strengths:**
- No TODO/FIXME/HACK comments in the codebase
- No deprecated API usage detected
- numpy compat shim (`trapezoid`/`trapz`) is clean
- Code is relatively fresh (10 commits, well-structured from the start)

**Issues:**
- 21 `assert` statements in production code that should be proper `ValueError`/`TypeError` raises
- `_balance_pose` is private but used as public API by exercise modules
- `except Exception:` patterns in `gui.py` are technical debt that masks bugs
- `mypy || true` in CI means type errors accumulate silently
- Black in dev deps contradicts project policy
- Version `1.0.0` but the project appears to be pre-1.0 maturity

---

## Overall A-O Grade: B

The codebase demonstrates strong engineering fundamentals: clean architecture, good test coverage, proper CI, comprehensive constants management, and solid physics implementation. The main weaknesses are the monolithic `gui.py` and `models.py` files, missing `README.md` and standard project files, `assert` instead of proper exception raising, and bare exception catches in the GUI layer.

---

## Pragmatic Programmer Assessment

### DRY (Don't Repeat Yourself): A-

The codebase follows DRY well. Constants are centralized in `constants.py`. Exercise config factories share a consistent pattern. Mass/inertia computation is factored into private helpers. Test fixtures avoid duplication via `conftest.py`.

**Minor violations:**
- `_make_result()` helper is duplicated in `test_persistence.py` and `test_comparison.py` -- should be in `conftest.py`
- `default_body` fixture is defined in both `conftest.py` and `test_exercises.py`
- COM balance checking logic is repeated across exercise config factories (each calls `_balance_pose` with similar patterns)

### Orthogonality: B+

Modules are largely orthogonal. The `PhysicsBackend` ABC ensures the optimizer doesn't depend on the specific dynamics implementation. Rendering is separated from the GUI. Persistence is isolated.

**Violations:**
- `gui.py` is a single 1,851-line file where widget construction, optimization orchestration, and state management are entangled
- Exercise modules reach into `models.py` private API (`_balance_pose`)
- `compute_max_load` in `models.py` imports from `trajectory.py`, creating a bidirectional dependency

### Reversibility: B+

The `PhysicsBackend` ABC makes the dynamics engine swappable. The Rust extension is optional with Python fallback. Exercise config factories can be extended without modifying existing code.

**Gaps:**
- The GUI is tightly coupled to PyQt6 -- no abstraction layer for alternative frontends
- Optimizer is tied to SLSQP -- no strategy pattern for different solver backends
- Hard-coded to 3 DOF (sagittal plane) -- extending to 3D would require significant refactoring

### Tracer Bullets: A-

The project follows a tracer-bullet approach well. The pipeline from BodyModel -> LagrangianDynamics -> TrajectoryOptimizer -> OptimizationResult -> GUI visualization is end-to-end functional. Each module can be tested independently. The Rust extension is a clean tracer bullet -- same interface, different implementation.

### Design by Contract: B

DBC is explicitly stated as a design principle in AGENTS.md. Preconditions are documented in docstrings and enforced at method entry.

**Issues:**
- Contracts use `assert` instead of `raise ValueError` -- assertions are disabled with `-O` flag
- No postcondition checking anywhere
- No class invariant enforcement (BodyModel's internal state could become inconsistent if attributes are modified after construction)
- `ComparisonStore.add_trial` documents "name is a non-empty string" precondition but doesn't enforce it

### Broken Windows: B+

The codebase is clean -- no TODO/FIXME comments, consistent formatting, good naming. Pre-commit hooks prevent degradation.

**Windows:**
- The `print()` statement in `gui.py:1517` violates the project's own logging rule
- `except Exception:` catches in `gui.py` are broken windows that signal "it's okay to swallow errors"
- `mypy || true` in CI normalizes type errors
- Black in dev deps despite policy against it

### Stone Soup: A-

The project effectively demonstrates value incrementally: starting with basic optimization, adding exercises, adding GUI features, adding persistence, adding Rust acceleration. Each PR builds on the previous.

### Good Enough Software: B+

The software ships functional, well-tested code. The optimizer produces physically reasonable results. The GUI is polished with dark theme and animation.

**Gaps:**
- No user-facing error messages when optimization fails (just a log warning)
- No documentation for end users
- No graceful degradation when PyQt6 is unavailable (could offer CLI mode)

### Domain Languages: A-

The code speaks the domain language fluently: joint angles, torques, COM, BOS, inverse dynamics, Hill model, NIOSH limits. Constants reference academic sources. Variable names match biomechanics conventions.

### Estimation: N/A

No estimation artifacts visible. The optimizer does have tuning parameters with well-chosen defaults, suggesting empirical calibration was done.

---

## Summary of Findings (by priority)

### Critical (fix immediately)
1. No `README.md` at repository root
2. 21 `assert` statements in production code (disabled with `-O`)
3. 9 bare `except Exception:` catches in `gui.py`

### High Priority
4. `gui.py` is 1,851 lines -- split into sub-modules
5. `models.py` is 973 lines -- split into focused modules
6. mypy CI step uses `|| true` -- effectively disabled
7. No coverage threshold enforcement in CI
8. `_balance_pose` is private but used as public API

### Medium Priority
9. No CLI/headless mode
10. No Linux launch script
11. Missing standard files: LICENSE, CONTRIBUTING.md, CHANGELOG.md
12. `ComparisonStore` not actually thread-safe despite docstring claim
13. Black in dev deps contradicts project policy
14. No property-based tests
15. No GUI tests
16. `print()` in `gui.py:1517`
17. Persistence uses `open()` without `encoding="utf-8"`

### Low Priority
18. No Dockerfile
19. No PyPI publishing workflow
20. Test helper duplication across test files
21. No `py.typed` marker
22. Hardcoded version `1.0.0` with no versioning strategy
23. No benchmarking suite
