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

| Module         | Responsibility                                                             |
| -------------- | -------------------------------------------------------------------------- |
| `backend.py`   | Abstract physics backend interface                                         |
| `models.py`    | Anthropometric body model, 3-link planar dynamics                          |
| `trajectory/`  | Multi-start parallel trajectory optimizer (SLSQP)                          |
| `exercises/`   | Exercise configuration factories (clean, snatch, jerk, gait, sit-to-stand) |
| `constants.py` | Physical constants, segment fractions, BOS parameters                      |
| `gui/`         | PyQt6 interactive GUI package with real-time visualization                 |
| `rendering.py` | Matplotlib-based figure rendering                                          |
| `rust_core/`   | Optional Rust extension (PyO3/maturin) for hot-path acceleration           |

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

| Tool       | Command                              | Stage      |
| ---------- | ------------------------------------ | ---------- |
| Lint       | `ruff check --fix`                   | pre-commit |
| Format     | `ruff format`                        | pre-commit |
| Type check | `mypy --ignore-missing-imports src/` | pre-push   |
| Security   | `bandit -ll -ii src/`                | pre-push   |
| Tests      | `pytest tests/ -x -q`                | pre-push   |

---

<!-- BEGIN FLEET-MANAGED: reasoning-engagement -->

## 🧠 Reasoning & Engagement

> This section is managed centrally by Repository_Management and synced fleet-wide.
> Do NOT edit it directly in individual repositories — edit the source in Repository_Management/AGENTS.md.

These rules govern *how* you engage with a task before and during implementation. They exist because LLM agents tend to pick an interpretation silently, overcomplicate the solution, and edit code they were not asked to touch. Each rule directly counteracts one of those failure modes.

- **Surface ambiguity. Do not guess silently.** If the request has more than one plausible interpretation, list the options and ask before implementing. Picking one and running with it is the single most common cause of rework in this fleet.
- **Push back on overcomplication.** If a simpler approach would satisfy the request, say so before you build the complicated one. Do not implement bloated 1000-line constructions when 100 would do. The senior-engineer test: would they call this overcomplicated? If yes, simplify.
- **Stay surgical.** Every changed line must trace directly to the user's request. Do not "improve" adjacent code, comments, formatting, or imports. Do not refactor things that are not broken. Match existing style even if you would do it differently.
- **Spotted ≠ fix.** If you notice unrelated dead code, latent bugs, or stylistic problems while working, *mention them in the PR body or as a follow-up issue* — do not fix them in the same PR. (The `mcp__ccd_session__spawn_task` tool is the right channel when working interactively.)
- **Clean up only your own orphans.** If your changes leave imports, variables, or functions newly unused, remove them. Do not delete pre-existing dead code unless the task asked for it.
- **State a verifiable success criterion before coding.** For a bug fix, that's a failing test that reproduces it (RED → GREEN, see TDD section below). For a feature, the explicit check that says "done." "Make it work" is not a success criterion.

**The diff test:** every line in your final diff should answer "this is here because the user asked for X." If you cannot answer that for a given line, remove it.

<!-- END FLEET-MANAGED: reasoning-engagement -->

---

<!-- BEGIN FLEET-MANAGED: network-api-hygiene -->

## 🛑 NETWORK & API HYGIENE (CRITICAL)

> This section is managed centrally by Repository_Management and synced fleet-wide.
> Do NOT edit it directly in individual repositories — edit the source in Repository_Management/AGENTS.md.

### GitHub API Quotas

| API Type                  | Quota        | Consumed By                                                        |
| ------------------------- | ------------ | ------------------------------------------------------------------ |
| REST (`gh api repos/...`) | 5,000 req/hr | Safe for polling                                                   |
| GraphQL                   | 5,000 req/hr | `gh pr list --json`, `gh pr checks`, `gh pr create`, `gh pr merge` |

GraphQL and REST have **separate** quotas. Exhausting GraphQL blocks PR creation and merging fleet-wide for an entire hour.

### Mandatory Rules

- **NO MASS POLLING**: Agents MUST NEVER use `gh pr list`, `gh issue list`, or arbitrary REST/GraphQL loops in a bulk manner to "scan" or "sweep" the repository fleet. Single, scoped repository lookups are allowed when needed (e.g., checking if a specific PR exists).
- **LOCAL FIRST**: Rely on local `.md` files, previously generated `issues.json` artifacts, or user assistance to find task context — do not query GitHub to discover what to work on.
- **NO PARALLELIZED GITHUB CLI**: Never write or execute scripts that loop over multiple repositories performing `gh` operations (automated PR merge scripts, fleet-wide status sweeps, etc.).
- **NO TIGHT POLLING LOOPS**: Never implement `while true; do gh pr checks $PR; sleep 30; done` patterns. Each iteration of such a loop costs 1–3 GraphQL calls; at 30-second intervals that drains the 5,000/hr quota in under 3 hours.
  - ❌ `while true; do gh pr checks; sleep 30; done`
  - ✅ `gh run watch <run-id>` — streams CI events without polling
  - ✅ Check status once at natural work breakpoints (after completing other tasks)
- **BATCHING**: If remote information is absolutely necessary, use a single focused query — not a loop of queries.
- **REST OVER GRAPHQL FOR CI STATUS**: Use REST endpoints for CI polling; they don't consume the GraphQL quota.
  - ❌ `gh pr checks <N>` (GraphQL)
  - ✅ `gh api repos/OWNER/REPO/actions/runs` (REST)
  - ✅ `gh api repos/OWNER/REPO/actions/jobs/<id>/logs` (REST)
- **STOP MONITORS IMMEDIATELY**: When using background monitor tasks, call `TaskStop <id>` the moment the monitored condition is satisfied. Do not leave monitors running "just in case."
- **LONG POLLING INTERVALS**: Background monitors must use ≥270-second intervals (keeps the prompt cache warm). Default to 1200–1800 s for idle monitoring. Never chain short sleeps to work around the 60-second minimum.
- **SILENT FAILURES**: If an API rate limit is hit, HALT NETWORK ACTIVITY IMMEDIATELY. Do not write retry-loops that further exhaust the quota. Alert the user and pivot to local work.

### Checking Rate Limit Status

```bash
gh api rate_limit | python3 -c "
import json, sys, datetime
d = json.load(sys.stdin)['resources']
for k in ['core', 'graphql']:
    r = d[k]
    reset = datetime.datetime.fromtimestamp(r['reset']).strftime('%H:%M:%S')
    print(f'{k}: {r[\"remaining\"]}/{r[\"limit\"]} remaining — resets {reset}')
"
```

<!-- END FLEET-MANAGED: network-api-hygiene -->
