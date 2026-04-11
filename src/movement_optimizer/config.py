"""Runtime configuration and filesystem paths for Movement Optimizer.

Configuration is intentionally lightweight and environment-driven so local
development, CI, and packaged usage can all override the same locations
without editing code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_STATE_DIR_ENV = "MOVEMENT_OPTIMIZER_STATE_DIR"


@dataclass(frozen=True)
class AppPaths:
    """Resolved application paths derived from environment variables."""

    state_dir: Path

    @property
    def state_file(self) -> Path:
        """Path to the persisted GUI session state file."""
        return self.state_dir / "last_state.json"


def load_app_paths() -> AppPaths:
    """Return app paths using environment overrides when provided."""
    configured = os.getenv(_STATE_DIR_ENV)
    state_dir = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".movement_optimizer"
    )
    return AppPaths(state_dir=state_dir)
