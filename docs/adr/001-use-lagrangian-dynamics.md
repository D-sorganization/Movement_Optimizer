# ADR 001: Use Lagrangian Dynamics for Biomechanics

## Status
<<<<<<< HEAD
Accepted

## Context
The project needs a dynamics framework for biomechanical trajectory optimization. Candidates included Lagrangian mechanics, Newton-Euler, and finite element methods.

## Decision
We chose Lagrangian dynamics because:
=======

Accepted

## Context

The project needs a dynamics framework for biomechanical trajectory optimization. Candidates included Lagrangian mechanics, Newton-Euler, and finite element methods.

## Decision

We chose Lagrangian dynamics because:

>>>>>>> origin/main
- It naturally handles constrained motion (joint limits, contact).
- It provides analytical gradients needed for optimal control.
- It scales well to multi-body systems like the human body.

## Consequences
<<<<<<< HEAD
=======

>>>>>>> origin/main
- **Positive:** Elegant handling of constraints, efficient gradient computation.
- **Negative:** Requires careful formulation of the Lagrangian; less intuitive than Newton-Euler for some users.

## Date
<<<<<<< HEAD
=======

>>>>>>> origin/main
2026-01-15
