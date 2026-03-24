"""3D bilateral body model with anatomical segments.

Uses Winter (2009) anthropometric mass fractions and segment length
proportions to build a 15-segment model driven by 16 simplified DOFs.
"""

from __future__ import annotations

from typing import ClassVar

from numpy.typing import NDArray


class BodyModel3D:
    """3D bilateral body model with anatomical segments.

    The model has 15 rigid segments connected by joints.  A simplified
    16-DOF generalized-coordinate vector *q* drives the forward
    kinematics.

    q layout (16 DOF)::

        0  ankle_l       (dorsiflexion)
        1  knee_l        (flexion)
        2  hip_flex_l    (flexion)
        3  hip_abd_l     (abduction)
        4  ankle_r       (dorsiflexion)
        5  knee_r        (flexion)
        6  hip_flex_r    (flexion)
        7  hip_abd_r     (abduction)
        8  spine_flex    (flexion)
        9  spine_lat     (lateral bend)
       10  shoulder_flex_l (flexion)
       11  shoulder_abd_l  (abduction)
       12  elbow_l       (flexion)
       13  shoulder_flex_r (flexion)
       14  shoulder_abd_r  (abduction)
       15  elbow_r       (flexion)
    """

    SEGMENTS: ClassVar[list[str]] = [
        "foot_l",
        "foot_r",
        "shank_l",
        "shank_r",
        "thigh_l",
        "thigh_r",
        "pelvis",
        "torso",
        "head",
        "upper_arm_l",
        "upper_arm_r",
        "forearm_l",
        "forearm_r",
        "hand_l",
        "hand_r",
    ]

    # Winter (2009) bilateral mass fractions (% of body mass)
    _MASS_FRACTIONS: ClassVar[dict[str, float]] = {
        "foot_l": 0.0145,
        "foot_r": 0.0145,
        "shank_l": 0.0465,
        "shank_r": 0.0465,
        "thigh_l": 0.1000,
        "thigh_r": 0.1000,
        "pelvis": 0.1420,
        "torso": 0.3340,
        "head": 0.0810,
        "upper_arm_l": 0.0280,
        "upper_arm_r": 0.0280,
        "forearm_l": 0.0160,
        "forearm_r": 0.0160,
        "hand_l": 0.0065,
        "hand_r": 0.0065,
    }

    # Segment length as fraction of height
    _LENGTH_FRACTIONS: ClassVar[dict[str, float]] = {
        "foot": 0.0450,  # ankle height
        "shank": 0.2460,  # ankle to knee
        "thigh": 0.2450,  # knee to hip
        "pelvis": 0.0600,  # hip to L5
        "torso": 0.2880,  # L5 to C7
        "head": 0.1000,  # C7 to top of head
        "upper_arm": 0.1860,  # shoulder to elbow
        "forearm": 0.1460,  # elbow to wrist
        "hand": 0.0560,  # wrist to fingertip
    }

    def __init__(
        self,
        body_mass: float = 75.0,
        height: float = 1.75,
        hip_width: float = 0.30,
        shoulder_width: float = 0.40,
    ) -> None:
        if body_mass <= 0:
            raise ValueError("body_mass must be positive")
        if height <= 0:
            raise ValueError("height must be positive")

        self.body_mass = body_mass
        self.height = height
        self.hip_width = hip_width
        self.shoulder_width = shoulder_width
        self.g = 9.81

        self._compute_segment_lengths()
        self._compute_segment_masses()

    # -- private helpers ------------------------------------------------

    def _compute_segment_lengths(self) -> None:
        """Derive all segment lengths from body height."""
        h = self.height
        lf = self._LENGTH_FRACTIONS
        self.foot_height = lf["foot"] * h
        self.shank_length = lf["shank"] * h
        self.thigh_length = lf["thigh"] * h
        self.pelvis_height = lf["pelvis"] * h
        self.torso_length = lf["torso"] * h
        self.head_length = lf["head"] * h
        self.upper_arm_length = lf["upper_arm"] * h
        self.forearm_length = lf["forearm"] * h
        self.hand_length = lf["hand"] * h

    def _compute_segment_masses(self) -> None:
        """Compute segment masses from body mass and Winter fractions.

        Fractions are normalised so they sum exactly to 1.0, ensuring
        total segment mass equals body_mass.
        """
        raw_total = sum(self._MASS_FRACTIONS[s] for s in self.SEGMENTS)
        self.segment_masses: dict[str, float] = {
            seg: (self._MASS_FRACTIONS[seg] / raw_total) * self.body_mass for seg in self.SEGMENTS
        }

    # -- forward kinematics --------------------------------------------

    def forward_kinematics(self, q: NDArray) -> dict[str, NDArray]:
        """Return 3D positions of all joints given 16-DOF vector *q*.

        .. warning::
            **Not yet implemented.** The 3D kinematics chain is planned for a future
            release. Use the 2D optimizer (``movement_optimizer.trajectory``) for
            functional trajectory optimization.

        Raises:
            NotImplementedError: Always — this method is not yet implemented.
        """
        if len(q) != 16:
            raise ValueError(f"q must be 16-DOF, got {len(q)}")
        raise NotImplementedError(
            "3D forward kinematics is not yet implemented. "
            "Use the 2D optimizer (movement_optimizer.trajectory.TrajectoryOptimizer) "
            "for functional trajectory optimization. See GitHub issue #76."
        )
