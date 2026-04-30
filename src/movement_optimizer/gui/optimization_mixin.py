# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""Mixin for optimization controller logic in the Movement Optimizer GUI."""

from __future__ import annotations

import logging
import threading
import traceback
from collections.abc import Callable
from typing import Any

import numpy as np

from ..cli import EXERCISE_FACTORIES
from ..constants import trapezoid
from ..models import BodyModel
from ..trajectory import (
    CancelledError,
    OptimizationResult,
    ProgressReport,
    SolutionCache,
    TrajectoryOptimizer,
)

logger = logging.getLogger(__name__)


class OptimizationMixin:
    """Contains logic for preparing and running optimization backgrounds tasks."""

    # These attributes are expected to be present on the MainWindow instance.
    # ``_opt_lock`` is an RLock so the same thread may re-enter critical
    # sections (e.g. a locked helper calling another locked helper) without
    # deadlocking. All writes to ``results``/``anim_frames``/``bodies_list``/
    # ``dynamics_list`` (and corresponding cross-thread reads) must hold this
    # lock to prevent torn updates between the worker thread and the GUI
    # main thread.
    _opt_lock: threading.RLock
    _opt_running: bool
    _cache: SolutionCache
    _cancel_event: threading.Event
    results: list[OptimizationResult | None]
    dynamics_list: list[Any]
    bodies_list: list[BodyModel | None]
    anim_frames: list[int]
    EXERCISE_CONFIGS: tuple[tuple[str, str], ...]
    _last_config: tuple[Any, ...]

    def __init__(self) -> None:
        """Init."""
        pass

    def _snapshot_idx_state(
        self, idx: int
    ) -> tuple[OptimizationResult | None, int, BodyModel | None, Any]:
        """Return a consistent snapshot of (result, anim_frame, body, dyn) for ``idx``.

        Acquires ``_opt_lock`` briefly to copy the four shared per-index values
        out so callers can work with the snapshot outside the critical section,
        avoiding torn reads while the worker thread is publishing a new result.
        """
        with self._opt_lock:
            return (
                self.results[idx],
                self.anim_frames[idx],
                self.bodies_list[idx],
                self.dynamics_list[idx],
            )

    def _set_anim_frame(self, idx: int, frame: int) -> None:
        """Atomically write ``anim_frames[idx]`` under the optimizer lock."""
        with self._opt_lock:
            self.anim_frames[idx] = frame

    def _resolve_exercise_params(self, idx: int) -> tuple[Any, Any, str, float, float, float]:
        body = self.sidebar.get_body_model()  # type: ignore[attr-defined]
        bar, dur, smoothness = self.sidebar.get_optimization_params()  # type: ignore[attr-defined]
        _, etype = self.EXERCISE_CONFIGS[idx]

        factory = EXERCISE_FACTORIES[etype]
        config = factory(body, bar)
        if len(config) == 5:
            dyn, qs, qe, qb, q_via = config  # type: ignore[misc]
        else:
            dyn, qs, qe, qb = config  # type: ignore[misc]
            q_via = None

        _min_durations = {
            "full_squat": 3.0,
            "bench_press": 3.0,
            "clean": 2.5,
            "jerk": 2.0,
            "snatch": 3.0,
        }
        if etype in _min_durations:
            dur = max(dur, _min_durations[etype])

        with self._opt_lock:
            self.dynamics_list[idx] = dyn
            self.bodies_list[idx] = body
            self._last_config = (dyn, qs, qe, qb, q_via, etype)
        return body, dyn, etype, bar, dur, smoothness

    def _seg_mults(self) -> dict[str, float]:
        return self.sidebar.get_segment_multipliers()  # type: ignore[attr-defined]

    def _run_optimizer(
        self,
        body: Any,
        bar: float,
        dur: float,
        smoothness: float,
    ) -> OptimizationResult:
        dyn, qs, qe, qb, q_via, etype = self._last_config
        logger.info(
            "Starting %s optimisation: mass=%.0f, height=%.2f, bar=%.0f",
            etype,
            body.body_mass,
            body.height,
            bar,
        )
        opt = TrajectoryOptimizer(
            body,
            dyn,  # type: ignore[arg-type]
            etype,
            bar,
            qs,  # type: ignore[arg-type]
            qe,  # type: ignore[arg-type]
            qb,  # type: ignore[arg-type]
            q_via=q_via,  # type: ignore[arg-type]
            duration=dur,
            n_waypoints=12,
            smoothness=smoothness,
            progress_cb=self._make_progress_cb(),
            cancel_event=self._cancel_event,
        )
        return opt.optimize()

    def _opt_worker(self, idx: int, then_chain: list[int] | None) -> None:
        try:
            body, _dyn, etype, bar, dur, smoothness = self._resolve_exercise_params(idx)
            seg_mults = self._seg_mults()

            b_depth = getattr(body, "squat_bar_depth", 0.0)
            b_height = getattr(body, "squat_bar_height", 0.0)
            cached = self._cache.get(
                etype,
                body.body_mass,
                body.height,
                seg_mults,
                bar,
                dur,
                smoothness,
                b_depth,
                b_height,
            )
            if cached is not None:
                logger.info("Cache hit for %s", etype)
                with self._opt_lock:
                    self.results[idx] = cached
                    self.anim_frames[idx] = 0
                self._sig_done.emit(idx, cached, body, bar, then_chain)  # type: ignore[attr-defined]
                return

            result = self._run_optimizer(body, bar, dur, smoothness)
            with self._opt_lock:
                self.results[idx] = result
                self.anim_frames[idx] = 0

            self._cache.put(
                etype,
                body.body_mass,
                body.height,
                seg_mults,
                bar,
                dur,
                smoothness,
                result,
                b_depth,
                b_height,
            )
            self._sig_done.emit(idx, result, body, bar, then_chain)  # type: ignore[attr-defined]
        except CancelledError:
            self._sig_cancelled.emit()  # type: ignore[attr-defined]
        except NotImplementedError as exc:
            tb = traceback.format_exc()
            logger.error("Optimisation failed (feature not implemented):\\n%s", tb)
            self._sig_error.emit(f"Feature not yet implemented: {exc}")  # type: ignore[attr-defined]
        except (ValueError, RuntimeError, OSError, np.linalg.LinAlgError) as exc:
            tb = traceback.format_exc()
            logger.error("Optimisation failed:\\n%s", tb)
            self._sig_error.emit(str(exc))  # type: ignore[attr-defined]

    def _make_progress_cb(self) -> Callable[[ProgressReport], None]:
        def cb(report: ProgressReport) -> None:
            logger.debug(
                "iter=%d cost=%.3f best=%.3f improve=%+.3f%% elapsed=%.1fs",
                report.iteration,
                report.cost,
                report.best_cost,
                report.improvement_pct,
                report.elapsed_s,
            )
            self._sig_progress.emit(report)  # type: ignore[attr-defined]

        return cb

    def _update_progress(self, report: ProgressReport) -> None:
        self.sidebar.update_progress(report)  # type: ignore[attr-defined]

    def _on_done(
        self,
        idx: int,
        result: OptimizationResult,
        body: BodyModel,
        bar: float,
        then_chain: list[int] | None,
    ) -> None:
        """Handle successful optimization completion (called from main thread via signal)."""
        try:
            name = self.EXERCISE_CONFIGS[idx][0]  # type: ignore[attr-defined]
            _, etype = self.EXERCISE_CONFIGS[idx]  # type: ignore[attr-defined]
            self._update_result_summary(name, result, exercise_type=etype)
            tab = self.exercise_tabs[idx]  # type: ignore[attr-defined]
            tab.draw_all_plots(result, body, bar, exercise_type=etype)
            with self._opt_lock:  # type: ignore[attr-defined]
                dyn = self.dynamics_list[idx]
            tab.draw_anim_frame(0, result, dyn, body, etype)  # type: ignore[attr-defined]
            elapsed = result.elapsed_s
            t_str = (
                f"{elapsed:.1f}s" if elapsed < 60 else f"{int(elapsed // 60)}m {elapsed % 60:.0f}s"
            )
            self.sidebar.set_progress_done(t_str, result.n_evals)  # type: ignore[attr-defined]
            self._enable_post_run_buttons()
            if result.success:
                self.sidebar.clear_stall_message()  # type: ignore[attr-defined]
                status_msg = f"{name} optimization complete in {t_str}!"
            else:
                self.sidebar.set_stall_message(  # type: ignore[attr-defined]
                    "\u26a0 COM went outside the inner 60% BOS zone. "
                    "Try increasing smoothness or adjusting body parameters."
                )
                status_msg = f"{name} done in {t_str} -- WARNING: COM balance violated"
            self._finish_or_chain(then_chain, status_msg)
        except (ValueError, RuntimeError, OSError, AttributeError) as exc:
            with self._opt_lock:  # type: ignore[attr-defined]
                self._opt_running = False  # type: ignore[attr-defined]
            tb = traceback.format_exc()
            logger.error("Error in _on_done:\n%s", tb)
            self.sidebar.show_idle()  # type: ignore[attr-defined]
            self.status_label.setText(f"Render error: {exc}")  # type: ignore[attr-defined]

    def _enable_post_run_buttons(self) -> None:
        """Enable export/save/compare buttons after a successful optimization run."""
        self.sidebar.enable_post_run_buttons()  # type: ignore[attr-defined]

    def _finish_or_chain(self, then_chain: list[int] | None, status_msg: str) -> None:
        """Either chain to the next exercise or finalize the run."""
        if then_chain:
            next_idx = then_chain[0]
            remaining = then_chain[1:] if len(then_chain) > 1 else None
            self._run_exercise(next_idx, remaining)  # type: ignore[attr-defined]
        else:
            with self._opt_lock:  # type: ignore[attr-defined]
                self._opt_running = False  # type: ignore[attr-defined]
            self.sidebar.show_idle()  # type: ignore[attr-defined]
            self.status_label.setText(status_msg)  # type: ignore[attr-defined]

    def _on_cancelled(self) -> None:
        """Handle user-requested cancellation (called from main thread via signal)."""
        with self._opt_lock:  # type: ignore[attr-defined]
            self._opt_running = False  # type: ignore[attr-defined]
        self.sidebar.show_idle()  # type: ignore[attr-defined]
        self.sidebar.set_cancelled()  # type: ignore[attr-defined]
        self.status_label.setText("Optimization cancelled by user.")  # type: ignore[attr-defined]

    def _update_result_summary(
        self, name: str, r: OptimizationResult, exercise_type: str = "squat"
    ) -> None:
        """Build and display the results summary in the sidebar."""
        pk = np.max(np.abs(r.torques), axis=0)
        work = trapezoid(np.sum(np.abs(r.power), axis=1), r.t)
        if exercise_type == "bench_press":
            joint_lines = (
                f"  Shoulder: {pk[0]:>6.0f} N\u00b7m\n"
                f"  Elbow:    {pk[1]:>6.0f} N\u00b7m\n"
                f"  Wrist:    {pk[2]:>6.0f} N\u00b7m"
            )
        else:
            balance_ok = "BALANCED" if r.success else "OUT OF BOUNDS"
            joint_lines = (
                f"  Ankle: {pk[0]:>6.0f} N\u00b7m\n"
                f"  Knee:  {pk[1]:>6.0f} N\u00b7m\n"
                f"  Hip:   {pk[2]:>6.0f} N\u00b7m\n"
                f"  COM sway: {r.com_horizontal_range_cm:.1f} cm\n"
                f"  Balance: {balance_ok}"
            )
        self.sidebar.set_result_label(  # type: ignore[attr-defined]
            f"{name} results:\n{joint_lines}\n  Work: {work:>6.0f} J"
        )

    def _on_err(self, msg: str) -> None:
        """Handle optimizer errors (called from main thread via signal)."""
        from PyQt6.QtWidgets import QMessageBox

        self._opt_running = False  # type: ignore[attr-defined]
        self.sidebar.show_idle()  # type: ignore[attr-defined]
        self.status_label.setText(f"Error: {msg}")  # type: ignore[attr-defined]
        QMessageBox.critical(self, "Error", msg)  # type: ignore[arg-type]

    def _reset(self) -> None:
        """Reset to defaults and clear the solution cache."""
        self._stop_anim()  # type: ignore[attr-defined]
        self.sidebar.reset_defaults()  # type: ignore[attr-defined]
        self._cache.clear()  # type: ignore[attr-defined]
        self.status_label.setText("Defaults restored. Cache cleared.")  # type: ignore[attr-defined]
