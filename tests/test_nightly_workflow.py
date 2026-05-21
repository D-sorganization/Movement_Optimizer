"""Regression tests for the nightly GitHub Actions workflow."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
NIGHTLY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "nightly.yml"


def _load_nightly_workflow() -> dict[str, object]:
    return yaml.safe_load(NIGHTLY_WORKFLOW.read_text(encoding="utf-8"))


def _nightly_install_step() -> dict[str, object]:
    workflow = _load_nightly_workflow()
    steps = workflow["jobs"]["nightly"]["steps"]
    return next(step for step in steps if step.get("name") == "Install System Dependencies")


def test_install_system_dependencies_retries_dpkg_lock_failures() -> None:
    run_script = _nightly_install_step()["run"]

    assert "for attempt in" in run_script
    assert "lock-frontend" in run_script
    assert "sleep 30" in run_script
