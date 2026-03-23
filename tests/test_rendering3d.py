"""Tests for movement_optimizer.three_d.rendering3d -- 3D body renderer."""

from __future__ import annotations

import numpy as np

from movement_optimizer.three_d.rendering3d import Renderer3D


class TestRenderer3D:
    def test_construction(self):
        r = Renderer3D()
        assert r is not None

    def test_draw_segment_no_crash(self):
        """Drawing a cylinder segment should not raise."""
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib.figure import Figure

        fig = Figure()
        ax = fig.add_subplot(111, projection="3d")
        r = Renderer3D()
        r.draw_segment(ax, np.array([0, 0, 0]), np.array([0, 0, 1]), radius=0.05, color="blue")

    def test_draw_joint_no_crash(self):
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib.figure import Figure

        fig = Figure()
        ax = fig.add_subplot(111, projection="3d")
        r = Renderer3D()
        r.draw_joint(ax, np.array([0, 0, 0.5]), radius=0.03, color="red")

    def test_draw_ground_plane_no_crash(self):
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib.figure import Figure

        fig = Figure()
        ax = fig.add_subplot(111, projection="3d")
        r = Renderer3D()
        r.draw_ground_plane(ax, size=1.0)

    def test_draw_barbell_no_crash(self):
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib.figure import Figure

        fig = Figure()
        ax = fig.add_subplot(111, projection="3d")
        r = Renderer3D()
        r.draw_barbell(ax, np.array([0, 0, 1.5]), bar_length=2.2)
