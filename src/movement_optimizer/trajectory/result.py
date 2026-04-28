# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""Data structures for optimisation results."""

from __future__ import annotations

from dataclasses import dataclass, field

from numpy.typing import NDArray


@dataclass
class OptimizationResult:
    """Immutable container for optimiser output."""

    t: NDArray
    q: NDArray
    qd: NDArray
    qdd: NDArray
    torques: NDArray
    power: NDArray
    com: NDArray
    bar: NDArray
    success: bool
    cost: float
    com_horizontal_range_cm: float
    elapsed_s: float = 0.0
    n_evals: int = 0
    n_joint_limit_violations: int = 0


@dataclass
class ProgressReport:
    """Snapshot of optimiser state for the GUI."""

    iteration: int
    cost: float
    best_cost: float
    improvement_pct: float
    elapsed_s: float
    cost_history: list[float] = field(default_factory=list)
    is_stalled: bool = False
    stall_reason: str = ""


class CancelledError(Exception):
    """Raised when the user cancels optimisation."""
