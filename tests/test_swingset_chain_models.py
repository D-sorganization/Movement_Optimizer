# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""Tests for swingset and segmented-chain analysis models."""

from __future__ import annotations

import numpy as np
import pytest

from movement_optimizer.models.chain_dynamics import (
    ChainConfig,
    ChainState,
    initial_catenary_angles,
    link_midpoints,
    simulate_chain,
    step_chain,
    total_energy,
)
from movement_optimizer.models.swingset import (
    CyclicPolicyParameters,
    CyclicPolicySearchSpace,
    HumanSegmentSpec,
    SwingControlAction,
    SwingPose,
    SwingSetConfig,
    SwingSetState,
    build_swingset_snapshot,
    heuristic_pumping_policy,
    optimize_cyclic_policy,
    simulate_swingset,
    step_swingset,
)


def test_chain_positions_include_anchor_and_tip() -> None:
    config = ChainConfig(segment_count=4, segment_length_m=0.25)
    state = ChainState.stationary(config)

    positions = state.node_positions(config)

    assert positions.shape == (5, 2)
    assert positions[-1, 1] == pytest.approx(1.0)
    assert state.metrics(config).tip_speed_m_s == pytest.approx(0.0)


def test_chain_config_validates_physical_inputs() -> None:
    with pytest.raises(ValueError, match="segment_count"):
        ChainConfig(segment_count=0)
    with pytest.raises(ValueError, match="segment_length_m"):
        ChainConfig(segment_length_m=0.0)
    with pytest.raises(ValueError, match="damping"):
        ChainConfig(damping=-0.1)
    with pytest.raises(ValueError, match="coupling"):
        ChainConfig(coupling=-0.1)


def test_chain_state_validation_rejects_bad_arrays() -> None:
    config = ChainConfig(segment_count=2)
    with pytest.raises(ValueError, match="angles_rad"):
        ChainState(np.zeros((2, 1)), np.zeros(2)).validated(config)
    with pytest.raises(ValueError, match="angular_velocities"):
        ChainState(np.zeros(2), np.zeros(3)).validated(config)
    with pytest.raises(ValueError, match="finite"):
        ChainState(np.asarray([0.0, np.nan]), np.zeros(2)).validated(config)


def test_chain_midpoints_validate_shape() -> None:
    with pytest.raises(ValueError, match="shape"):
        link_midpoints(np.zeros((1, 2)))


def test_chain_catenary_and_anchor_validate_inputs() -> None:
    config = ChainConfig(segment_count=2)
    state = ChainState.stationary(config)
    with pytest.raises(ValueError, match="at least 2"):
        initial_catenary_angles(1, 0.2)
    with pytest.raises(ValueError, match="non-negative"):
        initial_catenary_angles(2, -0.2)
    with pytest.raises(ValueError, match="two finite"):
        state.node_positions(config, anchor_xy_m=(0.0, float("nan")))


def test_chain_simulation_damps_energy() -> None:
    config = ChainConfig(segment_count=6, damping=0.25)
    initial = ChainState(
        initial_catenary_angles(config.segment_count, 0.25),
        np.full(config.segment_count, 0.15),
    )

    rollout = simulate_chain(config, initial, steps=24, dt_s=0.01)

    assert len(rollout.states) == 25
    assert rollout.positions.shape == (25, 7, 2)
    assert np.all(np.isfinite(rollout.energy_j))
    assert total_energy(config, rollout.states[-1]) == pytest.approx(rollout.energy_j[-1])
    link_lengths = np.linalg.norm(np.diff(rollout.positions, axis=1), axis=2)
    np.testing.assert_allclose(link_lengths, config.segment_length_m)


def test_chain_simulation_validates_rollout_inputs() -> None:
    config = ChainConfig(segment_count=3)
    initial = ChainState.stationary(config)
    with pytest.raises(ValueError, match="steps"):
        simulate_chain(config, initial, steps=0, dt_s=0.01)
    with pytest.raises(ValueError, match="dt_s"):
        step_chain(config, initial, dt_s=0.0)
    with pytest.raises(ValueError, match="incompatible"):
        simulate_chain(config, initial, steps=2, dt_s=0.01, torque_history_nm=np.zeros((2, 2)))


def test_swingset_snapshot_models_body_chain_and_mass() -> None:
    config = SwingSetConfig(chain_segments=8, seat_placement_thigh_fraction=0.40)
    snapshot = build_swingset_snapshot(
        config,
        SwingPose(swing_angle_rad=0.12, hip_angle_rad=0.2, elbow_angle_rad=0.3),
    )

    assert snapshot.chain_nodes.shape == (9, 2)
    assert {"seat", "hand", "elbow", "shoulder", "waist", "hip", "knee", "foot"} <= set(
        snapshot.points
    )
    assert snapshot.center_of_mass_m.shape == (2,)
    assert snapshot.hand_chain_error_m == pytest.approx(0.0)
    assert snapshot.seat_chain_error_m == pytest.approx(0.0)
    thigh_attachment = snapshot.points["hip"] + 0.40 * (
        snapshot.points["knee"] - snapshot.points["hip"]
    )
    np.testing.assert_allclose(thigh_attachment, snapshot.chain_nodes[-1])
    assert np.max(np.abs(np.diff(snapshot.chain_nodes[:, 0]))) > 0.0


def test_swingset_config_validates_inputs() -> None:
    with pytest.raises(ValueError, match="chain_segments"):
        SwingSetConfig(chain_segments=0)
    with pytest.raises(ValueError, match="chain_length_m"):
        SwingSetConfig(chain_length_m=-1.0)
    with pytest.raises(ValueError, match="damping"):
        SwingSetConfig(damping=-0.1)
    with pytest.raises(ValueError, match="pump_gain"):
        SwingSetConfig(pump_gain=-0.1)
    with pytest.raises(ValueError, match="seat_placement"):
        SwingSetConfig(seat_placement_thigh_fraction=0.0)
    with pytest.raises(ValueError, match="seat_placement"):
        SwingSetConfig(seat_placement_thigh_fraction=1.1)
    with pytest.raises(ValueError, match="length_m"):
        HumanSegmentSpec(0.0, 1.0)
    with pytest.raises(ValueError, match="mass_kg"):
        HumanSegmentSpec(1.0, 0.0)


def test_swingset_static_position_remains_static_without_control() -> None:
    config = SwingSetConfig()
    state = SwingSetState.rest()

    next_state = step_swingset(config, state, SwingControlAction(), dt_s=0.02)

    assert next_state.pose.swing_angle_rad == pytest.approx(0.0)
    assert next_state.swing_angular_velocity_rad_s == pytest.approx(0.0)


def test_swingset_single_segment_chain_snapshot_is_supported() -> None:
    snapshot = build_swingset_snapshot(SwingSetConfig(chain_segments=1), SwingPose())

    assert snapshot.chain_nodes.shape == (2, 2)
    assert snapshot.hand_chain_error_m == pytest.approx(0.0)


def test_swingset_control_limits_clip_rates_and_torque() -> None:
    action = SwingControlAction(
        torso_lean_rate_rad_s=99.0,
        hip_rate_rad_s=-99.0,
        knee_rate_rad_s=99.0,
        shoulder_rate_rad_s=-99.0,
        elbow_rate_rad_s=99.0,
        external_torque_nm=999.0,
    ).clipped()

    assert np.max(np.abs(action.vector())) == pytest.approx(2.4)
    assert action.external_torque_nm == pytest.approx(70.0)


def test_swingset_heuristic_policy_builds_amplitude() -> None:
    config = SwingSetConfig()

    rollout = simulate_swingset(
        config,
        SwingSetState(pose=SwingPose(swing_angle_rad=0.08)),
        steps=80,
        dt_s=0.02,
        policy=heuristic_pumping_policy,
    )

    assert rollout.controls.shape == (80, 5)
    assert rollout.metrics.max_abs_swing_angle_rad > 0.08
    assert rollout.metrics.max_height_gain_m > 0.0
    assert rollout.metrics.final_energy_proxy_j >= 0.0
    assert rollout.metrics.mean_hand_chain_error_m == pytest.approx(0.0)
    assert rollout.metrics.mean_seat_chain_error_m == pytest.approx(0.0)
    for snapshot in rollout.snapshots:
        np.testing.assert_allclose(snapshot.chain_nodes[0], 0.0)


def test_swingset_cyclic_policy_search_selects_height_objective() -> None:
    result = optimize_cyclic_policy(SwingSetConfig(), steps=40, dt_s=0.02)

    assert result.objective_height_m == pytest.approx(result.rollout.metrics.max_height_gain_m)
    assert result.objective_height_m > 0.0
    assert result.parameters.frequency_hz > 0.0


def test_swingset_policy_search_reports_progress_and_uses_cycles() -> None:
    progress: list[tuple[int, int, float]] = []
    search_space = CyclicPolicySearchSpace(
        frequency_hz_min=0.5,
        frequency_hz_max=1.0,
        frequency_samples=2,
        hip_rate_min_rad_s=0.8,
        hip_rate_max_rad_s=0.8,
        hip_rate_samples=1,
        torso_rate_min_rad_s=0.4,
        torso_rate_max_rad_s=0.4,
        torso_rate_samples=1,
        knee_ratio_min=0.35,
        knee_ratio_max=0.35,
        knee_ratio_samples=1,
        phase_samples=2,
    )

    result = optimize_cyclic_policy(
        SwingSetConfig(),
        cycles=2.0,
        dt_s=0.02,
        search_space=search_space,
        progress_callback=lambda done, total, score, _params: progress.append((done, total, score)),
    )

    assert result.evaluated_candidates == 4
    assert result.optimized_cycles == pytest.approx(2.0)
    assert progress[-1][0] == progress[-1][1] == 4
    assert progress[-1][2] == pytest.approx(result.objective_height_m)


def test_swingset_rollout_validates_inputs() -> None:
    config = SwingSetConfig()
    with pytest.raises(ValueError, match="steps"):
        simulate_swingset(config, SwingSetState.rest(), 0, 0.02, heuristic_pumping_policy)
    with pytest.raises(ValueError, match="dt_s"):
        step_swingset(config, SwingSetState.rest(), SwingControlAction(), dt_s=0.0)
    with pytest.raises(ValueError, match="steps"):
        optimize_cyclic_policy(config, steps=0)
    with pytest.raises(ValueError, match="frequency_hz"):
        CyclicPolicyParameters(0.0, 1.0, 1.0, 0.5, 0.0)
    with pytest.raises(ValueError, match="hip_rate"):
        CyclicPolicyParameters(1.0, -1.0, 1.0, 0.5, 0.0)
    with pytest.raises(ValueError, match="torso_rate"):
        CyclicPolicyParameters(1.0, 1.0, -1.0, 0.5, 0.0)
    with pytest.raises(ValueError, match="knee_rate"):
        CyclicPolicyParameters(1.0, 1.0, 1.0, -0.5, 0.0)
    with pytest.raises(ValueError, match="frequency_samples"):
        CyclicPolicySearchSpace(frequency_samples=0)
    with pytest.raises(ValueError, match="frequency_hz"):
        CyclicPolicySearchSpace(frequency_hz_min=1.0, frequency_hz_max=0.5)
    with pytest.raises(ValueError, match="cycles"):
        optimize_cyclic_policy(config, cycles=0.0)
