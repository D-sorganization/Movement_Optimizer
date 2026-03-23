"""Shared test fixtures."""

from __future__ import annotations

import pytest

from movement_optimizer.models import (
    BodyModel,
    JointTorqueSet,
    make_bench_press_config,
    make_bench_press_torque_set,
    make_deadlift_config,
    make_default_torque_set,
    make_full_squat_config,
    make_squat_config,
)


@pytest.fixture()
def default_body() -> BodyModel:
    return BodyModel(75.0, 1.75)


@pytest.fixture()
def custom_body() -> BodyModel:
    return BodyModel(
        80.0,
        1.80,
        seg_multipliers={"lower_leg": 1.1, "upper_leg": 0.9, "torso": 1.05},
    )


@pytest.fixture()
def squat_dynamics(default_body: BodyModel):
    return make_squat_config(default_body, 60.0)


@pytest.fixture()
def deadlift_dynamics(default_body: BodyModel):
    return make_deadlift_config(default_body, 60.0)


@pytest.fixture()
def full_squat_config(default_body: BodyModel):
    return make_full_squat_config(default_body, 60.0)


@pytest.fixture()
def bench_press_config(default_body: BodyModel):
    return make_bench_press_config(default_body, 60.0)


@pytest.fixture()
def default_torque_set() -> JointTorqueSet:
    return make_default_torque_set()


@pytest.fixture()
def bench_torque_set() -> JointTorqueSet:
    return make_bench_press_torque_set()
