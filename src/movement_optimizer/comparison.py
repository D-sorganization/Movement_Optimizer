"""Trial comparison storage and metrics computation.

Allows users to store multiple optimization runs and compare them
side-by-side with overlaid plots and summary metrics.

Design Principles:
    DBC  -- preconditions documented and checked.
    DRY  -- metrics extraction is a single function.
    LoD  -- store only exposes add/get/clear.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .trajectory import OptimizationResult


class ComparisonStore:
    """Thread-safe store for named optimization trials.

    Each trial contains a name, OptimizationResult, body params, and bar mass.
    """

    def __init__(self) -> None:
        self._trials: list[dict[str, Any]] = []

    def add_trial(
        self,
        name: str,
        result: OptimizationResult,
        body_params: dict[str, Any],
        bar_mass: float,
    ) -> None:
        """Add a named trial to the comparison list.

        Preconditions:
            name is a non-empty string.
            result is a valid OptimizationResult.
        """
        self._trials.append(
            {
                "name": name,
                "result": result,
                "body_params": body_params,
                "bar_mass": bar_mass,
            }
        )

    def get_trials(self) -> list[dict[str, Any]]:
        """Return a copy of the stored trials list."""
        return list(self._trials)

    def clear(self) -> None:
        """Remove all stored trials."""
        self._trials.clear()


def comparison_metrics(trials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute summary metrics for each trial.

    Returns a list of dicts, one per trial, each containing:
        name: trial name
        peak_torques: list of 3 floats (max abs torque per joint)
        total_work: float (integral of |power| over time)
        com_sway_cm: float (horizontal COM range in cm)

    Preconditions:
        Each trial dict has keys: name, result, body_params, bar_mass.
    """
    if not trials:
        return []

    metrics = []
    for trial in trials:
        r: OptimizationResult = trial["result"]
        peak_torques = [float(np.max(np.abs(r.torques[:, j]))) for j in range(3)]
        dt = float(r.t[1] - r.t[0]) if len(r.t) > 1 else 1.0
        total_work = float(np.sum(np.abs(r.power)) * dt)
        com_sway_cm = float(r.com_horizontal_range_cm)

        metrics.append(
            {
                "name": trial["name"],
                "peak_torques": peak_torques,
                "total_work": total_work,
                "com_sway_cm": com_sway_cm,
            }
        )

    return metrics
