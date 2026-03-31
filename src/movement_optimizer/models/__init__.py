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

# Re-export everything from submodules for backwards compatibility.
# All existing imports of the form ``from movement_optimizer.models import X``
# continue to work without modification.

from .bench_press_model import BenchPressModel as BenchPressModel
from .bench_press_model import make_bench_press_config as make_bench_press_config
from .body_model import BodyModel as BodyModel
from .body_model import ChainGeometry as ChainGeometry
from .body_model import clamp_joint_angles as clamp_joint_angles
from .body_model import joint_angles_within_limits as joint_angles_within_limits
from .exercise_configs import make_deadlift_config as make_deadlift_config
from .exercise_configs import make_full_squat_config as make_full_squat_config
from .exercise_configs import make_squat_config as make_squat_config
from .lagrangian_dynamics import LagrangianDynamics as LagrangianDynamics
from .lagrangian_dynamics import balance_pose as balance_pose

# Re-export strength helpers that the original models.py exposed at package level.
from ..strength import (
    HillTorqueModel as HillTorqueModel,
    JointTorqueSet as JointTorqueSet,
    compute_max_load as compute_max_load,
    make_bench_press_torque_set as make_bench_press_torque_set,
    make_default_torque_set as make_default_torque_set,
)

# Re-export exercise factories added in the exercises subpackage.
from ..exercises.gait import make_gait_config as make_gait_config
from ..exercises.sit_to_stand import make_sit_to_stand_config as make_sit_to_stand_config

__all__ = [
    "BodyModel",
    "BenchPressModel",
    "ChainGeometry",
    "HillTorqueModel",
    "JointTorqueSet",
    "LagrangianDynamics",
    "balance_pose",
    "clamp_joint_angles",
    "compute_max_load",
    "joint_angles_within_limits",
    "make_bench_press_config",
    "make_bench_press_torque_set",
    "make_deadlift_config",
    "make_default_torque_set",
    "make_full_squat_config",
    "make_gait_config",
    "make_sit_to_stand_config",
    "make_squat_config",
]
