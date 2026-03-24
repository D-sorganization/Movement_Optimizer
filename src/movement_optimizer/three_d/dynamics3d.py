"""Fail-fast 3D inverse dynamics placeholder.

The 16-DOF 3D backend currently exposes sizing information and a diagonal
mass-matrix approximation only. Public dynamics and kinematics entry points
raise a consistent ``NotImplementedError`` until a physically correct backend
exists.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from ..backend import PhysicsBackend
from .body3d import BodyModel3D
from .errors import unsupported_3d_error


class Dynamics3D(PhysicsBackend):
    """3D inverse dynamics via simplified Newton-Euler.

    Implements the :class:`PhysicsBackend` interface with 16 DOFs.
    """

    def __init__(self, body: BodyModel3D, load_mass: float = 0.0) -> None:
        self.body = body
        self.load_mass = load_mass
        self._g = 9.81
        # Diagonal mass matrix approximation (moment of inertia per DOF)
        self._M_diag = self._build_diagonal_mass_matrix()

    # -- PhysicsBackend interface --------------------------------------

    @property
    def n_dof(self) -> int:
        return 16

    @property
    def name(self) -> str:
        return "Dynamics3D"

    def forward_kinematics(self, q: NDArray) -> dict[str, NDArray]:
        return self.body.forward_kinematics(q)

    def bar_position(self, q: NDArray, exercise_type: str) -> NDArray:
        """Return barbell position for the 3D backend."""
        raise unsupported_3d_error("3D bar position")

    def com_position(
        self,
        q: NDArray,
        exercise_type: str = "squat",
        bar_mass: float = 0.0,
    ) -> NDArray:
        """Return 3D whole-body centre of mass."""
        raise unsupported_3d_error("3D COM position")

    def inverse_dynamics(self, q: NDArray, qd: NDArray, qdd: NDArray) -> NDArray:
        """Compute 3D joint torques."""
        raise unsupported_3d_error("3D inverse dynamics")

    def inverse_dynamics_batch(self, q: NDArray, qd: NDArray, qdd: NDArray) -> NDArray:
        """Vectorised batch torque computation for the 3D backend."""
        raise unsupported_3d_error("3D batch inverse dynamics")

    def com_x_batch(self, q: NDArray, exercise_type: str, bar_mass: float) -> NDArray:
        """Batch COM projected onto the ground plane."""
        raise unsupported_3d_error("3D COM projection batch")

    def mass_matrix(self, q: NDArray) -> NDArray:
        """Return diagonal mass matrix approximation."""
        return np.diag(self._M_diag)

    def _build_diagonal_mass_matrix(self) -> NDArray:
        """Build a diagonal inertia approximation per DOF.

        Each DOF's effective inertia is approximated as the mass of all
        segments distal to that joint times the square of the segment
        length (simplified rod inertia).
        """
        b = self.body
        m = b.segment_masses

        # Helper: sum of masses for a set of segments
        def msum(*names: str) -> float:
            return sum(m[n] for n in names)

        # Approximate effective inertia per DOF
        M = np.zeros(16)

        # Legs: each DOF moves segments above it

        # ankle: moves shank + thigh + share of upper body
        M[0] = msum("shank_l", "thigh_l") * b.shank_length**2
        M[4] = msum("shank_r", "thigh_r") * b.shank_length**2

        # knee: moves thigh
        M[1] = m["thigh_l"] * b.thigh_length**2
        M[5] = m["thigh_r"] * b.thigh_length**2

        # hip flexion: moves torso + head + arms
        upper_mass = msum(
            "pelvis",
            "torso",
            "head",
            "upper_arm_l",
            "upper_arm_r",
            "forearm_l",
            "forearm_r",
            "hand_l",
            "hand_r",
        )
        M[2] = upper_mass * b.thigh_length**2
        M[6] = upper_mass * b.thigh_length**2

        # hip abduction
        M[3] = upper_mass * b.thigh_length**2 * 0.3
        M[7] = upper_mass * b.thigh_length**2 * 0.3

        # spine flexion / lateral bend
        trunk_mass = msum(
            "torso",
            "head",
            "upper_arm_l",
            "upper_arm_r",
            "forearm_l",
            "forearm_r",
            "hand_l",
            "hand_r",
        )
        M[8] = trunk_mass * b.torso_length**2
        M[9] = trunk_mass * b.torso_length**2 * 0.3

        # shoulder flexion / abduction
        arm_mass_l = msum("upper_arm_l", "forearm_l", "hand_l")
        arm_mass_r = msum("upper_arm_r", "forearm_r", "hand_r")
        M[10] = arm_mass_l * b.upper_arm_length**2
        M[11] = arm_mass_l * b.upper_arm_length**2 * 0.3
        M[13] = arm_mass_r * b.upper_arm_length**2
        M[14] = arm_mass_r * b.upper_arm_length**2 * 0.3

        # elbow flexion
        M[12] = msum("forearm_l", "hand_l") * b.forearm_length**2
        M[15] = msum("forearm_r", "hand_r") * b.forearm_length**2

        return M
