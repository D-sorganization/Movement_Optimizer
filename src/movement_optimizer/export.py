# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""Export helpers for animation GIFs and plot images.

Design Principles:
    DBC  -- preconditions checked at function entry.
    DRY  -- common save logic factored into each function.
    LoD  -- callers pass only figure + path, no internal state.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable

from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.figure import Figure

logger = logging.getLogger(__name__)


def export_animation_gif(
    fig: Figure,
    draw_frame_fn: Callable[[int], None],
    n_frames: int,
    path: str,
    fps: int = 15,
) -> None:
    """Export a matplotlib animation as a GIF file.

    Args:
        fig: Matplotlib Figure to animate.
        draw_frame_fn: Callable that redraws the figure for a given frame index.
        n_frames: Total number of animation frames (must be > 0).
        path: Output file path (should end in ``.gif``).
        fps: Frames per second for playback (default 15).

    Raises:
        ValueError: If n_frames <= 0 or fps <= 0.
    """
    if n_frames <= 0:
        raise ValueError(f"n_frames must be positive, got {n_frames}")
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps}")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    anim = FuncAnimation(fig, draw_frame_fn, frames=n_frames, blit=False)  # type: ignore[arg-type]
    writer = PillowWriter(fps=fps)
    anim.save(path, writer=writer)  # type: ignore[arg-type]
    logger.info("Exported GIF animation to %s (%d frames, %d fps)", path, n_frames, fps)


def export_plots_png(fig: Figure, path: str) -> None:
    """Export a matplotlib figure as a PNG image.

    Preconditions:
        fig is a valid matplotlib Figure.
        path is a writable file path.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fig.savefig(path, format="png", dpi=150, bbox_inches="tight")
    logger.info("Exported PNG to %s", path)


def export_plots_pdf(fig: Figure, path: str) -> None:
    """Export a matplotlib figure as a PDF file.

    Preconditions:
        fig is a valid matplotlib Figure.
        path is a writable file path.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fig.savefig(path, format="pdf", bbox_inches="tight")
    logger.info("Exported PDF to %s", path)
