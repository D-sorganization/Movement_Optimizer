# ADR 001: Use Lagrangian Dynamics for Biomechanics

## Status

Accepted

## Context

Movement-Optimizer needs a physics backend to compute joint torques, center-of-mass trajectories, and power consumption for human movement exercises (squat, bench press, etc.). The backend must:

1. Be deterministic and reproducible across platforms.
2. Support real-time evaluation for GUI preview and offline optimization.
3. Remain maintainable by a small team without requiring external commercial licenses.
4. Allow future extension to 3D models with minimal API churn.

## Decision

We will use Lagrangian (analytical) dynamics as the canonical physics backend, implemented in Python with NumPy.

The Lagrangian formulation computes:

- Inverse dynamics (torques from joint angles, velocities, accelerations)
- Forward kinematics (COM position from joint angles)
- Power and work terms

All derived from closed-form equations for a planar 3-DOF kinematic chain (hip, knee, ankle).

## Consequences

### Positive

- **No external runtime dependencies**: Pure NumPy + SciPy; no need for MuJoCo, Drake, or Pinocchio binaries in the default install.
- **Deterministic**: Same inputs always produce identical outputs across macOS, Linux, and Windows.
- **Transparent**: Equations are readable and auditable by biomechanics reviewers.
- **Fast enough for optimization**: Vectorized NumPy batch evaluations keep optimization wall-time under 5s for 12-waypoint trajectories.
- **Easy to test**: Analytical derivatives allow symbolic verification of gradients.

### Negative

- **Limited to planar models**: Extending to full 3D (shoulder abduction, hip rotation) requires re-deriving the Lagrangian or switching to a general-purpose backend.
- **Manual derivation burden**: Every new body segment or joint type requires human derivation of equations of motion.
- **No collision detection**: Self-collision and environment contact must be handled manually or deferred to a future backend.

## Alternatives Considered

| Approach                    | Why Not Chosen                                                                                                    |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| MuJoCo                      | Excellent for contact-rich tasks, but adds a heavy binary dependency and licensing complexity for redistribution. |
| Drake                       | Powerful symbolic/autodiff, but steep learning curve and large build artifacts.                                   |
| Pinocchio                   | Fast C++ with Python bindings, but complicates CI and onboarding for contributors without robotics backgrounds.   |
| Numerical finite-difference | Slower and less accurate than analytical derivatives; scales poorly with waypoint count.                          |

## Date

2024-03-15
