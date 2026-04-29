# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""Validation helpers for the Movement Optimizer provider manifest."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MOVEMENT_PROVIDER_MANIFEST = REPO_ROOT / "model_pack.yaml"

_REQUIRED_TOP_LEVEL_FIELDS = (
    "manifest_version",
    "pack_id",
    "pack_name",
    "provider",
    "models",
)
_REQUIRED_MODEL_FIELDS = (
    "id",
    "name",
    "description",
    "type",
    "path",
    "source_root",
    "working_dir",
    "python_paths",
    "capabilities",
    "launcher",
)
_REQUIRED_LAUNCHER_FIELDS = ("category", "logo", "status")


def load_movement_provider_manifest(
    path: Path = MOVEMENT_PROVIDER_MANIFEST,
) -> dict[str, Any]:
    """Load the movement-optimizer provider manifest from disk."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("movement provider manifest must deserialize to a mapping")
    return data


def _require_fields(
    payload: dict[str, Any],
    required_fields: tuple[str, ...],
    *,
    label: str,
) -> None:
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(f"{label} missing required fields: {missing}")


def _resolve_repo_relative_path(repo_root: Path, relative_path: str, *, label: str) -> Path:
    path = (repo_root / relative_path).resolve(strict=False)
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    return path


def _validate_model_id(model_id: str, model_ids: set[str]) -> None:
    """Validate a model ID for format and uniqueness."""
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("model id must be a non-empty string")
    if model_id in model_ids:
        raise ValueError(f"duplicate model id: {model_id}")


def _validate_model_paths(model_id: str, model: dict[str, Any], repo_root: Path) -> None:
    """Validate all path references in a model entry."""
    source_root = _resolve_repo_relative_path(
        repo_root,
        str(model["source_root"]),
        label=f"{model_id}.source_root",
    )
    artifact_path = (source_root / str(model["path"])).resolve(strict=False)
    if not artifact_path.exists():
        raise ValueError(f"{model_id}.path does not exist: {artifact_path}")

    _resolve_repo_relative_path(
        repo_root,
        str(model["working_dir"]),
        label=f"{model_id}.working_dir",
    )


def _validate_model_python_paths(model_id: str, python_paths: Any, repo_root: Path) -> None:
    """Validate the python_paths list."""
    if not isinstance(python_paths, list) or not python_paths:
        raise ValueError(f"{model_id}.python_paths must be a non-empty list")
    for index, python_path in enumerate(python_paths):
        _resolve_repo_relative_path(
            repo_root,
            str(python_path),
            label=f"{model_id}.python_paths[{index}]",
        )


def _validate_model_launcher(model_id: str, launcher: Any, repo_root: Path) -> None:
    """Validate the launcher configuration."""
    if not isinstance(launcher, dict):
        raise ValueError(f"{model_id}.launcher must be a mapping")
    _require_fields(launcher, _REQUIRED_LAUNCHER_FIELDS, label=f"{model_id}.launcher")
    if launcher["category"] != "tool":
        raise ValueError(f"{model_id}.launcher.category must be 'tool'")

    _resolve_repo_relative_path(
        repo_root,
        str(launcher["logo"]),
        label=f"{model_id}.launcher.logo",
    )


def _validate_model_entry(model: dict[str, Any], model_ids: set[str], repo_root: Path) -> str:
    """Validate a single model entry and return its ID."""
    if not isinstance(model, dict):
        raise ValueError("model entries must be mappings")
    _require_fields(model, _REQUIRED_MODEL_FIELDS, label=f"model[{model.get('id', '?')}]")

    model_id = model["id"]
    _validate_model_id(model_id, model_ids)
    model_ids.add(model_id)

    _validate_model_paths(model_id, model, repo_root)

    python_paths = model["python_paths"]
    _validate_model_python_paths(model_id, python_paths, repo_root)

    capabilities = model["capabilities"]
    if not isinstance(capabilities, list) or not capabilities:
        raise ValueError(f"{model_id}.capabilities must be a non-empty list")

    launcher = model["launcher"]
    _validate_model_launcher(model_id, launcher, repo_root)

    return model_id


def validate_movement_provider_manifest(
    repo_root: Path = REPO_ROOT,
    path: Path = MOVEMENT_PROVIDER_MANIFEST,
) -> dict[str, Any]:
    """Validate the optimizer provider manifest against the local repo layout."""
    manifest = load_movement_provider_manifest(path)
    _require_fields(manifest, _REQUIRED_TOP_LEVEL_FIELDS, label="manifest")

    models = manifest["models"]
    if not isinstance(models, list) or not models:
        raise ValueError("manifest must contain at least one model entry")

    model_ids: set[str] = set()
    for model in models:
        _validate_model_entry(model, model_ids, repo_root)

    return manifest
