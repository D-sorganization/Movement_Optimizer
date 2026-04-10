"""Validation helpers for the Movement-Optimizer shared launcher provider manifest.

This module exposes a contract-tested validation function used by:
 - The test suite (TDD regression coverage)
 - CI (provider compatibility gate)
 - UpstreamDrift's shared harness when onboarding this provider pack

Design by Contract:
  Preconditions:
    - manifest_path must exist and contain valid YAML
  Postconditions:
    - Returned manifest passes all required-field checks
    - All referenced paths exist relative to repo_root
  Invariants:
    - Validation is side-effect-free (read-only)
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PROVIDER_MANIFEST_PATH = REPO_ROOT / "model_pack.yaml"

_OPTIONAL_DEPENDENCIES: dict[str, str] = {
    "maturin": "Rust/PyO3 extension build tooling (rust_core acceleration)",
    "jax": "JAX GPU-accelerated dynamics backend",
}

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
_REQUIRED_LAUNCHER_FIELDS = ("category", "status")


def load_provider_manifest(
    manifest_path: Path = PROVIDER_MANIFEST_PATH,
) -> dict[str, Any]:
    """Load the provider manifest YAML from disk.

    Args:
        manifest_path: Path to the model_pack.yaml file.

    Returns:
        Parsed manifest dictionary.

    Raises:
        FileNotFoundError: If the manifest file does not exist.
        ValueError: If the file does not parse to a mapping.
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"provider manifest not found: {manifest_path}")
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("provider manifest must deserialize to a mapping")
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


def validate_provider_manifest(
    repo_root: Path = REPO_ROOT,
    manifest_path: Path = PROVIDER_MANIFEST_PATH,
) -> dict[str, Any]:
    """Validate the provider manifest against the local repository layout.

    Checks that:
    - All required top-level and per-model fields are present.
    - source_root and working_dir directories exist.
    - The primary artifact path (path relative to source_root) exists.
    - All python_paths entries exist.
    - At least one model entry is declared.
    - Each launcher block has the required keys.

    Args:
        repo_root: Repository root for resolving relative paths.
        manifest_path: Path to the model_pack.yaml to validate.

    Returns:
        The validated manifest dictionary.

    Raises:
        ValueError: If any contract violation is found.
        FileNotFoundError: If manifest_path does not exist.
    """
    manifest = load_provider_manifest(manifest_path)
    _require_fields(manifest, _REQUIRED_TOP_LEVEL_FIELDS, label="manifest")

    models = manifest["models"]
    if not isinstance(models, list) or not models:
        raise ValueError("manifest must contain at least one model entry")

    seen_ids: set[str] = set()
    for model in models:
        if not isinstance(model, dict):
            raise ValueError("model entries must be mappings")
        _require_fields(model, _REQUIRED_MODEL_FIELDS, label=f"model[{model.get('id', '?')}]")

        model_id = model["id"]
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("model id must be a non-empty string")
        if model_id in seen_ids:
            raise ValueError(f"duplicate model id: {model_id!r}")
        seen_ids.add(model_id)

        source_root = (repo_root / str(model["source_root"])).resolve(strict=False)
        if not source_root.exists():
            raise ValueError(f"{model_id}.source_root does not exist: {source_root}")

        artifact_path = (source_root / str(model["path"])).resolve(strict=False)
        if not artifact_path.exists():
            raise ValueError(f"{model_id}.path does not exist: {artifact_path}")

        working_dir = (repo_root / str(model["working_dir"])).resolve(strict=False)
        if not working_dir.is_dir():
            raise ValueError(f"{model_id}.working_dir does not exist: {working_dir}")

        python_paths = model["python_paths"]
        if not isinstance(python_paths, list) or not python_paths:
            raise ValueError(f"{model_id}.python_paths must be a non-empty list")
        for index, python_path in enumerate(python_paths):
            path = (repo_root / str(python_path)).resolve(strict=False)
            if not path.is_dir():
                raise ValueError(f"{model_id}.python_paths[{index}] does not exist: {path}")

        capabilities = model["capabilities"]
        if not isinstance(capabilities, list) or not capabilities:
            raise ValueError(f"{model_id}.capabilities must be a non-empty list")

        launcher = model.get("launcher", {})
        if not isinstance(launcher, dict):
            raise ValueError(f"{model_id}.launcher must be a mapping")
        _require_fields(launcher, _REQUIRED_LAUNCHER_FIELDS, label=f"{model_id}.launcher")
        if launcher["category"] != "tool":
            raise ValueError(f"{model_id}.launcher.category must be 'tool' for utility providers")

    return manifest


def check_optional_dependencies(
    extra_optional_deps: dict[str, str] | None = None,
) -> list[str]:
    """Check which optional dependencies are unavailable and surface diagnostics.

    Returns a list of human-readable diagnostic strings, one per missing
    optional dependency.  An empty list means all optional dependencies are
    installed.

    Args:
        extra_optional_deps: Additional {package_name: description} pairs to
            check beyond the built-in optional dependency table.

    Returns:
        List of diagnostic strings for unavailable optional dependencies.
    """
    all_optional = dict(_OPTIONAL_DEPENDENCIES)
    if extra_optional_deps:
        all_optional.update(extra_optional_deps)

    issues: list[str] = []
    for package_name, description in all_optional.items():
        try:
            spec = importlib.util.find_spec(package_name)
            if spec is None:
                issues.append(
                    f"Optional dependency '{package_name}' not available "
                    f"({description}). Some features may be degraded."
                )
        except (ModuleNotFoundError, ValueError):
            issues.append(
                f"Optional dependency '{package_name}' not available "
                f"({description}). Some features may be degraded."
            )
    return issues
