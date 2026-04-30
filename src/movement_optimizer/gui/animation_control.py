# Copyright (c) 2026 D-Sorganization. All rights reserved.
# mypy: disable-error-code="misc,has-type,override"
# Mixin pattern: methods annotate self as MainWindow to access its attributes,
# but mypy cannot verify this pattern without the concrete class in scope.
# ``override`` is suppressed because mypy treats ``self: MainWindow`` as an
# incompatible self-type override for the mixin -- this is intentional.
"""Animation playback helpers extracted from MainWindow.

Provides play/pause toggle, step forward/back, rewind, and frame
advance as a mixin class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main_window import MainWindow


class AnimationControlMixin:
    """Mixin providing animation playback for MainWindow."""

    def _toggle_play(self: MainWindow) -> None:
        idx = self.tabs.currentIndex()
        if self.results[idx] is None:
            return
        if self.is_playing:
            self._stop_anim()
        else:
            self.is_playing = True
            self.controls.set_playing(True)
            self._anim_step()

    def _stop_anim(self: MainWindow) -> None:
        self.is_playing = False
        self.anim_timer.stop()
        self.controls.set_playing(False)

    def _anim_step(self: MainWindow) -> None:
        if not self.is_playing:
            return
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return

        fi = self.anim_frames[idx]
        _, etype = self.EXERCISE_CONFIGS[idx]
        body = self.bodies_list[idx]
        if body is None:
            raise ValueError("DbC Blocked: Precondition failed.")
        self.exercise_tabs[idx].draw_anim_frame(
            fi,
            r,
            self.dynamics_list[idx],
            body,
            etype,
        )

        n = len(r.t)
        self.anim_frames[idx] = (fi + 1) % n
        speed = self.controls.speed_multiplier()
        self.controls.set_playback_status(fi + 1, n, speed)
        delay = max(15, int(40 / max(0.1, speed)))
        if self.anim_frames[idx] == 0:
            delay = 700
        self.anim_timer.start(delay)

    def _step_fwd(self: MainWindow) -> None:
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return
        self._stop_anim()
        n = len(r.t)
        self.anim_frames[idx] = (self.anim_frames[idx] + 1) % n
        _, etype = self.EXERCISE_CONFIGS[idx]
        self.exercise_tabs[idx].draw_anim_frame(
            self.anim_frames[idx],
            r,
            self.dynamics_list[idx],
            self.bodies_list[idx],  # type: ignore[arg-type]  # bodies_list[idx] is BodyModel|None; None is guarded: r is None returns early before body is used
            etype,
        )
        self.controls.set_playback_status(
            self.anim_frames[idx] + 1,
            n,
            self.controls.speed_multiplier(),
        )

    def _step_back(self: MainWindow) -> None:
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return
        self._stop_anim()
        n = len(r.t)
        self.anim_frames[idx] = (self.anim_frames[idx] - 1) % n
        _, etype = self.EXERCISE_CONFIGS[idx]
        self.exercise_tabs[idx].draw_anim_frame(
            self.anim_frames[idx],
            r,
            self.dynamics_list[idx],
            self.bodies_list[idx],  # type: ignore[arg-type]  # bodies_list[idx] is BodyModel|None; None is guarded: r is None returns early before body is used
            etype,
        )

    def _rewind(self: MainWindow) -> None:
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return
        self._stop_anim()
        self.anim_frames[idx] = 0
        _, etype = self.EXERCISE_CONFIGS[idx]
        self.exercise_tabs[idx].draw_anim_frame(
            0,
            r,
            self.dynamics_list[idx],
            self.bodies_list[idx],  # type: ignore[arg-type]  # bodies_list[idx] is BodyModel|None; None is guarded: r is None returns early before body is used
            etype,
        )

    def _jump_to_end(self: MainWindow) -> None:
        idx = self.tabs.currentIndex()
        r = self.results[idx]
        if r is None:
            return
        self._stop_anim()
        n = len(r.t)
        last_frame = n - 1
        self.anim_frames[idx] = last_frame
        _, etype = self.EXERCISE_CONFIGS[idx]
        self.exercise_tabs[idx].draw_anim_frame(
            last_frame,
            r,
            self.dynamics_list[idx],
            self.bodies_list[idx],  # type: ignore[arg-type]  # bodies_list[idx] is BodyModel|None; None is guarded: r is None returns early before body is used
            etype,
        )
        self.controls.set_playback_status(
            last_frame + 1,
            n,
            self.controls.speed_multiplier(),
        )

    def _on_speed(self: MainWindow, speed: float) -> None:
        self.controls.set_speed_multiplier_text(speed)
