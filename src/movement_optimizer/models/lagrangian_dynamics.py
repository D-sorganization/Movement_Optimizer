"""Lagrangian inverse dynamics for a 3-link planar chain.

Contains ``LagrangianDynamics`` and the ``balance_pose`` helper.
"""

from __future__ import annotations

import logging

import numpy as np
from numpy.typing import NDArray

from ..backend import PhysicsBackend
from ..constants import (
    JOINT_LIMITS,
    STANDING_DEG,
)
from .body_model import BodyModel, ChainGeometry

logger = logging.getLogger(__name__)

__all__ = [
    "LagrangianDynamics",
    "balance_pose",
]


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
        chain_geometry: ChainGeometry | None = None,
        supine: bool = False,
    ) -> None:
        """Initialise Lagrangian dynamics for a 3-link planar chain.

        Parameters:
            body: Anthropometric model (used for g, BOS, and default geometry).
            m_segments: Length-3 array of segment masses (kg).
            I_segments: Length-3 array of segment moments of inertia (kg·m²).
            load_mass: Mass of the external load at the chain tip (kg).
            chain_geometry: Optional ChainGeometry providing segment lengths,
                COM distances, and joint names for non-leg kinematic chains
                (e.g. the arm chain for bench press).
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

        L, d = self._init_chain_geometry(body, chain_geometry)
        self._init_coupling_coefficients(m_segments, load_mass, L, d)
        self._init_diagonal_mass_constants(m_segments, I_segments, load_mass, L, d)
        self._init_gravity_coefficients(body.g, m_segments, load_mass, L, d)

    # -- init helpers -----------------------------------------------

    def _init_chain_geometry(
        self,
        body: BodyModel,
        chain_geometry: ChainGeometry | None,
    ) -> tuple[NDArray, NDArray]:
        """Set segment lengths, COM distances, and joint names.

        Returns the (L, d) arrays used by subsequent coefficient setup.
        """
        if chain_geometry is not None:
            L = chain_geometry.L
            d = chain_geometry.d
            self.L = L
            self.L_eff = L.copy()
            self.d = d
            self.d_eff = d.copy()
            self.joint_names = list(chain_geometry.joint_names)
        else:
            self.L = body.L
            self.L_eff = body.L_eff
            self.d = body.d
            self.d_eff = body.d_eff
            self.joint_names = ["ankle", "knee", "hip", "shoulder"]
            L = body.L
            d = body.d
        return L, d

    def _init_coupling_coefficients(
        self,
        m: NDArray,
        m_load: float,
        L: NDArray,
        d: NDArray,
    ) -> None:
        """Pre-compute off-diagonal coupling coefficients (constant for a given model)."""
        self._a01 = (m[1] * d[1] + (m[2] + m_load) * L[1]) * L[0]
        self._a02 = (m[2] * d[2] + m_load * L[2]) * L[0]
        self._a12 = (m[2] * d[2] + m_load * L[2]) * L[1]

    def _init_diagonal_mass_constants(
        self,
        m: NDArray,
        inertia: NDArray,
        m_load: float,
        L: NDArray,
        d: NDArray,
    ) -> None:
        """Pre-compute diagonal mass-matrix constants."""
        self._M00 = m[0] * d[0] ** 2 + (m[1] + m[2] + m_load) * L[0] ** 2 + inertia[0]
        self._M11 = m[1] * d[1] ** 2 + (m[2] + m_load) * L[1] ** 2 + inertia[1]
        self._M22 = m[2] * d[2] ** 2 + m_load * L[2] ** 2 + inertia[2]

    def _init_gravity_coefficients(
        self,
        g: float,
        m: NDArray,
        m_load: float,
        L: NDArray,
        d: NDArray,
    ) -> None:
        """Pre-compute gravity torque coefficients."""
        self._g0 = g * (m[0] * d[0] + (m[1] + m[2] + m_load) * L[0])
        self._g1 = g * (m[1] * d[1] + (m[2] + m_load) * L[1])
        self._g2 = g * (m[2] * d[2] + m_load * L[2])

    @property
    def segment_lengths(self) -> NDArray:
        """Lengths of the active kinematic chain segments."""
        return self.L

    @property
    def n_dof(self) -> int:
        """Number of degrees of freedom for this dynamics model (always 3)."""
        return 3

    @property
    def name(self) -> str:
        """Human-readable name identifying this dynamics backend."""
        return "Lagrangian (3-link planar)"

    def mass_matrix(self, q: NDArray) -> NDArray:
        """Compute the symmetric 3x3 joint-space mass (inertia) matrix.

        Args:
            q: Joint angle vector of shape (3,) in radians.

        Returns:
            Symmetric (3, 3) mass matrix M(q).
        """
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
        """Compute the gravity loading vector G(q).

        Args:
            q: Joint angle vector of shape (3,) in radians.

        Returns:
            Gravity vector G(q) of shape (3,).
        """
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
            if hasattr(b, "squat_bar_depth") and (
                b.squat_bar_depth != 0.0 or b.squat_bar_height != 0.0
            ):
                bar_x = (
                    shoulder_x - b.squat_bar_height * sq[:, 2] - b.squat_bar_depth * np.cos(q[:, 2])
                )
            else:
                bar_x = shoulder_x
            numerator += bar_mass * bar_x
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
        if exercise_type in ("squat", "full_squat"):
            b = self.body
            if hasattr(b, "squat_bar_depth") and (
                b.squat_bar_depth != 0.0 or b.squat_bar_height != 0.0
            ):
                u_down = np.array([-np.sin(q[2]), -np.cos(q[2])])
                u_back = np.array([-np.cos(q[2]), np.sin(q[2])])
                return s + b.squat_bar_height * u_down + b.squat_bar_depth * u_back
            return s.copy()
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
        from ..constants import COM_FRAC

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
            numerator += bar_mass * self.bar_position(q, exercise_type)
        else:
            bar_pos = self.bar_position(q, exercise_type)
            # Arm vector from shoulder to bar
            arm_vec = bar_pos - shoulder
            arm_com = shoulder + COM_FRAC["arm"] * arm_vec
            numerator += b.m_arms * arm_com + bar_mass * bar_pos

        return numerator / total_mass


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
    q_stand = np.array([np.radians(a) for a in STANDING_DEG])
    return balance_pose(dyn, q_stand, exercise_type, bar_mass, adjust_joint=0)
