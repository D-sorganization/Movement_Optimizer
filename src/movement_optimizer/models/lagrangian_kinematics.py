"""Kinematic output methods for the Lagrangian planar-chain model.

``LagrangianKinematicsMixin`` provides forward kinematics, bar-position
lookup, batch COM x-coordinate, and full COM position for the 3-link
sagittal chain.  It is mixed into ``LagrangianDynamics`` so that the core
physics class stays focused on mass-matrix and torque computation.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


class LagrangianKinematicsMixin:
    """Kinematics helpers for a 3-link sagittal chain.

    Assumes the owning class has:
        self.body      -- BodyModel
        self.m         -- (3,) segment masses
        self.L_eff     -- (3,) effective segment lengths
        self.d_eff     -- (3,) effective COM distances
        self.joint_names -- list[str] of joint names
    """

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
        b = self.body  # type: ignore[attr-defined]
        sq = np.sin(q)
        L = self.L_eff  # type: ignore[attr-defined]
        d = self.d_eff  # type: ignore[attr-defined]

        m = self.m  # type: ignore[attr-defined]

        # Using @ for matrix-vector multiplication is significantly faster than
        # allocating intermediate arrays for individual joints.
        shoulder_x = sq @ L
        w = np.array([m[0] * d[0] + (m[1] + m[2]) * L[0], m[1] * d[1] + m[2] * L[1], m[2] * d[2]])

        total_mass = b.body_mass + bar_mass
        numerator = b.m_feet * b.foot_com_x + sq @ w

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
        """Compute joint positions for all joints in the chain."""
        L = self.L_eff  # type: ignore[attr-defined]
        names = self.joint_names  # type: ignore[attr-defined]

        sq = np.sin(q)
        cq = np.cos(q)

        # Computing scalar coordinates avoids allocating 3 intermediate length-2 arrays.
        p0 = np.array([0.0, 0.0])
        p1 = np.array([L[0] * sq[0], L[0] * cq[0]])
        p2 = np.array([p1[0] + L[1] * sq[1], p1[1] + L[1] * cq[1]])
        p3 = np.array([p2[0] + L[2] * sq[2], p2[1] + L[2] * cq[2]])

        return {names[0]: p0, names[1]: p1, names[2]: p2, names[3]: p3}

    def bar_position(self, q: NDArray, exercise_type: str) -> NDArray:
        """Return the barbell position vector for a given joint configuration."""
        fk = self.forward_kinematics(q)
        s = fk["shoulder"]
        if exercise_type in ("squat", "full_squat"):
            b = self.body  # type: ignore[attr-defined]
            if hasattr(b, "squat_bar_depth") and (
                b.squat_bar_depth != 0.0 or b.squat_bar_height != 0.0
            ):
                u_down = np.array([-np.sin(q[2]), -np.cos(q[2])])
                u_back = np.array([-np.cos(q[2]), np.sin(q[2])])
                return s + b.squat_bar_height * u_down + b.squat_bar_depth * u_back
            return s.copy()
        if exercise_type == "deadlift":
            # Bar hangs from hands: arm-length below shoulder
            return np.array([s[0], s[1] - self.body.L_arm])  # type: ignore[attr-defined]
        if exercise_type in ("clean", "clean_and_jerk"):
            # Front rack: bar sits at shoulder height
            return s.copy()
        if exercise_type in ("snatch", "jerk"):
            # Overhead: bar is arm-length above shoulder
            return np.array([s[0], s[1] + self.body.L_arm])  # type: ignore[attr-defined]
        return s.copy()

    def com_position(
        self,
        q: NDArray,
        exercise_type: str = "squat",
        bar_mass: float = 0.0,
    ) -> NDArray:
        """Return the whole-body COM position vector."""
        from ..constants import COM_FRAC

        b = self.body  # type: ignore[attr-defined]
        L = self.L_eff  # type: ignore[attr-defined]
        d = self.d_eff  # type: ignore[attr-defined]
        sq = np.sin(q)
        cq = np.cos(q)
        m = self.m  # type: ignore[attr-defined]

        foot_com = np.array([b.foot_com_x, b.foot_com_y])
        total_mass = b.body_mass + bar_mass

        # Computing scalar coordinates and unrolling the sums is significantly faster
        # than allocating ~15 intermediate numpy arrays for vectors.
        w0 = m[0] * d[0] + (m[1] + m[2]) * L[0]
        w1 = m[1] * d[1] + m[2] * L[1]
        w2 = m[2] * d[2]

        numerator = b.m_feet * foot_com + np.array(
            [w0 * sq[0] + w1 * sq[1] + w2 * sq[2], w0 * cq[0] + w1 * cq[1] + w2 * cq[2]]
        )

        shoulder = np.array(
            [L[0] * sq[0] + L[1] * sq[1] + L[2] * sq[2], L[0] * cq[0] + L[1] * cq[1] + L[2] * cq[2]]
        )

        if exercise_type in ("squat", "full_squat"):
            numerator += bar_mass * self.bar_position(q, exercise_type)
        else:
            bar_pos = self.bar_position(q, exercise_type)
            # Arm vector from shoulder to bar
            arm_vec = bar_pos - shoulder
            arm_com = shoulder + COM_FRAC["arm"] * arm_vec
            numerator += b.m_arms * arm_com + bar_mass * bar_pos

        return numerator / total_mass
