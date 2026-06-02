# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""Body model and Lagrangian dynamics engine.

This package contains the anthropometric body model and the analytical
3-link planar dynamics that serve as the default physics backend.

Submodules:
    body_model: BodyModel, ChainGeometry, and joint-angle helpers.
    lagrangian_dynamics: LagrangianDynamics and balance_pose.
    bench_press_model: BenchPressModel and make_bench_press_config.
    exercise_configs: make_squat_config, make_full_squat_config, make_deadlift_config.

Design Principles:
    DBC -- every public method states and checks its preconditions.
    DRY -- mass/inertia setup is factored into private helpers.
    LoD -- callers interact only through the public API.
"""

from __future__ import annotations

# Re-export strength helpers that the original models.py exposed at package level.
from ..strength import (
    HillTorqueModel as HillTorqueModel,
)
from ..strength import (
    JointTorqueSet as JointTorqueSet,
)
from ..strength import (
    compute_max_load as compute_max_load,
)
from ..strength import (
    make_bench_press_torque_set as make_bench_press_torque_set,
)
from ..strength import (
    make_default_torque_set as make_default_torque_set,
)

# Re-export everything from submodules for backwards compatibility.
# All existing imports of the form ``from movement_optimizer.models import X``
# continue to work without modification.
from .bench_press_model import BenchPressModel as BenchPressModel
from .bench_press_model import make_bench_press_config as make_bench_press_config
from .bilateral_3d import Bilateral3DModel as Bilateral3DModel
from .bilateral_3d import Bilateral3DPose as Bilateral3DPose
from .body_model import BodyModel as BodyModel
from .body_model import ChainGeometry as ChainGeometry
from .body_model import clamp_joint_angles as clamp_joint_angles
from .body_model import joint_angles_within_limits as joint_angles_within_limits
from .chain_dynamics import ChainConfig as ChainConfig
from .chain_dynamics import ChainState as ChainState
from .chain_dynamics import simulate_chain as simulate_chain
from .exercise_configs import make_deadlift_config as make_deadlift_config
from .exercise_configs import make_full_squat_config as make_full_squat_config
from .exercise_configs import make_squat_config as make_squat_config
from .lagrangian_dynamics import LagrangianDynamics as LagrangianDynamics
from .lagrangian_dynamics import balance_pose as balance_pose
from .swingset import SwingSetConfig as SwingSetConfig
from .swingset import SwingSetState as SwingSetState
from .swingset import optimize_cyclic_policy as optimize_cyclic_policy
from .swingset import simulate_swingset as simulate_swingset

__all__ = [
    "BenchPressModel",
    "Bilateral3DModel",
    "Bilateral3DPose",
    "BodyModel",
    "ChainConfig",
    "ChainGeometry",
    "ChainState",
    "HillTorqueModel",
    "JointTorqueSet",
    "LagrangianDynamics",
    "SwingSetConfig",
    "SwingSetState",
    "balance_pose",
    "clamp_joint_angles",
    "compute_max_load",
    "joint_angles_within_limits",
    "make_bench_press_config",
    "make_bench_press_torque_set",
    "make_deadlift_config",
    "make_default_torque_set",
    "make_full_squat_config",
    "make_squat_config",
    "optimize_cyclic_policy",
    "simulate_chain",
    "simulate_swingset",
]
