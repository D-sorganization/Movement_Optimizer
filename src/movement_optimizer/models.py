"""Body model and Lagrangian dynamics engine.

This module contains the anthropometric body model and the analytical
3-link planar dynamics that serve as the default physics backend.

Design Principles:
    DBC -- every public method states and checks its preconditions.
    DRY -- mass/inertia setup is factored into private helpers.
    LoD -- callers interact only through the public API.
"""

from __future__ import annotations

import logging

import numpy as np
from numpy.typing import NDArray

from .backend import PhysicsBackend
from .constants import (
    BENCH_FOREARM_FRAC,
    BENCH_PRESS_JOINT_LIMITS,
    BENCH_UPPER_ARM_FRAC,
    BOS_INNER_FRACTION,
    COM_FRAC,
    JOINT_LIMITS,
    JOINT_NAMES,
    LENGTH_FRAC,
    MASS_FRAC,
    PLATE_RADIUS_STD_M,
    RADIUS_OF_GYRATION_FRAC,
)
from .strength import (
    HillTorqueModel,
    JointTorqueSet,
    compute_max_load,
    make_bench_press_torque_set,
    make_default_torque_set,
)

logger = logging.getLogger(__name__)

__all__ = [
    "BodyModel",
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
    "make_squat_config",
]


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
        abduction_angle: float = 0.0,
        arm_angle: float = 0.0,
    ) -> None:
        if body_mass <= 0:
            raise ValueError("body_mass must be positive")
        if height <= 0:
            raise ValueError("height must be positive")

        self.body_mass = body_mass
        self.height = height
        self.g = 9.81
        self.abduction_angle = abduction_angle
        self.arm_angle = arm_angle

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
            if not (0.5 <= val <= 2.0):
                raise ValueError(f"{k} multiplier out of range")
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

        # Leg abduction correction: project leg lengths into sagittal plane
        abduction_rad = np.radians(self.abduction_angle)
        correction = np.cos(abduction_rad)
        self.L_eff = self.L.copy()
        self.L_eff[0] *= correction  # lower leg projected length
        self.L_eff[1] *= correction  # upper leg projected length
        # torso (index 2) is NOT corrected - it stays in sagittal plane

        # Arm angle projection for bench press side-view
        self.L_arm_eff = self.L_arm * np.sin(np.radians(self.arm_angle))

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
        # Projected COM distances for kinematic calculations
        self.d_eff = np.array(
            [
                COM_FRAC["lower_leg"] * self.L_eff[0],
                COM_FRAC["upper_leg"] * self.L_eff[1],
                COM_FRAC["torso"] * self.L_eff[2],
            ]
        )

    def _compute_inertias(self) -> None:
        """Compute segment inertias using radius of gyration + parallel axis theorem.

        I_com = m * (rho * L)^2          (about segment COM)
        I_prox = I_com + m * d_com^2     (about proximal joint)

        Radius-of-gyration fractions (rho) from Winter (2009), Table 3.1.
        """
        rho = np.array(
            [
                RADIUS_OF_GYRATION_FRAC["lower_leg"],
                RADIUS_OF_GYRATION_FRAC["upper_leg"],
                RADIUS_OF_GYRATION_FRAC["trunk"],
            ]
        )
        I_com_squat = self.m_squat * (rho * self.L) ** 2
        I_com_deadlift = self.m_deadlift * (rho * self.L) ** 2
        self.I_squat = I_com_squat + self.m_squat * self.d**2
        self.I_deadlift = I_com_deadlift + self.m_deadlift * self.d**2


def clamp_joint_angles(
    q: NDArray,
    joint_limits: dict[str, tuple[float, float]] | None = None,
    joint_names: tuple[str, ...] | None = None,
) -> NDArray:
    """Clamp joint angles to their anatomical limits.

    Returns a copy with each angle clamped to [lo, hi].
    Handles the math gracefully: no NaN, no inf, no out-of-range.

    Preconditions:
        q is a 1-D array of length len(joint_names)
        joint_limits keys must include all joint_names
    """
    limits = joint_limits or JOINT_LIMITS
    names = joint_names or JOINT_NAMES
    if len(q) != len(names):
        raise ValueError(f"q length {len(q)} != {len(names)} joint names")
    q_clamped = q.copy()
    for i, name in enumerate(names):
        lo, hi = limits[name]
        q_clamped[i] = np.clip(q_clamped[i], lo, hi)
    return q_clamped


def joint_angles_within_limits(
    q: NDArray,
    joint_limits: dict[str, tuple[float, float]] | None = None,
    joint_names: tuple[str, ...] | None = None,
    tol: float = 1e-6,
) -> bool:
    """Check whether all joint angles are within anatomical limits.

    Preconditions:
        q is a 1-D array of length len(joint_names)
    """
    limits = joint_limits or JOINT_LIMITS
    names = joint_names or JOINT_NAMES
    if len(q) != len(names):
        raise ValueError(f"q length {len(q)} != {len(names)} joint names")
    for i, name in enumerate(names):
        lo, hi = limits[name]
        if q[i] < lo - tol or q[i] > hi + tol:
            return False
    return True


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
        body_override: dict[str, NDArray] | None = None,
        supine: bool = False,
    ) -> None:
        """Initialise Lagrangian dynamics for a 3-link planar chain.

        Parameters:
            body: Anthropometric model (used for g, BOS, and default geometry).
            m_segments: Length-3 array of segment masses (kg).
            I_segments: Length-3 array of segment moments of inertia (kg·m²).
            load_mass: Mass of the external load at the chain tip (kg).
            body_override: Optional dict with keys 'L', 'd' containing
                length-3 NDArrays that override the body geometry for the
                coupling-coefficient calculations.  Used by non-leg kinematic
                chains (e.g. the arm chain for bench press) without resorting
                to post-hoc attribute surgery.
            supine: If True, gravity acts perpendicular to the chain axis
                (the lifter is lying down).  Gravity torque uses cos(q)
                instead of sin(q).  Used for bench press.
        """
        if len(m_segments) != 3:
            raise ValueError("need 3 segment masses")
        if load_mass < 0:
            raise ValueError("load_mass cannot be negative")
        self.body = body
        self.m = m_segments
        self.I = I_segments
        self.m_load = load_mass
        self.g = body.g
        self.supine = supine

        # Allow callers to supply alternative segment geometry (e.g. arm chain).
        if body_override is not None:
            L = body_override["L"]
            d = body_override["d"]
            self.L = L
            self.L_eff = L.copy()
            self.d = d
            self.d_eff = d.copy()
            self.joint_names = body_override.get(
                "joint_names", ["link0", "link1", "link2", "link3"]
            )
        else:
            self.L = body.L
            self.L_eff = body.L_eff
            self.d = body.d
            self.d_eff = body.d_eff
            self.joint_names = ["ankle", "knee", "hip", "shoulder"]
            L = body.L
            d = body.d

        # Pre-compute coupling coefficients (constant for given model)
        self._a01 = (m_segments[1] * d[1] + (m_segments[2] + load_mass) * L[1]) * L[0]
        self._a02 = (m_segments[2] * d[2] + load_mass * L[2]) * L[0]
        self._a12 = (m_segments[2] * d[2] + load_mass * L[2]) * L[1]

        # Diagonal mass-matrix constants
        self._M00 = (
            m_segments[0] * d[0] ** 2
            + (m_segments[1] + m_segments[2] + load_mass) * L[0] ** 2
            + I_segments[0]
        )
        self._M11 = (
            m_segments[1] * d[1] ** 2 + (m_segments[2] + load_mass) * L[1] ** 2 + I_segments[1]
        )
        self._M22 = m_segments[2] * d[2] ** 2 + load_mass * L[2] ** 2 + I_segments[2]

        # Gravity coefficients
        self._g0 = body.g * (
            m_segments[0] * d[0] + (m_segments[1] + m_segments[2] + load_mass) * L[0]
        )
        self._g1 = body.g * (m_segments[1] * d[1] + (m_segments[2] + load_mass) * L[1])
        self._g2 = body.g * (m_segments[2] * d[2] + load_mass * L[2])

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
        """Centrifugal terms of the Coriolis/centrifugal vector.

        NOTE: This implementation includes only the centrifugal (qd_j^2)
        terms and omits the cross-velocity Coriolis terms (qd_i * qd_j,
        i != j).  This is a known simplification that is acceptable for
        slow barbell movements where cross-velocity products are small
        relative to centrifugal and gravitational terms.  A full
        Christoffel-symbol formulation would be needed for fast movements.
        """
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
        trig = np.cos if self.supine else np.sin
        G[0] = self._g0 * trig(q[0])
        G[1] = self._g1 * trig(q[1])
        G[2] = self._g2 * trig(q[2])
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
            logger.debug(
                "Rust accelerator unavailable; falling back to NumPy batch inverse dynamics"
            )

        n = q.shape[0]
        # Supine (bench press): gravity perpendicular to chain → cos(q)
        sq = np.cos(q) if self.supine else np.sin(q)
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
        L = self.L_eff
        d = self.d_eff

        knee_x = L[0] * sq[:, 0]
        hip_x = knee_x + L[1] * sq[:, 1]
        shoulder_x = hip_x + L[2] * sq[:, 2]

        c1x = d[0] * sq[:, 0]
        c2x = knee_x + d[1] * sq[:, 1]
        c3x = hip_x + d[2] * sq[:, 2]

        total_mass = b.body_mass + bar_mass
        numerator = b.m_feet * b.foot_com_x + self.m[0] * c1x + self.m[1] * c2x + self.m[2] * c3x

        if exercise_type in ("squat", "full_squat"):
            numerator += bar_mass * shoulder_x
        else:
            numerator += b.m_arms * shoulder_x + bar_mass * shoulder_x

        return numerator / total_mass

    def forward_kinematics(self, q: NDArray) -> dict[str, NDArray]:
        L = self.L_eff
        names = self.joint_names
        p0 = np.array([0.0, 0.0])
        p1 = p0 + L[0] * np.array([np.sin(q[0]), np.cos(q[0])])
        p2 = p1 + L[1] * np.array([np.sin(q[1]), np.cos(q[1])])
        p3 = p2 + L[2] * np.array([np.sin(q[2]), np.cos(q[2])])
        return {names[0]: p0, names[1]: p1, names[2]: p2, names[3]: p3}

    def bar_position(self, q: NDArray, exercise_type: str) -> NDArray:
        fk = self.forward_kinematics(q)
        s = fk["shoulder"]
        if exercise_type == "deadlift":
            # Bar hangs from hands: arm-length below shoulder
            return np.array([s[0], s[1] - self.body.L_arm])
        if exercise_type in ("clean", "clean_and_jerk"):
            # Front rack: bar sits at shoulder height
            return s.copy()
        if exercise_type in ("snatch", "jerk"):
            # Overhead: bar is arm-length above shoulder
            return np.array([s[0], s[1] + self.body.L_arm])
        return s.copy()

    def com_position(
        self,
        q: NDArray,
        exercise_type: str = "squat",
        bar_mass: float = 0.0,
    ) -> NDArray:
        b = self.body
        L = self.L_eff
        d = self.d_eff
        ankle = np.array([0.0, 0.0])
        c1 = ankle + d[0] * np.array([np.sin(q[0]), np.cos(q[0])])
        knee = ankle + L[0] * np.array([np.sin(q[0]), np.cos(q[0])])
        c2 = knee + d[1] * np.array([np.sin(q[1]), np.cos(q[1])])
        hip = knee + L[1] * np.array([np.sin(q[1]), np.cos(q[1])])
        c3 = hip + d[2] * np.array([np.sin(q[2]), np.cos(q[2])])
        shoulder = hip + L[2] * np.array([np.sin(q[2]), np.cos(q[2])])

        foot_com = np.array([b.foot_com_x, b.foot_com_y])
        total_mass = b.body_mass + bar_mass

        numerator = b.m_feet * foot_com + self.m[0] * c1 + self.m[1] * c2 + self.m[2] * c3

        if exercise_type in ("squat", "full_squat"):
            numerator += bar_mass * shoulder
        else:
            bar_pos = self.bar_position(q, exercise_type)
            # Arm vector from shoulder to bar
            arm_vec = bar_pos - shoulder
            arm_com = shoulder + COM_FRAC["arm"] * arm_vec
            numerator += b.m_arms * arm_com + bar_mass * bar_pos

        return numerator / total_mass


# ==============================================================
# Exercise Configuration Factories
# ==============================================================


def balance_pose(
    dyn: LagrangianDynamics,
    q_init: NDArray,
    exercise_type: str,
    bar_mass: float,
    adjust_joint: int = 2,
) -> NDArray:
    """Adjust one joint angle so the COM lands at the inner BOS center.

    Solves for the angle of ``adjust_joint`` (default: torso) that places
    the whole-body COM_x at ``body.inner_center``.  Uses bisection on the
    COM_x function — guaranteed to converge within joint bounds.

    Preconditions:
        adjust_joint in {0, 1, 2}
        q_init is length-3
    """
    from scipy.optimize import brentq

    body = dyn.body
    target_x = body.inner_center
    # Use actual joint limits from JOINT_LIMITS for the bracket bounds
    # instead of hardcoded values.  For non-monotonic residuals (e.g. hip
    # in a deep squat), scan the bracket to find the first sign change so
    # brentq converges to the nearest root.
    joint_names = ("ankle", "knee", "hip")
    lo, hi = JOINT_LIMITS[joint_names[adjust_joint]]

    def residual(angle: float) -> float:
        q = q_init.copy()
        q[adjust_joint] = angle
        return dyn.com_position(q, exercise_type, bar_mass)[0] - target_x

    # Scan for the first sign change within the bracket.  The residual
    # may be non-monotonic (e.g. hip COM_x peaks mid-range then falls),
    # so a full-bracket brentq can miss roots.  We subdivide into steps
    # and use the first sub-interval that contains a sign change, which
    # yields the smallest-magnitude solution closest to the lower limit.
    n_scan = 20
    angles = np.linspace(lo, hi, n_scan + 1)
    f_vals = np.array([residual(a) for a in angles])
    bracket_lo, bracket_hi = lo, hi
    found_bracket = False
    for k in range(n_scan):
        if f_vals[k] * f_vals[k + 1] <= 0:
            bracket_lo, bracket_hi = angles[k], angles[k + 1]
            found_bracket = True
            break

    if not found_bracket:
        # No root in the joint range -- pick the angle with smallest residual
        best_idx = int(np.argmin(np.abs(f_vals)))
        q = q_init.copy()
        q[adjust_joint] = angles[best_idx]
        return q

    angle_opt = brentq(residual, bracket_lo, bracket_hi, xtol=1e-6)
    q = q_init.copy()
    q[adjust_joint] = angle_opt
    return q


def _standing_balanced(dyn: LagrangianDynamics, bar_mass: float, exercise_type: str) -> NDArray:
    """Find a near-standing pose with COM at inner BOS center.

    Adjusts shin angle (joint 0) to shift COM forward over mid-foot.
    """
    q_stand = np.array([0.0, 0.0, 0.0])
    return balance_pose(dyn, q_stand, exercise_type, bar_mass, adjust_joint=0)


def make_squat_config(
    body: BodyModel, bar_mass: float
) -> tuple[LagrangianDynamics, NDArray, NDArray, NDArray]:
    dyn = LagrangianDynamics(body, body.m_squat.copy(), body.I_squat.copy(), bar_mass)
    # Squat bottom: deep knee bend, torso adjusted for COM balance
    q_bottom_raw = np.array([np.radians(25), np.radians(-90), np.radians(50)])
    q_start = balance_pose(dyn, q_bottom_raw, "squat", bar_mass, adjust_joint=2)
    q_end = _standing_balanced(dyn, bar_mass, "squat")
    q_bounds = np.array(
        [
            [np.radians(-5), np.radians(40)],
            [np.radians(-95), np.radians(5)],
            [np.radians(-5), np.radians(75)],
        ]
    )
    return dyn, q_start, q_end, q_bounds


def make_full_squat_config(
    body: BodyModel, bar_mass: float
) -> tuple[LagrangianDynamics, NDArray, NDArray, NDArray, NDArray]:
    dyn = LagrangianDynamics(body, body.m_squat.copy(), body.I_squat.copy(), bar_mass)
    q_stand = _standing_balanced(dyn, bar_mass, "full_squat")
    q_start = q_stand.copy()
    q_end = q_stand.copy()
    q_bottom_raw = np.array([np.radians(25), np.radians(-90), np.radians(50)])
    q_via = balance_pose(dyn, q_bottom_raw, "full_squat", bar_mass, adjust_joint=2)
    q_bounds = np.array(
        [
            [np.radians(-5), np.radians(40)],
            [np.radians(-95), np.radians(5)],
            [np.radians(-5), np.radians(75)],
        ]
    )
    return dyn, q_start, q_end, q_bounds, q_via


def make_deadlift_config(
    body: BodyModel, bar_mass: float
) -> tuple[LagrangianDynamics, NDArray, NDArray, NDArray]:
    load = body.m_arms + bar_mass
    dyn = LagrangianDynamics(body, body.m_deadlift.copy(), body.I_deadlift.copy(), load)
    q_start_raw = _deadlift_start_angles(body)
    q_start = balance_pose(dyn, q_start_raw, "deadlift", bar_mass, adjust_joint=0)
    q_end = _standing_balanced(dyn, bar_mass, "deadlift")
    q_bounds = np.array(
        [
            [np.radians(-5), np.radians(30)],
            [np.radians(-80), np.radians(5)],
            [np.radians(-5), np.radians(75)],
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


# ==============================================================
# Bench Press Configuration
# ==============================================================


class BenchPressModel:
    """Anthropometric model for the bench press arm chain.

    Maps the 3-link model to: shoulder, elbow, wrist.
    Segment lengths are derived from the full body arm length.

    Preconditions:
        body is a valid BodyModel
    """

    def __init__(self, body: BodyModel) -> None:
        arm_len = body.L_arm
        self.L = np.array(
            [
                BENCH_UPPER_ARM_FRAC * arm_len,
                BENCH_FOREARM_FRAC * arm_len,
                0.01,  # wrist/hand (effectively zero — grip only)
            ]
        )
        self.body_mass = body.body_mass
        # Arm segment masses: split arm mass into upper arm, forearm, hand
        # Fractions per Winter (2009): upper arm 56%, forearm 32%, hand 12%
        arm_mass = MASS_FRAC["arms"] * body.body_mass
        self.m = np.array(
            [
                0.56 * arm_mass,  # upper arm (Winter 2009)
                0.32 * arm_mass,  # forearm (Winter 2009)
                0.12 * arm_mass,  # hand/wrist (Winter 2009)
            ]
        )
        self.d = np.array(
            [
                0.436 * self.L[0],  # upper arm COM
                0.430 * self.L[1],  # forearm COM
                0.500 * self.L[2],  # hand COM
            ]
        )
        self.I = (1.0 / 12.0) * self.m * self.L**2
        self.g = body.g
        # NOTE: BOS bounds are copied for API compatibility but are NOT
        # physically meaningful for bench press.  The lifter is supine on
        # a bench, so the standing base-of-support constraint does not
        # apply.  The optimizer skips COM-in-BOS checks for bench_press.
        self.inner_heel = body.inner_heel
        self.inner_toe = body.inner_toe
        self.inner_center = body.inner_center
        self.height = body.height


def make_bench_press_config(
    body: BodyModel, bar_mass: float
) -> tuple[LagrangianDynamics, NDArray, NDArray, NDArray, NDArray]:
    """Create dynamics and trajectory config for bench press.

    The bench press is modelled as a supine press: gravity acts along
    the vertical axis while the lifter pushes the bar upward from chest
    level.  The 3-link chain represents shoulder, elbow, wrist.

    Full rep: lockout (arms straight) -> chest (arms flexed) -> lockout.
    This uses a via-point trajectory just like full_squat.

    Returns:
        (dynamics, q_start, q_end, q_bounds, q_via)
    """
    bp = BenchPressModel(body)

    # Create a dynamics object using arm segment properties.
    # Pass body_override so the constructor uses arm geometry (L, d) for all
    # coupling-coefficient calculations — no post-hoc attribute surgery needed.
    dyn = LagrangianDynamics(
        body,
        bp.m.copy(),
        bp.I.copy(),
        bar_mass,
        body_override={
            "L": bp.L,
            "d": bp.d,
            "joint_names": ["shoulder", "elbow", "wrist", "hand"],
        },
        supine=True,
    )

    # Start: lockout (arms straight up, perpendicular to supine body)
    q_start = np.array([np.radians(0), np.radians(0), np.radians(0)])
    # Via: bar at chest (upper arm ~horizontal, elbow bent ~90 degrees)
    q_via = np.array([np.radians(80), np.radians(-100), np.radians(0)])
    # End: lockout again (full rep)
    q_end = np.array([np.radians(0), np.radians(0), np.radians(0)])

    q_bounds = np.array(
        [
            [BENCH_PRESS_JOINT_LIMITS["shoulder"][0], BENCH_PRESS_JOINT_LIMITS["shoulder"][1]],
            [BENCH_PRESS_JOINT_LIMITS["elbow"][0], BENCH_PRESS_JOINT_LIMITS["elbow"][1]],
            [BENCH_PRESS_JOINT_LIMITS["wrist"][0], BENCH_PRESS_JOINT_LIMITS["wrist"][1]],
        ]
    )

    return dyn, q_start, q_end, q_bounds, q_via
