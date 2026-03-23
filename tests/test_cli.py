"""Tests for the CLI module."""

from __future__ import annotations

import pytest
from conftest import make_test_result

from movement_optimizer.cli import _build_parser, _result_to_summary


class TestCLIParser:
    def test_required_exercise(self):
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_valid_exercise(self):
        parser = _build_parser()
        args = parser.parse_args(["--exercise", "squat"])
        assert args.exercise == "squat"

    def test_defaults(self):
        parser = _build_parser()
        args = parser.parse_args(["--exercise", "deadlift"])
        assert args.body_mass == 75.0
        assert args.height == 1.75
        assert args.bar_mass == 60.0
        assert args.duration == 2.0
        assert args.smoothness == 1.0
        assert args.output is None

    def test_custom_args(self):
        parser = _build_parser()
        args = parser.parse_args(
            [
                "--exercise",
                "bench_press",
                "--body-mass",
                "90",
                "--height",
                "1.85",
                "--bar-mass",
                "100",
                "--duration",
                "3.0",
                "--output",
                "out.json",
            ]
        )
        assert args.exercise == "bench_press"
        assert args.body_mass == 90.0
        assert args.bar_mass == 100.0
        assert args.output == "out.json"


class TestResultSummary:
    def test_summary_keys(self):
        result = make_test_result()
        summary = _result_to_summary(result, "squat")
        assert summary["exercise"] == "squat"
        assert "success" in summary
        assert "cost" in summary
        assert "peak_torques_Nm" in summary
        assert "ankle" in summary["peak_torques_Nm"]
