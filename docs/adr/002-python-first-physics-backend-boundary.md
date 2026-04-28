# ADR 002: Keep Python As The Canonical Physics API

## Status

Accepted

## Context

Movement-Optimizer has a Python package that owns the public GUI, CLI, persistence,
exercise factories, and test contracts. It also has an optional `rust_core/` extension
for hot-path inverse dynamics and center-of-mass batch calculations.

The project needs room for native acceleration without making every development,
testing, or user workflow depend on a compiled extension. The runtime contract in
`SPEC.md` also describes Rust acceleration as optional rather than required.

## Decision

The Python package remains the canonical physics API and runtime boundary. Core
domain concepts such as body models, exercise configurations, optimizer inputs, and
result objects are defined and validated in Python. Native code may accelerate
well-bounded numerical kernels, but it must preserve the Python-facing contracts.

The Rust extension is therefore an implementation detail:

- Python modules define the public behavior and fallback path.
- Rust functions may be used for performance-sensitive batch math.
- Callers should not need to know whether a calculation used Python or Rust.
- Tests for public behavior should exercise the Python API rather than importing
  `rust_core/` directly unless the test is specifically about the extension.

## Consequences

- **Positive:** The GUI, CLI, and test suite remain usable without a Rust toolchain.
- **Positive:** Public contracts stay centralized in one package, which reduces drift
  between Python and native implementations.
- **Positive:** Performance work can focus on measured hot paths without changing user
  workflows.
- **Negative:** Accelerated kernels need parity tests against the Python behavior.
- **Negative:** Some duplication between Python and Rust numerical code is acceptable
  when it preserves an optional acceleration boundary.

## Date

2026-04-28
