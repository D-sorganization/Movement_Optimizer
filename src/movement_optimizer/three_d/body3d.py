"""3D bilateral body model with anatomical segments.

Uses Winter (2009) anthropometric mass fractions and segment length
proportions to build a 15-segment model driven by 16 simplified DOFs.
"""

from __future__ import annotations

from typing import ClassVar

import numpy as np
from numpy.typing import NDArray

from .math3d import rotation_x, rotation_z


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
        assert body_mass > 0, "body_mass must be positive"
        assert height > 0, "height must be positive"

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

        Coordinate convention: x = left/right, y = front/back, z = up.
        Standing pose (q=0) has the body upright.
        """
        assert len(q) == 16, f"Expected 16 DOF, got {len(q)}"

        joints: dict[str, NDArray] = {}

        # Ground contact: feet on floor (z=0)
        # Hip centres offset laterally from pelvis centre
        half_hip = self.hip_width / 2.0

        # ---- Left leg (bottom-up) ----
        ankle_l = np.array([-half_hip, 0.0, self.foot_height])
        joints["ankle_l"] = ankle_l

        # Ankle dorsiflexion rotates shank about x-axis (sagittal)
        rot_ankle_l = rotation_x(q[0])
        shank_vec_l = rot_ankle_l @ np.array([0.0, 0.0, self.shank_length])
        knee_l = ankle_l + shank_vec_l
        joints["knee_l"] = knee_l

        # Knee flexion
        rot_knee_l = rot_ankle_l @ rotation_x(q[1])
        thigh_vec_l = rot_knee_l @ np.array([0.0, 0.0, self.thigh_length])
        hip_l = knee_l + thigh_vec_l
        joints["hip_l"] = hip_l

        # ---- Right leg (bottom-up) ----
        ankle_r = np.array([half_hip, 0.0, self.foot_height])
        joints["ankle_r"] = ankle_r

        rot_ankle_r = rotation_x(q[4])
        shank_vec_r = rot_ankle_r @ np.array([0.0, 0.0, self.shank_length])
        knee_r = ankle_r + shank_vec_r
        joints["knee_r"] = knee_r

        rot_knee_r = rot_ankle_r @ rotation_x(q[5])
        thigh_vec_r = rot_knee_r @ np.array([0.0, 0.0, self.thigh_length])
        hip_r = knee_r + thigh_vec_r
        joints["hip_r"] = hip_r

        # ---- Pelvis ----
        # Pelvis centre is midpoint of hip joints
        pelvis = (hip_l + hip_r) / 2.0
        joints["pelvis"] = pelvis

        # ---- Spine (from pelvis upward) ----
        # Hip flexion/abduction affects the torso orientation
        # For standing (q=0), spine goes straight up
        # Spine flexion (q[8]) and lateral bend (q[9])
        rot_spine = rotation_x(q[8]) @ rotation_z(q[9])
        spine_vec = rot_spine @ np.array([0.0, 0.0, self.pelvis_height + self.torso_length])
        spine_top = pelvis + spine_vec
        joints["spine_top"] = spine_top

        # ---- Head ----
        head_vec = rot_spine @ np.array([0.0, 0.0, self.head_length])
        head = spine_top + head_vec
        joints["head"] = head

        # ---- Shoulders ----
        half_shoulder = self.shoulder_width / 2.0
        shoulder_offset_l = rot_spine @ np.array([-half_shoulder, 0.0, 0.0])
        shoulder_offset_r = rot_spine @ np.array([half_shoulder, 0.0, 0.0])
        shoulder_l = spine_top + shoulder_offset_l
        shoulder_r = spine_top + shoulder_offset_r
        joints["shoulder_l"] = shoulder_l
        joints["shoulder_r"] = shoulder_r

        # ---- Left arm ----
        rot_sh_l = rot_spine @ rotation_x(q[10]) @ rotation_z(q[11])
        # Arms hang down at rest (negative z)
        ua_vec_l = rot_sh_l @ np.array([0.0, 0.0, -self.upper_arm_length])
        elbow_l = shoulder_l + ua_vec_l
        joints["elbow_l"] = elbow_l

        rot_elbow_l = rot_sh_l @ rotation_x(q[12])
        fa_vec_l = rot_elbow_l @ np.array([0.0, 0.0, -self.forearm_length])
        wrist_l = elbow_l + fa_vec_l
        joints["wrist_l"] = wrist_l

        # ---- Right arm ----
        rot_sh_r = rot_spine @ rotation_x(q[13]) @ rotation_z(q[14])
        ua_vec_r = rot_sh_r @ np.array([0.0, 0.0, -self.upper_arm_length])
        elbow_r = shoulder_r + ua_vec_r
        joints["elbow_r"] = elbow_r

        rot_elbow_r = rot_sh_r @ rotation_x(q[15])
        fa_vec_r = rot_elbow_r @ np.array([0.0, 0.0, -self.forearm_length])
        wrist_r = elbow_r + fa_vec_r
        joints["wrist_r"] = wrist_r

        return joints
