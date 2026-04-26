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

        # Performance optimization: Fully unroll scalar components and only instantiate
        # the final return vectors to prevent massive memory allocation overhead from
        # intermediate np.array combinations.
        sq0, sq1, sq2 = np.sin(q)
        cq0, cq1, cq2 = np.cos(q)

        p1_x = L[0] * sq0
        p1_y = L[0] * cq0

        p2_x = p1_x + L[1] * sq1
        p2_y = p1_y + L[1] * cq1

        p3_x = p2_x + L[2] * sq2
        p3_y = p2_y + L[2] * cq2

        return {
            names[0]: np.array([0.0, 0.0]),
            names[1]: np.array([p1_x, p1_y]),
            names[2]: np.array([p2_x, p2_y]),
            names[3]: np.array([p3_x, p3_y]),
        }

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

        # Performance optimization: Fully unroll scalar components to avoid intermediate array allocations
        sq0, sq1, sq2 = np.sin(q)
        cq0, cq1, cq2 = np.cos(q)

        knee_x = L[0] * sq0
        knee_y = L[0] * cq0

        hip_x = knee_x + L[1] * sq1
        hip_y = knee_y + L[1] * cq1

        m0, m1, m2 = self.m  # type: ignore[attr-defined]

        num_x = (
            b.m_feet * b.foot_com_x
            + m0 * (d[0] * sq0)
            + m1 * (knee_x + d[1] * sq1)
            + m2 * (hip_x + d[2] * sq2)
        )

        num_y = (
            b.m_feet * b.foot_com_y
            + m0 * (d[0] * cq0)
            + m1 * (knee_y + d[1] * cq1)
            + m2 * (hip_y + d[2] * cq2)
        )

        shoulder_x = hip_x + L[2] * sq2
        shoulder_y = hip_y + L[2] * cq2
        shoulder = np.array([shoulder_x, shoulder_y])

        total_mass = b.body_mass + bar_mass
        numerator = np.array([num_x, num_y])

        if exercise_type in ("squat", "full_squat"):
            numerator += bar_mass * self.bar_position(q, exercise_type)
        else:
            bar_pos = self.bar_position(q, exercise_type)
            # Arm vector from shoulder to bar
            arm_vec = bar_pos - shoulder
            arm_com = shoulder + COM_FRAC["arm"] * arm_vec
            numerator += b.m_arms * arm_com + bar_mass * bar_pos

        return numerator / total_mass
