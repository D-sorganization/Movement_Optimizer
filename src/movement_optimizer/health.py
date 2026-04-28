"""Health endpoint for Movement-Optimizer.

Provides a lightweight, side-effect-free health check that reports
package version, critical dependency availability, and a basic
physics-solver sanity check.
"""

from __future__ import annotations

import importlib.metadata
import json
import sys
import time
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class HealthStatus:
    """Immutable health status snapshot."""

    status: str
    version: str
    python_version: str
    timestamp: float = field(default_factory=time.time)
    checks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary representation."""
        return asdict(self)

    def to_json(self, indent: int | None = None) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


def health_check() -> HealthStatus:
    """Run dependency and sanity checks.

    Postcondition:
        Returns HealthStatus with status == "ok" iff all checks pass.
    """
    version = "unknown"
    with suppress(importlib.metadata.PackageNotFoundError):
        version = importlib.metadata.version("movement-optimizer")

    checks: dict[str, Any] = {}

    # Check numpy (required for all trajectory math)
    try:
        import numpy as np  # noqa: F401

        checks["numpy"] = "ok"
    except ImportError as exc:
        checks["numpy"] = f"missing: {exc}"

    # Check core physics backend instantiates without error
    try:
        from .models import BodyModel, LagrangianDynamics

        body = BodyModel()
        _ = LagrangianDynamics(body, body.m_squat.copy(), body.I_squat.copy(), 0.0)
        checks["physics_backend"] = "ok"
    except Exception as exc:
        checks["physics_backend"] = f"error: {exc}"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return HealthStatus(
        status=status,
        version=version,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        checks=checks,
    )
