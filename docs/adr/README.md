# Architecture Decision Records

This directory records architecture decisions that affect Movement-Optimizer's
module boundaries, runtime contracts, or long-term maintenance costs.

## Index

| ADR                                                 | Status   | Decision                                                                         |
| --------------------------------------------------- | -------- | -------------------------------------------------------------------------------- |
| [001](001-use-lagrangian-dynamics.md)               | Accepted | Use Lagrangian dynamics for biomechanics                                         |
| [002](002-python-first-physics-backend-boundary.md) | Accepted | Keep Python as the canonical physics API and treat Rust as optional acceleration |

## When To Add An ADR

Add or update an ADR when a change:

- Changes the public runtime contract described in [SPEC.md](../../SPEC.md).
- Moves responsibilities between `models/`, `trajectory/`, `exercises/`, `gui/`, or
  `rust_core/`.
- Introduces, removes, or changes a hard dependency.
- Changes optimizer behavior, physics assumptions, persistence format, or GUI state
  ownership in a way future contributors need to understand.

Small implementation fixes, test-only changes, and routine refactors usually do not
need an ADR unless they establish a new pattern.

## Format

Use the existing ADRs as the template:

- Title: `ADR NNN: Short Decision`
- Status: `Proposed`, `Accepted`, `Deprecated`, or `Superseded`
- Context: the forces and constraints behind the decision
- Decision: the chosen approach
- Consequences: important tradeoffs, both positive and negative
- Date: the date the decision was accepted or last materially revised
