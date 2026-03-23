"""Body model and Lagrangian dynamics engine.

This module contains the anthropometric body model and the analytical
3-link planar dynamics that serve as the default physics backend.

Design Principles:
    DBC -- every public method states and checks its preconditions.
    DRY -- mass/inertia setup is factored into private helpers.
    LoD -- callers interact only through the public API.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from .backend import PhysicsBackend
from .constants import (
    BOS_INNER_FRACTION,
    COM_FRAC,
    LENGTH_FRAC,
    MASS_FRAC,
    PLATE_RADIUS_STD_M,
)


class BodyModel:
    """Anthropometric model storing segment lengths and masses.

    Preconditions:
        body_mass > 0
        height > 0
        seg_multipliers values in [0.5, 2.0]

    The base-of-support (BOS) is split into an *inner zone* (middle 60%
    of the foot) and an *outer zone*.  The optimizer uses ``inner_heel``
    and ``inner_toe`` as the hard constraint boundary for COM placement.
    """

    def __init__(
        self,
        body_mass: float = 75.0,
        height: float = 1.75,
        seg_multipliers: dict[str, float] | None = None,
    ) -> None:
        assert body_mass > 0, "body_mass must be positive"
        assert height > 0, "height must be positive"

        self.body_mass = body_mass
        self.height = height
        self.g = 9.81

        mults = self._validated_multipliers(seg_multipliers)
        self._compute_lengths(height, mults)
        self._compute_base_of_support()
        self._compute_masses(body_mass)
        self._compute_com_distances()
        self._compute_inertias()

    # -- private helpers ----------------------------------------

    @staticmethod
    def _validated_multipliers(
        raw: dict[str, float] | None,
    ) -> dict[str, float]:
        defaults = {"lower_leg": 1.0, "upper_leg": 1.0, "torso": 1.0}
        if raw is None:
            return defaults
        out: dict[str, float] = {}
        for k, v in defaults.items():
            val = raw.get(k, v)
            assert 0.5 <= val <= 2.0, f"{k} multiplier out of range"
            out[k] = val
        return out

    def _compute_lengths(self, height: float, mults: dict[str, float]) -> None:
        self.L = np.array(
            [
                LENGTH_FRAC["lower_leg"] * height * mults["lower_leg"],
                LENGTH_FRAC["upper_leg"] * height * mults["upper_leg"],
                LENGTH_FRAC["torso"] * height * mults["torso"],
            ]
        )
        self.L_arm = LENGTH_FRAC["arm"] * height
        self.foot_length = LENGTH_FRAC["foot"] * height

    def _compute_base_of_support(self) -> None:
        """Compute full and inner (constrained) base-of-support bounds.

        The ankle sits at x=0.  The heel is slightly behind, the toe
        extends forward.  The *inner* zone is the middle BOS_INNER_FRACTION
        of the foot -- the outer 20% on each end is out-of-bounds for the
        COM constraint.
        """
        self.heel_x = -0.05 * self.foot_length
        self.toe_x = 0.95 * self.foot_length

        foot_span = self.toe_x - self.heel_x
        outer_margin = (1.0 - BOS_INNER_FRACTION) / 2.0 * foot_span
        self.inner_heel = self.heel_x + outer_margin
        self.inner_toe = self.toe_x - outer_margin

        # Centers for soft preference penalties
        self.bos_center = 0.5 * (self.heel_x + self.toe_x)
        self.inner_center = 0.5 * (self.inner_heel + self.inner_toe)

    def _compute_masses(self, bm: float) -> None:
        self.m_feet = MASS_FRAC["feet"] * bm
        self.foot_com_x = self.bos_center
        self.foot_com_y = 0.0

        self.m_squat = np.array(
            [
                MASS_FRAC["lower_legs"] * bm,
                MASS_FRAC["upper_legs"] * bm,
                (MASS_FRAC["trunk_head"] + MASS_FRAC["arms"]) * bm,
            ]
        )
        self.m_deadlift = np.array(
            [
                MASS_FRAC["lower_legs"] * bm,
                MASS_FRAC["upper_legs"] * bm,
                MASS_FRAC["trunk_head"] * bm,
            ]
        )
        self.m_arms = MASS_FRAC["arms"] * bm

    def _compute_com_distances(self) -> None:
        self.d = np.array(
            [
                COM_FRAC["lower_leg"] * self.L[0],
                COM_FRAC["upper_leg"] * self.L[1],
                COM_FRAC["torso"] * self.L[2],
            ]
        )

    def _compute_inertias(self) -> None:
        self.I_squat = (1.0 / 12.0) * self.m_squat * self.L**2
        self.I_deadlift = (1.0 / 12.0) * self.m_deadlift * self.L**2


class LagrangianDynamics(PhysicsBackend):
    """Analytical inverse dynamics for a 3-link planar chain.

    Computes M(q)*qdd + C(q,qd) + G(q) = tau analytically.

    Preconditions:
        body is a valid BodyModel
        m_segments, I_segments are length-3 arrays
        load_mass >= 0
    """

    def __init__(
        self,
        body: BodyModel,
        m_segments: NDArray,
        I_segments: NDArray,
        load_mass: float,
    ) -> None:
        assert len(m_segments) == 3, "need 3 segment masses"
        assert load_mass >= 0, "load_mass cannot be negative"
        self.body = body
        self.L = body.L
        self.d = body.d
        self.m = m_segments
        self.I = I_segments
        self.m_load = load_mass
        self.g = body.g

        # Pre-compute coupling coefficients (constant for given model)
        self._a01 = (m_segments[1] * body.d[1] + (m_segments[2] + load_mass) * body.L[1]) * body.L[
            0
        ]
        self._a02 = (m_segments[2] * body.d[2] + load_mass * body.L[2]) * body.L[0]
        self._a12 = (m_segments[2] * body.d[2] + load_mass * body.L[2]) * body.L[1]

        # Diagonal mass-matrix constants
        self._M00 = (
            m_segments[0] * body.d[0] ** 2
            + (m_segments[1] + m_segments[2] + load_mass) * body.L[0] ** 2
            + I_segments[0]
        )
        self._M11 = (
            m_segments[1] * body.d[1] ** 2
            + (m_segments[2] + load_mass) * body.L[1] ** 2
            + I_segments[1]
        )
        self._M22 = m_segments[2] * body.d[2] ** 2 + load_mass * body.L[2] ** 2 + I_segments[2]

        # Gravity coefficients
        self._g0 = body.g * (
            m_segments[0] * body.d[0] + (m_segments[1] + m_segments[2] + load_mass) * body.L[0]
        )
        self._g1 = body.g * (m_segments[1] * body.d[1] + (m_segments[2] + load_mass) * body.L[1])
        self._g2 = body.g * (m_segments[2] * body.d[2] + load_mass * body.L[2])

    @property
    def n_dof(self) -> int:
        return 3

    @property
    def name(self) -> str:
        return "Lagrangian (3-link planar)"

    def mass_matrix(self, q: NDArray) -> NDArray:
        M = np.zeros((3, 3))
        M[0, 0] = self._M00
        M[1, 1] = self._M11
        M[2, 2] = self._M22
        M[0, 1] = M[1, 0] = self._a01 * np.cos(q[0] - q[1])
        M[0, 2] = M[2, 0] = self._a02 * np.cos(q[0] - q[2])
        M[1, 2] = M[2, 1] = self._a12 * np.cos(q[1] - q[2])
        return M

    def _coriolis_vector(self, q: NDArray, qd: NDArray) -> NDArray:
        s01 = np.sin(q[0] - q[1])
        s02 = np.sin(q[0] - q[2])
        s12 = np.sin(q[1] - q[2])
        C = np.zeros(3)
        C[0] = self._a01 * s01 * qd[1] ** 2 + self._a02 * s02 * qd[2] ** 2
        C[1] = -self._a01 * s01 * qd[0] ** 2 + self._a12 * s12 * qd[2] ** 2
        C[2] = -self._a02 * s02 * qd[0] ** 2 - self._a12 * s12 * qd[1] ** 2
        return C

    def _gravity_vector(self, q: NDArray) -> NDArray:
        G = np.zeros(3)
        G[0] = self._g0 * np.sin(q[0])
        G[1] = self._g1 * np.sin(q[1])
        G[2] = self._g2 * np.sin(q[2])
        return G

    def inverse_dynamics(self, q: NDArray, qd: NDArray, qdd: NDArray) -> NDArray:
        return self.mass_matrix(q) @ qdd + self._coriolis_vector(q, qd) + self._gravity_vector(q)

    def inverse_dynamics_batch(self, q: NDArray, qd: NDArray, qdd: NDArray) -> NDArray:
        """Vectorised batch torques for all timesteps.

        Parameters:
            q, qd, qdd: shape (N, 3)
        Returns:
            torques: shape (N, 3)
        """
        # Try Rust accelerator first
        try:
            from movement_optimizer_core import inverse_dynamics_batch_rs  # type: ignore[import-not-found]  # noqa: I001

            return inverse_dynamics_batch_rs(
                q,
                qd,
                qdd,
                self._M00,
                self._M11,
                self._M22,
                self._a01,
                self._a02,
                self._a12,
                self._g0,
                self._g1,
                self._g2,
            )
        except ImportError:
            pass

        n = q.shape[0]
        sq = np.sin(q)
        d01 = q[:, 0] - q[:, 1]
        d02 = q[:, 0] - q[:, 2]
        d12 = q[:, 1] - q[:, 2]

        c01 = np.cos(d01)
        c02 = np.cos(d02)
        c12 = np.cos(d12)

        tau = np.empty((n, 3))
        tau[:, 0] = (
            self._M00 * qdd[:, 0] + self._a01 * c01 * qdd[:, 1] + self._a02 * c02 * qdd[:, 2]
        )
        tau[:, 1] = (
            self._a01 * c01 * qdd[:, 0] + self._M11 * qdd[:, 1] + self._a12 * c12 * qdd[:, 2]
        )
        tau[:, 2] = (
            self._a02 * c02 * qdd[:, 0] + self._a12 * c12 * qdd[:, 1] + self._M22 * qdd[:, 2]
        )

        s01 = np.sin(d01)
        s02 = np.sin(d02)
        s12 = np.sin(d12)

        tau[:, 0] += self._a01 * s01 * qd[:, 1] ** 2 + self._a02 * s02 * qd[:, 2] ** 2
        tau[:, 1] += -self._a01 * s01 * qd[:, 0] ** 2 + self._a12 * s12 * qd[:, 2] ** 2
        tau[:, 2] += -self._a02 * s02 * qd[:, 0] ** 2 - self._a12 * s12 * qd[:, 1] ** 2

        tau[:, 0] += self._g0 * sq[:, 0]
        tau[:, 1] += self._g1 * sq[:, 1]
        tau[:, 2] += self._g2 * sq[:, 2]

        return tau

    def com_x_batch(
        self,
        q: NDArray,
        exercise_type: str = "squat",
        bar_mass: float = 0.0,
    ) -> NDArray:
        """Vectorised batch COM x-coordinate.

        Parameters:
            q: shape (N, 3)
        Returns:
            com_x: shape (N,)
        """
        b = self.body
        sq = np.sin(q)

        knee_x = b.L[0] * sq[:, 0]
        hip_x = knee_x + b.L[1] * sq[:, 1]
        shoulder_x = hip_x + b.L[2] * sq[:, 2]

        c1x = b.d[0] * sq[:, 0]
        c2x = knee_x + b.d[1] * sq[:, 1]
        c3x = hip_x + b.d[2] * sq[:, 2]

        total_mass = b.body_mass + bar_mass
        numerator = b.m_feet * b.foot_com_x + self.m[0] * c1x + self.m[1] * c2x + self.m[2] * c3x

        if exercise_type in ("squat", "full_squat"):
            numerator += bar_mass * shoulder_x
        else:
            numerator += b.m_arms * shoulder_x + bar_mass * shoulder_x

        return numerator / total_mass

    def forward_kinematics(self, q: NDArray) -> dict[str, NDArray]:
        L = self.L
        ankle = np.array([0.0, 0.0])
        knee = ankle + L[0] * np.array([np.sin(q[0]), np.cos(q[0])])
        hip = knee + L[1] * np.array([np.sin(q[1]), np.cos(q[1])])
        shoulder = hip + L[2] * np.array([np.sin(q[2]), np.cos(q[2])])
        return {"ankle": ankle, "knee": knee, "hip": hip, "shoulder": shoulder}

    def bar_position(self, q: NDArray, exercise_type: str) -> NDArray:
        fk = self.forward_kinematics(q)
        s = fk["shoulder"]
        if exercise_type == "deadlift":
            return np.array([s[0], s[1] - self.body.L_arm])
        return s.copy()

    def com_position(
        self,
        q: NDArray,
        exercise_type: str = "squat",
        bar_mass: float = 0.0,
    ) -> NDArray:
        b = self.body
        ankle = np.array([0.0, 0.0])
        c1 = ankle + b.d[0] * np.array([np.sin(q[0]), np.cos(q[0])])
        knee = ankle + b.L[0] * np.array([np.sin(q[0]), np.cos(q[0])])
        c2 = knee + b.d[1] * np.array([np.sin(q[1]), np.cos(q[1])])
        hip = knee + b.L[1] * np.array([np.sin(q[1]), np.cos(q[1])])
        c3 = hip + b.d[2] * np.array([np.sin(q[2]), np.cos(q[2])])
        shoulder = hip + b.L[2] * np.array([np.sin(q[2]), np.cos(q[2])])

        foot_com = np.array([b.foot_com_x, b.foot_com_y])
        total_mass = b.body_mass + bar_mass

        numerator = b.m_feet * foot_com + self.m[0] * c1 + self.m[1] * c2 + self.m[2] * c3

        if exercise_type in ("squat", "full_squat"):
            numerator += bar_mass * shoulder
        else:
            arm_com = np.array([shoulder[0], shoulder[1] - COM_FRAC["arm"] * b.L_arm])
            bar_pos = np.array([shoulder[0], shoulder[1] - b.L_arm])
            numerator += b.m_arms * arm_com + bar_mass * bar_pos

        return numerator / total_mass


# ==============================================================
# Exercise Configuration Factories
# ==============================================================


def make_squat_config(
    body: BodyModel, bar_mass: float
) -> tuple[LagrangianDynamics, NDArray, NDArray, NDArray]:
    dyn = LagrangianDynamics(body, body.m_squat.copy(), body.I_squat.copy(), bar_mass)
    q_start = np.array([np.radians(20), np.radians(-90), np.radians(40)])
    q_end = np.array([0.0, 0.0, 0.0])
    q_bounds = np.array(
        [
            [np.radians(-5), np.radians(40)],
            [np.radians(-95), np.radians(5)],
            [np.radians(-5), np.radians(60)],
        ]
    )
    return dyn, q_start, q_end, q_bounds


def make_full_squat_config(
    body: BodyModel, bar_mass: float
) -> tuple[LagrangianDynamics, NDArray, NDArray, NDArray, NDArray]:
    dyn = LagrangianDynamics(body, body.m_squat.copy(), body.I_squat.copy(), bar_mass)
    q_start = np.array([0.0, 0.0, 0.0])
    q_end = np.array([0.0, 0.0, 0.0])
    q_via = np.array([np.radians(20), np.radians(-90), np.radians(40)])
    q_bounds = np.array(
        [
            [np.radians(-5), np.radians(40)],
            [np.radians(-95), np.radians(5)],
            [np.radians(-5), np.radians(60)],
        ]
    )
    return dyn, q_start, q_end, q_bounds, q_via


def make_deadlift_config(
    body: BodyModel, bar_mass: float
) -> tuple[LagrangianDynamics, NDArray, NDArray, NDArray]:
    load = body.m_arms + bar_mass
    dyn = LagrangianDynamics(body, body.m_deadlift.copy(), body.I_deadlift.copy(), load)
    q_start = _deadlift_start_angles(body)
    q_end = np.array([0.0, 0.0, 0.0])
    q_bounds = np.array(
        [
            [np.radians(-5), np.radians(30)],
            [np.radians(-80), np.radians(5)],
            [np.radians(-5), np.radians(70)],
        ]
    )
    return dyn, q_start, q_end, q_bounds


def _deadlift_start_angles(body: BodyModel) -> NDArray:
    target_shoulder_h = PLATE_RADIUS_STD_M + body.L_arm
    q0 = np.radians(15)
    q2 = np.radians(52)
    needed = target_shoulder_h - body.L[0] * np.cos(q0) - body.L[2] * np.cos(q2)
    cos_q1 = np.clip(needed / body.L[1], -1, 1)
    q1 = -np.arccos(cos_q1)
    return np.array([q0, q1, q2])
