"""TDD tests for the Movement-Optimizer shared launcher provider manifest.

Tests are written before the implementation (Red) and drive the design of:
 - model_pack.yaml — the provider manifest consumed by UpstreamDrift
 - scripts/provider_manifest.py — validation helpers
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "model_pack.yaml"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_manifest() -> dict:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "manifest must deserialize to a mapping"
    return data


# ---------------------------------------------------------------------------
# 1. Manifest file existence and top-level contract
# ---------------------------------------------------------------------------


class TestManifestExists:
    def test_model_pack_yaml_exists_at_repo_root(self) -> None:
        assert MANIFEST_PATH.is_file(), f"model_pack.yaml not found at {MANIFEST_PATH}"


class TestManifestTopLevel:
    def test_has_required_top_level_fields(self) -> None:
        manifest = _load_manifest()
        required = {"manifest_version", "pack_id", "pack_name", "provider", "models"}
        missing = required - set(manifest.keys())
        assert not missing, f"manifest missing required fields: {missing}"

    def test_provider_is_movement_optimizer(self) -> None:
        manifest = _load_manifest()
        assert manifest["provider"] == "movement_optimizer"

    def test_pack_id_is_stable(self) -> None:
        manifest = _load_manifest()
        assert manifest["pack_id"] == "movement-optimizer"

    def test_manifest_version_is_semver(self) -> None:
        manifest = _load_manifest()
        version = manifest["manifest_version"]
        assert isinstance(version, str) and len(version.split(".")) == 3


# ---------------------------------------------------------------------------
# 2. Model entry contract
# ---------------------------------------------------------------------------


class TestManifestModels:
    def test_has_at_least_one_model(self) -> None:
        manifest = _load_manifest()
        assert len(manifest["models"]) >= 1

    def test_each_model_has_required_fields(self) -> None:
        manifest = _load_manifest()
        required = {"id", "name", "description", "type", "path"}
        for model in manifest["models"]:
            missing = required - set(model.keys())
            assert not missing, f"model[{model.get('id')}] missing: {missing}"

    def test_optimizer_entry_is_present(self) -> None:
        manifest = _load_manifest()
        ids = {m["id"] for m in manifest["models"]}
        assert "movement_optimizer" in ids

    def test_model_ids_are_unique(self) -> None:
        manifest = _load_manifest()
        ids = [m["id"] for m in manifest["models"]]
        assert len(ids) == len(set(ids)), "duplicate model ids"

    def test_main_entry_type_is_tool(self) -> None:
        manifest = _load_manifest()
        entry = next(m for m in manifest["models"] if m["id"] == "movement_optimizer")
        assert entry["type"] == "tool"

    def test_main_entry_path_points_at_valid_file(self) -> None:
        manifest = _load_manifest()
        entry = next(m for m in manifest["models"] if m["id"] == "movement_optimizer")
        artifact = REPO_ROOT / entry["path"]
        assert artifact.is_file(), f"entry path does not exist: {artifact}"

    def test_working_dir_exists(self) -> None:
        manifest = _load_manifest()
        entry = next(m for m in manifest["models"] if m["id"] == "movement_optimizer")
        working_dir = REPO_ROOT / entry["working_dir"]
        assert working_dir.is_dir(), f"working_dir does not exist: {working_dir}"

    def test_python_paths_are_non_empty_list(self) -> None:
        manifest = _load_manifest()
        entry = next(m for m in manifest["models"] if m["id"] == "movement_optimizer")
        python_paths = entry.get("python_paths", [])
        assert isinstance(python_paths, list)
        assert len(python_paths) >= 1

    def test_python_paths_exist(self) -> None:
        manifest = _load_manifest()
        entry = next(m for m in manifest["models"] if m["id"] == "movement_optimizer")
        for python_path in entry.get("python_paths", []):
            path = REPO_ROOT / python_path
            assert path.is_dir(), f"python_path does not exist: {path}"


# ---------------------------------------------------------------------------
# 3. Capabilities and metadata
# ---------------------------------------------------------------------------


class TestManifestCapabilities:
    def test_main_entry_declares_capabilities(self) -> None:
        manifest = _load_manifest()
        entry = next(m for m in manifest["models"] if m["id"] == "movement_optimizer")
        caps = entry.get("capabilities", [])
        assert isinstance(caps, list) and len(caps) >= 1

    def test_main_entry_declares_launcher_metadata(self) -> None:
        manifest = _load_manifest()
        entry = next(m for m in manifest["models"] if m["id"] == "movement_optimizer")
        launcher = entry.get("launcher", {})
        required = {"category", "status"}
        missing = required - set(launcher.keys())
        assert not missing, f"launcher metadata missing: {missing}"

    def test_launcher_category_is_tool(self) -> None:
        manifest = _load_manifest()
        entry = next(m for m in manifest["models"] if m["id"] == "movement_optimizer")
        assert entry["launcher"]["category"] == "tool"


# ---------------------------------------------------------------------------
# 4. Compatibility validation helper
# ---------------------------------------------------------------------------


class TestValidationHelper:
    def test_validate_function_returns_manifest_dict(self) -> None:
        from scripts.provider_manifest import validate_provider_manifest

        result = validate_provider_manifest()
        assert isinstance(result, dict)
        assert result["provider"] == "movement_optimizer"

    def test_validate_raises_for_missing_required_field(self, tmp_path: Path) -> None:
        from scripts.provider_manifest import validate_provider_manifest

        bad_manifest = tmp_path / "model_pack.yaml"
        bad_manifest.write_text(
            "manifest_version: '1.0.0'\npack_id: 'test'\npack_name: 'Test'\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="missing required"):
            validate_provider_manifest(manifest_path=bad_manifest)

    def test_validate_raises_for_empty_models(self, tmp_path: Path) -> None:
        from scripts.provider_manifest import validate_provider_manifest

        bad_manifest = tmp_path / "model_pack.yaml"
        bad_manifest.write_text(
            "manifest_version: '1.0.0'\npack_id: 'x'\npack_name: 'X'\nprovider: 'x'\nmodels: []\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="at least one"):
            validate_provider_manifest(manifest_path=bad_manifest)


# ---------------------------------------------------------------------------
# 5. Optional dependency diagnostics
# ---------------------------------------------------------------------------


class TestOptionalDependencyDiagnostics:
    def test_optional_dep_check_returns_list(self) -> None:
        from scripts.provider_manifest import check_optional_dependencies

        issues = check_optional_dependencies()
        assert isinstance(issues, list)

    def test_unavailable_optional_dep_surfaces_diagnostic(self) -> None:
        from scripts.provider_manifest import check_optional_dependencies

        issues = check_optional_dependencies(
            extra_optional_deps={"_nonexistent_package_xyz_": "rust acceleration"}
        )
        assert any("_nonexistent_package_xyz_" in issue for issue in issues)
