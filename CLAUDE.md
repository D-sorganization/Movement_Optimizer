# CLAUDE.md -- Movement-Optimizer

Project-specific guidance for Claude Code sessions.

## Quick Commands

```bash
# Run tests
PYTHONPATH=src python3 -m pytest tests/ -v

# Run a single test file
PYTHONPATH=src python3 -m pytest tests/test_models.py -v

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Build Rust extension (optional)
cd rust_core && maturin develop --release
```

## Architecture

Movement-Optimizer computes optimal barbell exercise trajectories using Lagrangian
inverse dynamics in the sagittal plane. The body is modelled as a 3-link planar chain
(shank, thigh, trunk) with a barbell load at the top.

### Module Map

- `src/movement_optimizer/backend.py` -- Abstract `PhysicsBackend` interface. The default
  implementation lives in `models.py`; a Rust-accelerated backend can be swapped in.
- `src/movement_optimizer/models.py` -- `BodyModel` (anthropometrics) and `PlanarDynamics`
  (Lagrangian equations of motion). This is the core physics engine.
- `src/movement_optimizer/trajectory/` -- `TrajectoryOptimizer` with multi-start
  parallel SLSQP. Entry point: `optimize()`. Sub-modules: `optimizer.py`, `result.py`,
  `cache.py`, `tuning.py`.
- `src/movement_optimizer/constants.py` -- All physical constants, segment mass/length
  fractions, BOS parameters. Never hard-code numbers elsewhere.
- `src/movement_optimizer/exercises/` -- Exercise configuration factories (clean, snatch,
  jerk, gait, sit-to-stand). Shared helpers in `_common.py`.
- `src/movement_optimizer/gui/` -- PyQt6 GUI package. Sub-modules: `main_window.py`,
  `exercise_tab.py`, `comparison_dialog.py`, `widgets.py`, `session_state.py`.
- `src/movement_optimizer/rendering.py` -- Matplotlib rendering utilities.
- `rust_core/` -- Optional PyO3/maturin Rust extension for hot-path dynamics.

### Inner BOS Constraint (Important)

The optimizer enforces that the whole-body center of mass stays within the **inner 60%**
of the base of support (the foot). This is controlled by `BOS_INNER_FRACTION` in
`constants.py`. The inner boundary (`inner_heel`, `inner_toe`) is computed by
`BodyModel` and passed to the optimizer as a hard constraint.

This is intentionally stricter than requiring COM to stay anywhere within the full foot.
Real humans maintain balance with a margin; the inner-BOS constraint produces trajectories
that look natural and stable. If the optimizer reports infeasibility, the exercise ROM
may be too aggressive for the given body proportions -- reduce the range or increase
the BOS fraction.

## Adding a New Exercise

1. Define the exercise's start and end joint angles in `constants.py` (or as a new
   config dict in the module that manages exercises).
2. Add a test in `tests/test_trajectory.py` that optimizes the new exercise with a
   reference body model and asserts convergence.
3. Wire the exercise into the GUI dropdown in `gui.py`.
4. Run the full test suite to verify nothing regresses.

## Key Design Decisions

- **No Black**: Formatting is handled exclusively by `ruff format`. Do not add Black.
- **DBC everywhere**: Public methods check preconditions and raise `ValueError` on
  violation. Follow this pattern in all new code.
- **Logging, not print**: `src/` code uses `logging.getLogger(__name__)`. The pre-commit
  hook blocks `print()` in `src/`.
- **Thread parallelism**: scipy's SLSQP releases the GIL, so `ThreadPoolExecutor`
  achieves real parallelism for multi-start optimization. Do not switch to
  `ProcessPoolExecutor` without benchmarking -- the overhead is not worth it for
  typical problem sizes.
- **Constants module**: All magic numbers live in `constants.py`. If you need a new
  physical constant or tuning parameter, add it there with a docstring.

## Testing

- Tests live in `tests/`.
- Use fixtures from `conftest.py` for shared body model instances.
- Seed all RNGs for determinism (`np.random.default_rng(seed)`).
- The optimizer tests use loose tolerances since L-BFGS-B results vary slightly
  across platforms.

## Hook bypass policy

**Never use `git commit --no-verify` or `git push --no-verify` unless the hook itself is broken** (tooling not installed, hook script crashes). It is _not_ an acceptable workaround for a hook that flags real issues.

### When a hook fails on something you didn't touch

The hook is scoped to _your diff_. If `fleet-fast-guardrails` or any other guardrail reports a violation in a file you didn't change, that's a regression — file an issue against `Repository_Management`. Bypassing locally doesn't help: the same checks run in CI's `quality-gate` and will block the PR.

### When the hook is legitimately broken

Open an issue in `Repository_Management`. If you must bypass once to land an urgent fix, include the hook error in the commit body and link the tracking issue. **Do not normalize `--no-verify` as a workaround.**

### Enforcement

Branch protection requires the CI `quality-gate` check on every PR. That check runs the same lint, format, type, and security gates as the hooks. `--no-verify` only delays feedback — it cannot land code that would have failed the hook.

For the canonical hook contract, see [`Repository_Management/docs/FLEET_HOOK_STANDARDS.md`](https://github.com/D-sorganization/Repository_Management/blob/main/docs/FLEET_HOOK_STANDARDS.md).
