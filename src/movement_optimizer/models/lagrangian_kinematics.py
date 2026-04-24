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

        knee_x = L[0] * sq[:, 0]
        hip_x = knee_x + L[1] * sq[:, 1]
        shoulder_x = hip_x + L[2] * sq[:, 2]

        c1x = d[0] * sq[:, 0]
        c2x = knee_x + d[1] * sq[:, 1]
        c3x = hip_x + d[2] * sq[:, 2]

        total_mass = b.body_mass + bar_mass
        numerator = (
            b.m_feet * b.foot_com_x
            + self.m[0] * c1x  # type: ignore[attr-defined]
            + self.m[1] * c2x  # type: ignore[attr-defined]
            + self.m[2] * c3x  # type: ignore[attr-defined]
        )

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
        p0 = np.array([0.0, 0.0])
        p1 = p0 + L[0] * np.array([np.sin(q[0]), np.cos(q[0])])
        p2 = p1 + L[1] * np.array([np.sin(q[1]), np.cos(q[1])])
        p3 = p2 + L[2] * np.array([np.sin(q[2]), np.cos(q[2])])
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
        ankle = np.array([0.0, 0.0])
        c1 = ankle + d[0] * np.array([np.sin(q[0]), np.cos(q[0])])
        knee = ankle + L[0] * np.array([np.sin(q[0]), np.cos(q[0])])
        c2 = knee + d[1] * np.array([np.sin(q[1]), np.cos(q[1])])
        hip = knee + L[1] * np.array([np.sin(q[1]), np.cos(q[1])])
        c3 = hip + d[2] * np.array([np.sin(q[2]), np.cos(q[2])])
        shoulder = hip + L[2] * np.array([np.sin(q[2]), np.cos(q[2])])

        foot_com = np.array([b.foot_com_x, b.foot_com_y])
        total_mass = b.body_mass + bar_mass

        numerator = (
            b.m_feet * foot_com
            + self.m[0] * c1  # type: ignore[attr-defined]
            + self.m[1] * c2  # type: ignore[attr-defined]
            + self.m[2] * c3  # type: ignore[attr-defined]
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
