"""Simplified 3D inverse dynamics via gravity-torque computation.

Uses a quasi-static approach: gravity torques are computed analytically
from segment masses and moment arms.  Inertial torques use a diagonal
mass-matrix approximation.  Coriolis terms are omitted (planned for a
future iteration).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from ..backend import PhysicsBackend
from .body3d import BodyModel3D

_FD_EPSILON: float = 1e-6  # Finite-difference step for gravity torques


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
        """Return barbell position (simplified: at wrist midpoint).

        Raises:
            NotImplementedError: 3D FK is not implemented; Coriolis terms also omitted.
        """
        raise NotImplementedError(
            "3D inverse dynamics requires forward kinematics (GitHub issue #76, not implemented). "
            "Additionally, Coriolis/centrifugal terms are omitted from the mass matrix — "
            "results would be physically incorrect for dynamic movements. See GitHub issue #77."
        )

    def com_position(
        self,
        q: NDArray,
        exercise_type: str = "squat",
        bar_mass: float = 0.0,
    ) -> NDArray:
        """Return 3D whole-body centre of mass.

        Raises:
            NotImplementedError: 3D FK is not implemented; Coriolis terms also omitted.
        """
        raise NotImplementedError(
            "3D inverse dynamics requires forward kinematics (GitHub issue #76, not implemented). "
            "Additionally, Coriolis/centrifugal terms are omitted from the mass matrix — "
            "results would be physically incorrect for dynamic movements. See GitHub issue #77."
        )

    def inverse_dynamics(self, q: NDArray, qd: NDArray, qdd: NDArray) -> NDArray:
        """Compute joint torques: tau = M*qdd + G(q).

        Raises:
            NotImplementedError: 3D FK is not implemented; Coriolis terms also omitted.
        """
        raise NotImplementedError(
            "3D inverse dynamics requires forward kinematics (GitHub issue #76, not implemented). "
            "Additionally, Coriolis/centrifugal terms are omitted from the mass matrix — "
            "results would be physically incorrect for dynamic movements. See GitHub issue #77."
        )

    def inverse_dynamics_batch(self, q: NDArray, qd: NDArray, qdd: NDArray) -> NDArray:
        """Vectorised batch torques: q, qd, qdd are (N, 16).

        Raises:
            NotImplementedError: 3D FK is not implemented; Coriolis terms also omitted.
        """
        raise NotImplementedError(
            "3D inverse dynamics requires forward kinematics (GitHub issue #76, not implemented). "
            "Additionally, Coriolis/centrifugal terms are omitted from the mass matrix — "
            "results would be physically incorrect for dynamic movements. See GitHub issue #77."
        )

    def com_x_batch(self, q: NDArray, exercise_type: str, bar_mass: float) -> NDArray:
        """Batch COM projected onto ground plane (returns x,y for each timestep).

        Raises:
            NotImplementedError: 3D FK is not implemented; Coriolis terms also omitted.
        """
        raise NotImplementedError(
            "3D inverse dynamics requires forward kinematics (GitHub issue #76, not implemented). "
            "Additionally, Coriolis/centrifugal terms are omitted from the mass matrix — "
            "results would be physically incorrect for dynamic movements. See GitHub issue #77."
        )

    def mass_matrix(self, q: NDArray) -> NDArray:
        """Return diagonal mass matrix approximation."""
        return np.diag(self._M_diag)

    # -- private helpers -----------------------------------------------

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

    def _gravity_torques(self, q: NDArray) -> NDArray:
        """Compute gravity generalized forces via central finite differences.

        .. warning::
            **Performance bottleneck** (GitHub issue #79): This method requires
            2 × n_dof = 32 forward kinematics evaluations per call due to numerical
            differentiation with hardcoded step ``eps=1e-6``.

            Replace with analytical gravity torques when FK is implemented:
                ``tau_g = -J_com(q).T @ (total_mass * g_vec)``
            where ``J_com`` is the 3×n_dof Jacobian of the system COM w.r.t. ``q``.

        """
        # NOTE (GitHub issue #78): This method references joint names that must match
        # the output schema of BodyModel3D.forward_kinematics() when it is implemented.
        # Required joint names: "spine_top", "shoulder_l", "shoulder_r", "elbow_l",
        # "elbow_r", "wrist_l", "wrist_r", "pelvis", "head", "hip_l", "hip_r",
        # "knee_l", "knee_r", "ankle_l", "ankle_r".
        # These names MUST be verified against the FK implementation before use.
        eps = _FD_EPSILON
        G = np.zeros(16)
        for i in range(16):
            q_plus = q.copy()
            q_minus = q.copy()
            q_plus[i] += eps
            q_minus[i] -= eps

            joints_plus = self.body.forward_kinematics(q_plus)
            joints_minus = self.body.forward_kinematics(q_minus)

            pe_plus = self._potential_energy(joints_plus)
            pe_minus = self._potential_energy(joints_minus)

            G[i] = (pe_plus - pe_minus) / (2.0 * eps)
        return G

    def _potential_energy(self, joints: dict[str, NDArray]) -> float:
        """Compute gravitational potential energy from joint positions.

        Uses midpoint of adjacent joints as segment COM approximation.
        """
        # NOTE (GitHub issue #78): This method references joint names that must match
        # the output schema of BodyModel3D.forward_kinematics() when it is implemented.
        # Required joint names: "spine_top", "shoulder_l", "shoulder_r", "elbow_l",
        # "elbow_r", "wrist_l", "wrist_r", "pelvis", "head", "hip_l", "hip_r",
        # "knee_l", "knee_r", "ankle_l", "ankle_r".
        # These names MUST be verified against the FK implementation before use.
        b = self.body
        m = b.segment_masses
        g = self._g

        # Map segments to adjacent joint pairs for COM estimation
        seg_joints = {
            "foot_l": ("ankle_l", None),
            "foot_r": ("ankle_r", None),
            "shank_l": ("ankle_l", "knee_l"),
            "shank_r": ("ankle_r", "knee_r"),
            "thigh_l": ("knee_l", "hip_l"),
            "thigh_r": ("knee_r", "hip_r"),
            "pelvis": ("pelvis", None),
            "torso": ("pelvis", "spine_top"),
            "head": ("spine_top", "head"),
            "upper_arm_l": ("shoulder_l", "elbow_l"),
            "upper_arm_r": ("shoulder_r", "elbow_r"),
            "forearm_l": ("elbow_l", "wrist_l"),
            "forearm_r": ("elbow_r", "wrist_r"),
            "hand_l": ("wrist_l", None),
            "hand_r": ("wrist_r", None),
        }

        pe = 0.0
        for seg, (j1, j2) in seg_joints.items():
            com_z = (joints[j1][2] + joints[j2][2]) / 2.0 if j2 is not None else joints[j1][2]
            pe += m[seg] * g * com_z

        # Add load contribution (at bar position = wrist midpoint)
        if self.load_mass > 0:
            bar_z = (joints["wrist_l"][2] + joints["wrist_r"][2]) / 2.0
            pe += self.load_mass * g * bar_z

        return pe

    def _compute_com(self, joints: dict[str, NDArray], bar_mass: float = 0.0) -> NDArray:
        """Compute whole-body 3D centre of mass."""
        b = self.body
        m = b.segment_masses

        seg_joints = {
            "foot_l": ("ankle_l", None),
            "foot_r": ("ankle_r", None),
            "shank_l": ("ankle_l", "knee_l"),
            "shank_r": ("ankle_r", "knee_r"),
            "thigh_l": ("knee_l", "hip_l"),
            "thigh_r": ("knee_r", "hip_r"),
            "pelvis": ("pelvis", None),
            "torso": ("pelvis", "spine_top"),
            "head": ("spine_top", "head"),
            "upper_arm_l": ("shoulder_l", "elbow_l"),
            "upper_arm_r": ("shoulder_r", "elbow_r"),
            "forearm_l": ("elbow_l", "wrist_l"),
            "forearm_r": ("elbow_r", "wrist_r"),
            "hand_l": ("wrist_l", None),
            "hand_r": ("wrist_r", None),
        }

        total_mass = b.body_mass + bar_mass
        com = np.zeros(3)

        for seg, (j1, j2) in seg_joints.items():
            seg_com = (joints[j1] + joints[j2]) / 2.0 if j2 is not None else joints[j1].copy()
            com += m[seg] * seg_com

        if bar_mass > 0:
            bar_pos = (joints["wrist_l"] + joints["wrist_r"]) / 2.0
            com += bar_mass * bar_pos

        com /= total_mass
        return com
