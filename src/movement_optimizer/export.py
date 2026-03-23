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

    Preconditions:
        fig is a valid matplotlib Figure.
        draw_frame_fn(frame_idx) redraws the figure for the given frame.
        n_frames > 0.
        path is a writable file path ending in .gif.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    anim = FuncAnimation(fig, draw_frame_fn, frames=n_frames, blit=False)
    writer = PillowWriter(fps=fps)
    anim.save(path, writer=writer)
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
