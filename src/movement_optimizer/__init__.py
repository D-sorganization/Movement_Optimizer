"""Movement Optimizer.

A biomechanics tool for optimising exercise movement trajectories
using Lagrangian inverse dynamics in the sagittal plane.
"""

from __future__ import annotations

import importlib.metadata

from .models import balance_pose as balance_pose

try:
    __version__ = importlib.metadata.version("movement-optimizer")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0.dev0"
