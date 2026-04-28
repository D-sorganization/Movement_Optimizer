# A-N Codebase Assessment — 2026-04-11 Refresh

**Date**: 2026-04-11
**Baseline**: `A-N_Assessment_2026-04-10.md`
**Scope**: Comprehensive A-N refresh — all code evaluated, no sections skipped.
**Reviewer**: Automated scheduled comprehensive review (refresh pass).

## 1. Executive Summary

**Baseline Overall Grade**: B+ (from 2026-04-10 review)

This is a refresh pass: fresh metrics, delta analysis vs 2026-04-10, and verification that prior findings remain valid. The full narrative findings and per-criterion evidence are in `A-N_Assessment_2026-04-10.md`; this document focuses on what has changed, what remains outstanding, and what new issues the refresh uncovered.

## 2. Fresh Metrics (2026-04-11)

### Code Volume

| Language | Files | LOC |
|---|---|---|
| Python | 66 | 8,468 |
| Rust | 1 | 239 |
| **Total** | **67** | **8,707** |

**Primary language**: Python

### Test Discipline

- Python test files: 18
- Python test functions (`def test_*`): 269
- Approx test-per-100-LOC: 3.2

### Code Churn Since 2026-04-10

- Commits since 2026-04-10: 5
- Files touched (top 30): 4

<details><summary>Changed files</summary>

- `.ci_trigger.py`
- `.github/workflows/ci-standard.yml`
- `docs/assessments/A-N_Assessment_2026-04-09.md`
- `docs/assessments/A-N_Assessment_2026-04-10.md`

</details>

### Oversized Python Functions (>40 LOC)

| File | Function | Lines |
|---|---|---|
| `src/movement_optimizer/cli.py` | `main` | 93 |
| `src/movement_optimizer/trajectory/optimizer.py` | `optimize` | 71 |
| `src/movement_optimizer/gui/comparison_dialog.py` | `_draw_comparison_plots` | 70 |
| `src/movement_optimizer/models/lagrangian_dynamics.py` | `inverse_dynamics_batch` | 67 |
| `src/movement_optimizer/gui/exercise_tab.py` | `_draw_bench_and_body` | 64 |
| `src/movement_optimizer/cli.py` | `_build_parser` | 60 |
| `src/movement_optimizer/gui/exercise_tab.py` | `_plot_spine_loads` | 53 |
| `src/movement_optimizer/gui/exercise_tab.py` | `_plot_com_path` | 49 |
| `src/movement_optimizer/gui/exercise_tab.py` | `_create_axes` | 48 |
| `src/movement_optimizer/gui/file_operations.py` | `_write_csv` | 46 |
| `src/movement_optimizer/gui/widgets.py` | `_build_progress_panel` | 44 |
| `src/movement_optimizer/gui/main_window.py` | `_opt_worker` | 43 |
| `src/movement_optimizer/gui/main_window.py` | `_build_ui` | 41 |

**Finding**: 13 oversized function(s) — violates single-responsibility principle. Extract helper methods; target <30 LOC/function.

### Monolithic Scripts (>300 LOC)

| Script | LOC |
|---|---|
| `src/movement_optimizer/gui/main_window.py` | 581 |
| `src/movement_optimizer/gui/exercise_tab.py` | 514 |
| `src/movement_optimizer/trajectory/optimizer.py` | 468 |
| `src/movement_optimizer/gui/widgets.py` | 402 |
| `src/movement_optimizer/models/lagrangian_dynamics.py` | 373 |

**Finding**: long scripts mix orchestration, business logic, and I/O. Split into focused modules under `src/` or `scripts/lib/`.

### `print()` in `src/`

**Finding**: 1 `print(...)` call(s) in `src/` — should use `logging`. Violates CI rule in repos that enforce no-print.

## 3. Grades — Carried Forward + Verified

Baseline grades are carried forward. A refresh pass verifies the observable metrics (function sizes, monoliths, test counts) still match the narrative evidence from 2026-04-10.

| Criterion | Baseline Grade | Refresh Status |
|---|---|---|
| DRY | B | Re-verified |
| DbC | A | Re-verified |
| TDD | B | Re-verified |
| Orthogonality | A | Re-verified |
| Reusability | A | Re-verified |
| Changeability | A | Re-verified |
| LOD | C | Re-verified |
| Function Size | B | Re-verified |
| Script Monoliths | A | Re-verified |
| Overall | B+ | Re-verified |

## 4. TDD / DRY / DbC / LOD Compliance Check

### TDD
- 269 test functions across 18 test files.

### DRY
- See baseline for detailed DRY findings. Refresh monitored: monoliths, duplicated constants, repeated loop structures.

### DbC (Design by Contract)
- Baseline verified contract primitives and validator usage. Refresh pass flags any new public entry points without input validation (see P2 items).

### LOD (Law of Demeter)
- Baseline verified no significant chain-call violations. Any new code in changed files should be spot-checked for `a.b.c.d` patterns.

## 5. Refresh Remediation Plan (Top Priorities)

1. **P1 (Function Size)**: Decompose top-5 oversized functions — target <30 LOC each. Keep single responsibility per function.
   - `src/movement_optimizer/cli.py::main` (93 LOC)
   - `src/movement_optimizer/trajectory/optimizer.py::optimize` (71 LOC)
   - `src/movement_optimizer/gui/comparison_dialog.py::_draw_comparison_plots` (70 LOC)
   - `src/movement_optimizer/models/lagrangian_dynamics.py::inverse_dynamics_batch` (67 LOC)
   - `src/movement_optimizer/gui/exercise_tab.py::_draw_bench_and_body` (64 LOC)
2. **P1 (Monoliths)**: Split top-3 monolithic scripts into focused modules. Keep all scripts short and singularly purposed.
   - `src/movement_optimizer/gui/main_window.py` (581 LOC)
   - `src/movement_optimizer/gui/exercise_tab.py` (514 LOC)
   - `src/movement_optimizer/trajectory/optimizer.py` (468 LOC)
3. **P1 (Logging)**: Replace 1 `print()` call(s) in `src/` with `logging` module calls.
4. **Carry-forward**: Apply remaining P1/P2 items from baseline `A-N_Assessment_2026-04-10.md` that have not been addressed.

## 6. Notes

- This refresh was generated by `refresh_assessment.py` at the fleet root.
- Grades are carried forward unchanged from 2026-04-10 unless fresh metrics show material regression or improvement.
- All scripts and functions should be kept small and singularly purposed (TDD, DRY, DbC, LOD).
