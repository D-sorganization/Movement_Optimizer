import os
import re

src_dir = "src/movement_optimizer"
traj_py = os.path.join(src_dir, "trajectory.py")
traj_pkg = os.path.join(src_dir, "trajectory")

os.makedirs(traj_pkg, exist_ok=True)

with open(traj_py, encoding="utf-8") as f:
    text = f.read()

# 1. result.py -> OptimizationResult, ProgressReport, CancelledError
m_result = re.search(
    r"(class OptimizationResult:.*?)(?=# ==============================================================\n# Progress report)",
    text,
    re.DOTALL,
)
m_prog = re.search(
    r"(class ProgressReport:.*?)(?=# ==============================================================\n# Cancellation sentinel)",
    text,
    re.DOTALL,
)
m_cancel = re.search(
    r"(class CancelledError\(Exception\):.*?)(?=# ==============================================================\n# Solution cache)",
    text,
    re.DOTALL,
)

res_code = f"""\"\"\"Data structures for optimisation results.\"\"\"
from __future__ import annotations

from dataclasses import dataclass, field
from numpy.typing import NDArray

{m_result.group(1).strip()}

{m_prog.group(1).strip()}

{m_cancel.group(1).strip()}
"""
with open(os.path.join(traj_pkg, "result.py"), "w", encoding="utf-8") as f:
    f.write(res_code)

# 2. cache.py -> SolutionCache
m_cache = re.search(
    r"(class SolutionCache:.*?)(?=# ==============================================================\n# Tuning defaults)",
    text,
    re.DOTALL,
)

cache_code = f"""\"\"\"Thread-safe cache for optimisation solutions.\"\"\"
from __future__ import annotations

import hashlib
import json
import logging
import threading

from .result import OptimizationResult

logger = logging.getLogger(__name__)

{m_cache.group(1).strip()}
"""
with open(os.path.join(traj_pkg, "cache.py"), "w", encoding="utf-8") as f:
    f.write(cache_code)

# 3. tuning.py -> Tuning defaults
m_tuning = re.search(
    r"(DEFAULT_JERK_WEIGHT: float = 0\.05.*?)(?=# ==============================================================\n# Trajectory Optimiser)",
    text,
    re.DOTALL,
)
tuning_code = f"""\"\"\"Tuning parameters and magical numbers for the optimiser.\"\"\"

{m_tuning.group(1).strip()}
"""
with open(os.path.join(traj_pkg, "tuning.py"), "w", encoding="utf-8") as f:
    f.write(tuning_code)

# 4. optimizer.py -> TrajectoryOptimizer
m_opt = re.search(r"(class TrajectoryOptimizer:.*)", text, re.DOTALL)
opt_code = f"""\"\"\"Parallel multi-start trajectory optimiser engine.\"\"\"
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import CubicSpline
from scipy.optimize import minimize

from ..backend import PhysicsBackend
from ..models import BodyModel
from .result import CancelledError, OptimizationResult, ProgressReport
from .tuning import (
    BALANCE_BARRIER_WEIGHT,
    BALANCE_CENTER_WEIGHT,
    DEFAULT_ENDPOINT_WEIGHT,
    DEFAULT_JERK_WEIGHT,
    DEFAULT_N_STARTS,
    DEFAULT_TORQUE_RATE_WEIGHT,
    MAX_ITER_PER_START,
    PERTURBATION_SCALE,
    STALL_THRESHOLD,
    STALL_WINDOW,
)

logger = logging.getLogger(__name__)

{m_opt.group(1).strip()}
"""
with open(os.path.join(traj_pkg, "optimizer.py"), "w", encoding="utf-8") as f:
    f.write(opt_code)

# 5. __init__.py -> Expose all
init_code = """\"\"\"Trajectory module extracted from monolith.\"\"\"
from __future__ import annotations

from .cache import SolutionCache as SolutionCache
from .optimizer import TrajectoryOptimizer as TrajectoryOptimizer
from .result import CancelledError as CancelledError
from .result import OptimizationResult as OptimizationResult
from .result import ProgressReport as ProgressReport

__all__ = [
    "CancelledError",
    "OptimizationResult",
    "ProgressReport",
    "SolutionCache",
    "TrajectoryOptimizer",
]
"""
with open(os.path.join(traj_pkg, "__init__.py"), "w", encoding="utf-8") as f:
    f.write(init_code)

os.remove(traj_py)
print("Complete")
