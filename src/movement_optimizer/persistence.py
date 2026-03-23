"""Persistence layer for saving/loading solutions and app state.

Handles JSON serialization of OptimizationResult objects, including
numpy array conversion to/from nested Python lists.

Design Principles:
    DBC  -- preconditions checked at function entry.
    DRY  -- array conversion logic is factored into helpers.
    LoD  -- callers pass only the data they want persisted.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np

from .trajectory import OptimizationResult

logger = logging.getLogger(__name__)

# Default state directory
_DEFAULT_STATE_DIR = os.path.join(Path.home(), ".movement_optimizer")

# Array field names in OptimizationResult
_ARRAY_FIELDS = ("t", "q", "qd", "qdd", "torques", "power", "com", "bar")

# Scalar metadata fields in OptimizationResult
_METADATA_FIELDS = ("success", "cost", "com_horizontal_range_cm", "elapsed_s", "n_evals")


def _result_to_dict(result: OptimizationResult) -> dict[str, Any]:
    """Convert an OptimizationResult to a JSON-serializable dict."""
    arrays = {k: getattr(result, k).tolist() for k in _ARRAY_FIELDS}
    metadata = {k: getattr(result, k) for k in _METADATA_FIELDS}
    return {"arrays": arrays, "metadata": metadata}


def _dict_to_result(d: dict[str, Any]) -> OptimizationResult:
    """Reconstruct an OptimizationResult from a dict."""
    arrays = {k: np.array(d["arrays"][k]) for k in _ARRAY_FIELDS}
    meta = d["metadata"]
    return OptimizationResult(
        **arrays,
        success=meta["success"],
        cost=meta["cost"],
        com_horizontal_range_cm=meta["com_horizontal_range_cm"],
        elapsed_s=meta.get("elapsed_s", 0.0),
        n_evals=meta.get("n_evals", 0),
    )


def save_solution(
    path: str,
    result: OptimizationResult,
    body_params: dict[str, Any],
    exercise_type: str,
    bar_mass: float,
) -> None:
    """Save an optimization solution to a JSON file.

    Preconditions:
        path is a writable file path.
        result is a valid OptimizationResult.
    """
    data = {
        "exercise_type": exercise_type,
        "bar_mass": bar_mass,
        "body_params": body_params,
        **_result_to_dict(result),
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Saved solution to %s", path)


def load_solution(path: str) -> dict[str, Any]:
    """Load an optimization solution from a JSON file.

    Returns a dict with keys: exercise_type, bar_mass, body_params,
    arrays (dict of list data), metadata (dict of scalars).

    Raises:
        FileNotFoundError: if path does not exist.
        json.JSONDecodeError: if file is not valid JSON.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Solution file not found: {path}")
    with open(path) as f:
        data = json.load(f)
    logger.info("Loaded solution from %s", path)
    return data


def save_app_state(
    results_dict: dict[str, OptimizationResult],
    slider_values: dict[str, float],
    *,
    state_dir: str | None = None,
) -> None:
    """Save the current app state to the state directory.

    Preconditions:
        results_dict maps exercise_type -> OptimizationResult.
        slider_values maps slider_name -> float value.
    """
    sdir = state_dir or _DEFAULT_STATE_DIR
    os.makedirs(sdir, exist_ok=True)
    path = os.path.join(sdir, "last_state.json")

    serialized_results = {}
    for etype, result in results_dict.items():
        if result is not None:
            serialized_results[etype] = _result_to_dict(result)

    data = {
        "slider_values": slider_values,
        "results": serialized_results,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Saved app state to %s", path)


def load_app_state(*, state_dir: str | None = None) -> dict[str, Any] | None:
    """Load the last app state from the state directory.

    Returns None if no state file exists or if it is corrupt.
    """
    sdir = state_dir or _DEFAULT_STATE_DIR
    path = os.path.join(sdir, "last_state.json")

    if not os.path.exists(path):
        return None

    try:
        with open(path) as f:
            data = json.load(f)
        logger.info("Loaded app state from %s", path)
        return data
    except (json.JSONDecodeError, KeyError, OSError) as exc:
        logger.warning("Failed to load app state: %s", exc)
        return None
