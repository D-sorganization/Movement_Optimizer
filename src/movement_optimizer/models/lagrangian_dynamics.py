# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 D-sorganization
"""Lagrangian inverse dynamics for a 3-link planar chain.

Contains ``LagrangianDynamics``.  Balance utilities (``balance_pose``,
``_standing_balanced``) live in ``lagrangian_balance`` and are re-exported
here for backward compatibility.
"""

from __future__ import annotations

import logging
import math

import numpy as np
from numpy.typing import NDArray

from ..backend import PhysicsBackend
from .body_model import BodyModel, ChainGeometry
from .lagrangian_balance import _standing_balanced, balance_pose
from .lagrangian_batch import (
    batch_coriolis_torques,
    batch_gravity_torques,
    batch_inertia_torques,
    numpy_inverse_dynamics_batch,
)
from .lagrangian_kinematics import LagrangianKinematicsMixin

logger = logging.getLogger(__name__)

__all__ = [
    "LagrangianDynamics",
    "_standing_balanced",
    "balance_pose",
]


class LagrangianDynamics(LagrangianKinematicsMixin, PhysicsBackend):
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
        # Performance optimization: Convert to float and use math.sin
        # for unrolled scalar ops, avoiding np.zeros allocation overhead.
        q0, q1, q2 = float(q[0]), float(q[1]), float(q[2])
        qd0, qd1, qd2 = float(qd[0]), float(qd[1]), float(qd[2])
        s01 = math.sin(q0 - q1)
        s02 = math.sin(q0 - q2)
        s12 = math.sin(q1 - q2)
        qd0_sq = qd0 * qd0
        qd1_sq = qd1 * qd1
        qd2_sq = qd2 * qd2
        return np.array(
            [
                self._a01 * s01 * qd1_sq + self._a02 * s02 * qd2_sq,
                -self._a01 * s01 * qd0_sq + self._a12 * s12 * qd2_sq,
                -self._a02 * s02 * qd0_sq - self._a12 * s12 * qd1_sq,
            ]
        )

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
        # Performance optimization:
        # In highly called scalar physical calculations like inverse_dynamics, avoid
        # composing intermediate structural arrays (e.g., 3x3 mass matrices via mass_matrix(),
        # 3x1 vectors via _coriolis_vector() and _gravity_vector()) for immediate matrix
        # multiplication. Instead, unroll the operations into simple scalars to save memory
        # allocation and loop overhead.
        q0, q1, q2 = q
        qd0, qd1, qd2 = qd
        qdd0, qdd1, qdd2 = qdd

        c01 = np.cos(q0 - q1)
        c02 = np.cos(q0 - q2)
        c12 = np.cos(q1 - q2)
        s01 = np.sin(q0 - q1)
        s02 = np.sin(q0 - q2)
        s12 = np.sin(q1 - q2)

        qd2_0 = qd0 * qd0
        qd2_1 = qd1 * qd1
        qd2_2 = qd2 * qd2

        a01_c01 = self._a01 * c01
        a02_c02 = self._a02 * c02
        a12_c12 = self._a12 * c12

        a01_s01 = self._a01 * s01
        a02_s02 = self._a02 * s02
        a12_s12 = self._a12 * s12

        trig = np.cos if self.supine else np.sin
        sq0 = trig(q0)
        sq1 = trig(q1)
        sq2 = trig(q2)

        tau0 = (
            self._M00 * qdd0
            + a01_c01 * qdd1
            + a02_c02 * qdd2
            + a01_s01 * qd2_1
            + a02_s02 * qd2_2
            + self._g0 * sq0
        )
        tau1 = (
            a01_c01 * qdd0
            + self._M11 * qdd1
            + a12_c12 * qdd2
            - a01_s01 * qd2_0
            + a12_s12 * qd2_2
            + self._g1 * sq1
        )
        tau2 = (
            a02_c02 * qdd0
            + a12_c12 * qdd1
            + self._M22 * qdd2
            - a02_s02 * qd2_0
            - a12_s12 * qd2_1
            + self._g2 * sq2
        )

        return np.array([tau0, tau1, tau2])

    def _batch_inertia_torques(
        self,
        qdd: NDArray,
        c01: NDArray,
        c02: NDArray,
        c12: NDArray,
    ) -> NDArray:
        """Inertia contribution — delegates to :func:`lagrangian_batch.batch_inertia_torques`."""
        return batch_inertia_torques(
            qdd,
            c01,
            c02,
            c12,
            M00=self._M00,
            M11=self._M11,
            M22=self._M22,
            a01=self._a01,
            a02=self._a02,
            a12=self._a12,
        )

    def _batch_coriolis_torques(
        self,
        qd: NDArray,
        s01: NDArray,
        s02: NDArray,
        s12: NDArray,
    ) -> NDArray:
        """Coriolis contribution — delegates to :func:`lagrangian_batch.batch_coriolis_torques`."""
        return batch_coriolis_torques(
            qd,
            s01,
            s02,
            s12,
            a01=self._a01,
            a02=self._a02,
            a12=self._a12,
        )

    def _batch_gravity_torques(self, q: NDArray) -> NDArray:
        """Gravity contribution — delegates to :func:`lagrangian_batch.batch_gravity_torques`."""
        return batch_gravity_torques(
            q,
            g0=self._g0,
            g1=self._g1,
            g2=self._g2,
            supine=self.supine,
        )

    def _numpy_inverse_dynamics_batch(self, q: NDArray, qd: NDArray, qdd: NDArray) -> NDArray:
        """NumPy fallback — delegates to :func:`lagrangian_batch.numpy_inverse_dynamics_batch`."""
        return numpy_inverse_dynamics_batch(
            q,
            qd,
            qdd,
            M00=self._M00,
            M11=self._M11,
            M22=self._M22,
            a01=self._a01,
            a02=self._a02,
            a12=self._a12,
            g0=self._g0,
            g1=self._g1,
            g2=self._g2,
            supine=self.supine,
        )

    def inverse_dynamics_batch(self, q: NDArray, qd: NDArray, qdd: NDArray) -> NDArray:
        """Vectorised batch torques (N, 3) for q/qd/qdd each (N, 3).

        Tries the Rust accelerator; falls back to _numpy_inverse_dynamics_batch.
        """
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
        return self._numpy_inverse_dynamics_batch(q, qd, qdd)


# Kinematic methods (com_x_batch, forward_kinematics, bar_position,
# com_position) are inherited from LagrangianKinematicsMixin.
# Balance helpers (balance_pose, _standing_balanced) are imported from
# lagrangian_balance and re-exported via __all__ for backward compatibility.