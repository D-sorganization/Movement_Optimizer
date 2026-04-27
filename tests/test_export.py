# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""Tests for export module -- GIF, PNG, PDF export."""

from __future__ import annotations

import matplotlib
import numpy as np
from matplotlib.figure import Figure

matplotlib.use("Agg")

from movement_optimizer.export import (
    export_animation_gif,
    export_plots_pdf,
    export_plots_png,
)


def _make_figure() -> Figure:
    """Create a simple matplotlib figure for testing."""
    fig = Figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 0])
    return fig


class TestExportPNG:
    def test_produces_nonempty_file(self, tmp_path):
        fig = _make_figure()
        path = tmp_path / "test.png"
        export_plots_png(fig, str(path))
        assert path.exists()
        assert path.stat().st_size > 0

    def test_creates_parent_dirs(self, tmp_path):
        fig = _make_figure()
        path = tmp_path / "sub" / "dir" / "test.png"
        export_plots_png(fig, str(path))
        assert path.exists()


class TestExportPDF:
    def test_produces_nonempty_file(self, tmp_path):
        fig = _make_figure()
        path = tmp_path / "test.pdf"
        export_plots_pdf(fig, str(path))
        assert path.exists()
        assert path.stat().st_size > 0


class TestExportGIF:
    def test_produces_nonempty_file(self, tmp_path):
        fig = _make_figure()
        ax = fig.get_axes()[0]
        xs = np.linspace(0, 2 * np.pi, 5)

        def draw_frame(frame_idx: int) -> None:
            ax.clear()
            ax.plot(xs, np.sin(xs + frame_idx * 0.5))

        path = tmp_path / "test.gif"
        export_animation_gif(fig, draw_frame, n_frames=5, path=str(path), fps=5)
        assert path.exists()
        assert path.stat().st_size > 0
