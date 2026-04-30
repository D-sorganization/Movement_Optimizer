# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""Tests for import_results module -- JSON round-trip and error handling."""

from __future__ import annotations

import json

import pytest

from movement_optimizer.export import EXPORT_FORMAT_VERSION, export_result_json
from movement_optimizer.import_results import import_result_from_json


class TestImportResultFromJson:
    """Tests for import_result_from_json."""

    def test_round_trip_basic(self, tmp_path):
        """Export then import should return the original data (plus format_version)."""
        original = {"exercise_type": "squat", "cost": 12.5, "metadata": {"success": True}}
        out_path = tmp_path / "result.json"
        export_result_json(original, str(out_path))

        loaded = import_result_from_json(out_path)

        assert loaded["exercise_type"] == "squat"
        assert loaded["cost"] == 12.5
        assert loaded["format_version"] == EXPORT_FORMAT_VERSION

    def test_round_trip_preserves_nested_data(self, tmp_path):
        """Nested dicts survive the round-trip unchanged."""
        original = {
            "exercise_type": "deadlift",
            "metadata": {"cost": 5.0, "success": False, "n_evals": 200},
            "body_params": {"mass": 80.0, "height": 1.8},
        }
        out_path = tmp_path / "result.json"
        export_result_json(original, str(out_path))

        loaded = import_result_from_json(out_path)

        assert loaded["metadata"]["cost"] == 5.0
        assert loaded["body_params"]["mass"] == 80.0

    def test_file_not_found_raises(self, tmp_path):
        """Passing a non-existent path raises FileNotFoundError."""
        missing = tmp_path / "does_not_exist.json"
        with pytest.raises(FileNotFoundError, match="Result file not found"):
            import_result_from_json(missing)

    def test_invalid_json_raises_value_error(self, tmp_path):
        """A file containing invalid JSON raises ValueError."""
        bad = tmp_path / "bad.json"
        bad.write_text("this is not json {{{", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            import_result_from_json(bad)

    def test_non_object_json_raises_value_error(self, tmp_path):
        """A JSON file whose top-level value is not an object raises ValueError."""
        bad = tmp_path / "list.json"
        bad.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(ValueError, match="expected JSON object"):
            import_result_from_json(bad)

    def test_legacy_file_without_version_loads_with_warning(self, tmp_path, caplog):
        """A file without format_version loads successfully but emits a warning."""
        legacy = tmp_path / "legacy.json"
        legacy.write_text(json.dumps({"exercise_type": "squat", "cost": 9.0}), encoding="utf-8")
        import logging

        with caplog.at_level(logging.WARNING, logger="movement_optimizer.import_results"):
            data = import_result_from_json(legacy)

        assert data["exercise_type"] == "squat"
        assert any("format_version" in record.message for record in caplog.records)

    def test_incompatible_version_raises_value_error(self, tmp_path):
        """A file with an unsupported format_version raises ValueError."""
        versioned = tmp_path / "future.json"
        versioned.write_text(json.dumps({"format_version": "99.0", "cost": 1.0}), encoding="utf-8")
        with pytest.raises(ValueError, match="Incompatible format_version"):
            import_result_from_json(versioned)

    def test_accepts_string_path(self, tmp_path):
        """import_result_from_json accepts a plain string path."""
        out_path = tmp_path / "result.json"
        export_result_json({"exercise_type": "clean"}, str(out_path))
        data = import_result_from_json(str(out_path))
        assert data["exercise_type"] == "clean"


class TestExportResultJson:
    """Tests for export_result_json (the export side of the round-trip)."""

    def test_format_version_injected(self, tmp_path):
        """export_result_json always writes a format_version field."""
        out_path = tmp_path / "result.json"
        export_result_json({"exercise_type": "snatch"}, str(out_path))
        raw = json.loads(out_path.read_text(encoding="utf-8"))
        assert raw["format_version"] == EXPORT_FORMAT_VERSION

    def test_caller_data_preserved_alongside_version(self, tmp_path):
        """format_version does not overwrite caller-supplied keys."""
        out_path = tmp_path / "result.json"
        export_result_json({"exercise_type": "jerk", "cost": 3.3}, str(out_path))
        raw = json.loads(out_path.read_text(encoding="utf-8"))
        assert raw["exercise_type"] == "jerk"
        assert raw["cost"] == 3.3

    def test_non_dict_raises_value_error(self, tmp_path):
        """Passing a non-dict as data raises ValueError."""
        with pytest.raises(ValueError, match="data must be a dict"):
            export_result_json([1, 2, 3], str(tmp_path / "bad.json"))  # type: ignore[arg-type]

    def test_creates_parent_dirs(self, tmp_path):
        """export_result_json creates missing parent directories."""
        out_path = tmp_path / "subdir" / "nested" / "result.json"
        export_result_json({"k": "v"}, str(out_path))
        assert out_path.exists()
