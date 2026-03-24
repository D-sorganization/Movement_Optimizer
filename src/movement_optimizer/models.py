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
    BENCH_FOREARM_FRAC,
    BENCH_PRESS_HILL_OPTIMAL_ANGLES,
    BENCH_PRESS_JOINT_LIMITS,
    BENCH_PRESS_JOINT_NAMES,
    BENCH_PRESS_MAX_JOINT_TORQUES,
    BENCH_UPPER_ARM_FRAC,
    BOS_INNER_FRACTION,
    COM_FRAC,
    DEFAULT_MAX_JOINT_TORQUES,
    HILL_ANGLE_WIDTH,
    HILL_ECCENTRIC_FACTOR,
    HILL_K_SHAPE,
    HILL_MAX_ANGULAR_VELOCITY,
    HILL_MAX_ECCENTRIC_RATIO,
    HILL_OPTIMAL_ANGLES,
    JOINT_LIMITS,
    JOINT_NAMES,
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
        self.I_squat = (1.0 / 12.0) * self.m_squat * self.L**2
        self.I_deadlift = (1.0 / 12.0) * self.m_deadlift * self.L**2


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


class HillTorqueModel:
    """Hill-type torque-angle-velocity model for a joint.

    Computes the maximum available torque at a joint given its angle
    and angular velocity:

        τ_avail = τ_max · f_angle(q) · f_velocity(qd)

    f_angle is a Gaussian curve centered at the optimal angle.
    f_velocity follows Hill's force-velocity relationship.

    Preconditions:
        tau_max > 0
        angle_width > 0
        v_max > 0
    """

    def __init__(
        self,
        tau_max: float,
        q_optimal: float,
        angle_width: float = HILL_ANGLE_WIDTH,
        v_max: float = HILL_MAX_ANGULAR_VELOCITY,
        k_shape: float = HILL_K_SHAPE,
        ecc_factor: float = HILL_ECCENTRIC_FACTOR,
        max_ecc_ratio: float = HILL_MAX_ECCENTRIC_RATIO,
    ) -> None:
        if tau_max <= 0:
            raise ValueError("tau_max must be positive")
        if angle_width <= 0:
            raise ValueError("angle_width must be positive")
        if v_max <= 0:
            raise ValueError("v_max must be positive")

        self.tau_max = tau_max
        self.q_optimal = q_optimal
        self.angle_width = angle_width
        self.v_max = v_max
        self.k_shape = k_shape
        self.ecc_factor = ecc_factor
        self.max_ecc_ratio = max_ecc_ratio

    def torque_angle_factor(self, q: float | NDArray) -> NDArray:
        """Gaussian torque-angle scaling factor in [0, 1]."""
        return np.exp(-(((np.asarray(q) - self.q_optimal) / self.angle_width) ** 2))

    def torque_velocity_factor(self, qd: float | NDArray) -> NDArray:
        """Hill-type force-velocity scaling factor.

        Concentric (shortening, same sign as torque direction):
            f = (v_max - |qd|) / (v_max + |qd| / k_shape)
        Eccentric (lengthening):
            f = (1 + ecc_factor * |qd|) / (1 + |qd| / k_shape)

        Clamped to [0, max_ecc_ratio].
        """
        qd = np.asarray(qd)
        speed = np.abs(qd)
        # Concentric branch
        conc = (self.v_max - speed) / (self.v_max + speed / self.k_shape)
        # Eccentric branch
        ecc = (1.0 + self.ecc_factor * speed) / (1.0 + speed / self.k_shape)
        # Use concentric when speed < v_max, eccentric otherwise
        # Actually: concentric when the muscle is shortening (speed < v_max)
        # eccentric when lengthening (always positive factor)
        # We select based on whether concentric factor is still positive
        f = np.where(conc > 0, conc, ecc)
        return np.clip(f, 0.0, self.max_ecc_ratio)

    def available_torque(self, q: float | NDArray, qd: float | NDArray) -> NDArray:
        """Maximum torque the joint can produce at given angle and velocity.

        Returns τ_max * f_angle(q) * f_velocity(qd), always >= 0.
        """
        return self.tau_max * self.torque_angle_factor(q) * self.torque_velocity_factor(qd)


class JointTorqueSet:
    """Collection of Hill torque models for all joints in a chain.

    Provides batch evaluation of torque capacity and identification
    of the limiting joint (sticking point).

    Preconditions:
        joint_names and max_torques must have the same keys
        optimal_angles must have the same keys
    """

    def __init__(
        self,
        joint_names: tuple[str, ...],
        max_torques: dict[str, float],
        optimal_angles: dict[str, float],
        angle_width: float = HILL_ANGLE_WIDTH,
        v_max: float = HILL_MAX_ANGULAR_VELOCITY,
    ) -> None:
        if not all(n in max_torques for n in joint_names):
            raise ValueError("max_torques must cover all joints")
        if not all(n in optimal_angles for n in joint_names):
            raise ValueError("optimal_angles must cover all joints")

        self.joint_names = joint_names
        self._models: dict[str, HillTorqueModel] = {}
        for name in joint_names:
            self._models[name] = HillTorqueModel(
                tau_max=max_torques[name],
                q_optimal=optimal_angles[name],
                angle_width=angle_width,
                v_max=v_max,
            )

    def set_max_torque(self, joint_name: str, tau_max: float) -> None:
        """Update the maximum isometric torque for a joint.

        Preconditions:
            joint_name is a valid joint in this set
            tau_max > 0
        """
        if joint_name not in self._models:
            raise ValueError(f"Unknown joint: {joint_name}")
        if tau_max <= 0:
            raise ValueError("tau_max must be positive")
        self._models[joint_name].tau_max = tau_max

    def get_max_torque(self, joint_name: str) -> float:
        """Return current max isometric torque for a joint."""
        if joint_name not in self._models:
            raise ValueError(f"Unknown joint: {joint_name}")
        return self._models[joint_name].tau_max

    def available_torques(self, q: NDArray, qd: NDArray) -> NDArray:
        """Compute available torque at each joint for a single pose.

        Returns array of shape (n_joints,) with positive values.
        """
        result = np.empty(len(self.joint_names))
        for i, name in enumerate(self.joint_names):
            result[i] = self._models[name].available_torque(q[i], qd[i])
        return result

    def available_torques_batch(self, q: NDArray, qd: NDArray) -> NDArray:
        """Compute available torque at each joint for N poses.

        Parameters:
            q, qd: shape (N, n_joints)
        Returns:
            shape (N, n_joints) with positive values
        """
        n = q.shape[0]
        result = np.empty((n, len(self.joint_names)))
        for i, name in enumerate(self.joint_names):
            result[:, i] = self._models[name].available_torque(q[:, i], qd[:, i])
        return result

    def torque_utilization(self, q: NDArray, qd: NDArray, required_torques: NDArray) -> NDArray:
        """Ratio of required torque to available torque.

        Parameters:
            q, qd: shape (N, n_joints)
            required_torques: shape (N, n_joints)
        Returns:
            shape (N, n_joints) — values > 1.0 mean the joint is overloaded
        """
        available = self.available_torques_batch(q, qd)
        # Avoid division by zero
        safe_avail = np.maximum(available, 1e-10)
        return np.abs(required_torques) / safe_avail

    def find_sticking_point(
        self, q: NDArray, qd: NDArray, required_torques: NDArray
    ) -> tuple[int, str, float]:
        """Find the time step and joint where torque utilization is highest.

        Returns:
            (time_index, joint_name, peak_utilization)

        The sticking point is the moment in the lift where the lifter
        is closest to (or exceeds) their torque capacity.
        """
        utilization = self.torque_utilization(q, qd, required_torques)
        flat_idx = int(np.argmax(utilization))
        time_idx, joint_idx = np.unravel_index(flat_idx, utilization.shape)
        return (
            int(time_idx),
            self.joint_names[joint_idx],
            float(utilization[time_idx, joint_idx]),
        )


def make_default_torque_set() -> JointTorqueSet:
    """Create a JointTorqueSet with default parameters for the standing chain."""
    return JointTorqueSet(
        joint_names=JOINT_NAMES,
        max_torques=DEFAULT_MAX_JOINT_TORQUES,
        optimal_angles=HILL_OPTIMAL_ANGLES,
    )


def make_bench_press_torque_set() -> JointTorqueSet:
    """Create a JointTorqueSet with bench press parameters."""
    return JointTorqueSet(
        joint_names=BENCH_PRESS_JOINT_NAMES,
        max_torques=BENCH_PRESS_MAX_JOINT_TORQUES,
        optimal_angles=BENCH_PRESS_HILL_OPTIMAL_ANGLES,
    )


def compute_max_load(
    dynamics_factory,
    body: BodyModel,
    torque_set: JointTorqueSet,
    exercise_type: str,
    load_range: tuple[float, float] = (0.0, 500.0),
    tol: float = 0.5,
    n_eval: int = 40,
) -> tuple[float, int, str, float]:
    """Binary search for the maximum load a lifter can handle.

    Uses the torque model to find the heaviest bar_mass where peak
    torque utilization stays <= 1.0 across the optimized trajectory.

    Parameters:
        dynamics_factory: callable(body, bar_mass) -> (dyn, qs, qe, qb[, q_via])
        body: BodyModel instance
        torque_set: JointTorqueSet with current max torques
        exercise_type: "squat", "deadlift", "bench_press", etc.
        load_range: (min_load, max_load) search bounds in kg
        tol: convergence tolerance in kg
        n_eval: number of evaluation points for the trajectory

    Returns:
        (max_load_kg, sticking_time_idx, sticking_joint, peak_utilization)

    Preconditions:
        load_range[0] >= 0
        load_range[1] > load_range[0]
        tol > 0
    """
    from .trajectory import TrajectoryOptimizer

    if load_range[0] < 0:
        raise ValueError("min load must be non-negative")
    if load_range[1] <= load_range[0]:
        raise ValueError("max must exceed min")
    if tol <= 0:
        raise ValueError("tolerance must be positive")

    lo, hi = load_range

    def _is_feasible(bar_mass: float) -> tuple[bool, int, str, float]:
        """Check if bar_mass is liftable; return sticking point info."""
        config = dynamics_factory(body, bar_mass)
        if len(config) == 5:
            dyn, qs, qe, qb, q_via = config
        else:
            dyn, qs, qe, qb = config
            q_via = None

        opt = TrajectoryOptimizer(
            body,
            dyn,
            exercise_type,
            bar_mass,
            qs,
            qe,
            qb,
            q_via=q_via,
            duration=2.0,
            n_waypoints=8,
            n_eval=n_eval,
            n_starts=1,
        )
        result = opt.optimize()
        if not result.success:
            return False, 0, "", float("inf")

        time_idx, joint_name, peak_util = torque_set.find_sticking_point(
            result.q, result.qd, result.torques
        )
        return peak_util <= 1.0, time_idx, joint_name, peak_util

    best_time_idx, best_joint, best_util = 0, "", 0.0
    last_feasible_load = lo

    while hi - lo > tol:
        mid = (lo + hi) / 2.0
        feasible, t_idx, j_name, util = _is_feasible(mid)
        if feasible:
            lo = mid
            last_feasible_load = mid
            best_time_idx, best_joint, best_util = t_idx, j_name, util
        else:
            hi = mid

    return last_feasible_load, best_time_idx, best_joint, best_util


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

        # Allow callers to supply alternative segment geometry (e.g. arm chain).
        if body_override is not None:
            L = body_override["L"]
            d = body_override["d"]
            self.L = L
            self.L_eff = L.copy()
            self.d = d
            self.d_eff = d.copy()
        else:
            self.L = body.L
            self.L_eff = body.L_eff
            self.d = body.d
            self.d_eff = body.d_eff
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
        ankle = np.array([0.0, 0.0])
        knee = ankle + L[0] * np.array([np.sin(q[0]), np.cos(q[0])])
        hip = knee + L[1] * np.array([np.sin(q[1]), np.cos(q[1])])
        shoulder = hip + L[2] * np.array([np.sin(q[2]), np.cos(q[2])])
        return {"ankle": ankle, "knee": knee, "hip": hip, "shoulder": shoulder}

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
            arm_com = np.array([shoulder[0], shoulder[1] - COM_FRAC["arm"] * b.L_arm])
            bar_pos = np.array([shoulder[0], shoulder[1] - b.L_arm])
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
    lo, hi = np.radians(-10), np.radians(80)

    def residual(angle: float) -> float:
        q = q_init.copy()
        q[adjust_joint] = angle
        return dyn.com_position(q, exercise_type, bar_mass)[0] - target_x

    # Check if a root exists in the bracket
    f_lo, f_hi = residual(lo), residual(hi)
    if f_lo * f_hi > 0:
        # No root — pick whichever end is closer to target
        q = q_init.copy()
        q[adjust_joint] = lo if abs(f_lo) < abs(f_hi) else hi
        return q

    angle_opt = brentq(residual, lo, hi, xtol=1e-6)
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
        arm_mass = MASS_FRAC["arms"] * body.body_mass
        self.m = np.array(
            [
                0.50 * arm_mass,  # upper arm
                0.35 * arm_mass,  # forearm
                0.15 * arm_mass,  # hand/wrist
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
        body_override={"L": bp.L, "d": bp.d},
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
