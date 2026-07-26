"""Tests for the pure-numpy D8 engine on toy DEMs with known answers."""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.dem_engine import (
    d8_directions,
    flow_accumulation,
    path_length_m,
    priority_flood_fill,
    trace_downstream,
)


def _valley_dem(n=20):
    """Tilted valley: elevation rises away from the center column and toward
    the top row → water collects in the center column and flows to the last
    row. The channel is column n//2."""
    dem = np.zeros((n, n))
    for r in range(n):
        for c in range(n):
            dem[r, c] = (n - r) * 1.0 + abs(c - n // 2) * 2.0
    return dem


class TestD8Engine:
    def test_valley_channel_accumulates(self):
        dem = _valley_dem()
        filled = priority_flood_fill(dem)
        dirs = d8_directions(filled)
        acc = flow_accumulation(filled, dirs)
        mid = dem.shape[1] // 2
        # the valley bottom near the outlet gathers far more flow than slopes
        assert acc[-2, mid] > 10 * acc[-2, mid - 4]

    def test_downstream_trace_reaches_outlet_row(self):
        dem = _valley_dem()
        filled = priority_flood_fill(dem)
        dirs = d8_directions(filled)
        mid = dem.shape[1] // 2
        path = trace_downstream(dirs, 2, mid - 3)
        rows = [p[0] for p in path]
        cols = [p[1] for p in path]
        assert rows[-1] >= dem.shape[0] - 2      # reached the low edge
        assert abs(cols[-1] - mid) <= 1          # via the valley bottom

    def test_depression_is_filled_and_drains(self):
        dem = _valley_dem()
        dem[10, 10] = -50.0                      # artificial pit in the slope
        filled = priority_flood_fill(dem)
        dirs = d8_directions(filled)
        assert filled[10, 10] > -50.0            # pit raised
        path = trace_downstream(dirs, 10, 10)
        assert path[-1][0] >= dem.shape[0] - 2   # and it drains to the edge

    def test_path_length_diagonal_vs_straight(self):
        straight = [(0, 0), (1, 0), (2, 0)]
        diagonal = [(0, 0), (1, 1), (2, 2)]
        assert path_length_m(straight, 30.0) == 60.0
        assert abs(path_length_m(diagonal, 30.0) - 60.0 * 1.41421356) < 1e-6

    def test_path_distance_exceeds_aerial_in_bent_valley(self):
        """An L-shaped valley: flow path is longer than straight-line distance."""
        n = 30
        dem = np.full((n, n), 100.0)
        # horizontal reach: row 5, cols 5..25 descending toward col 25
        for c in range(5, 26):
            dem[5, c] = 50.0 - c * 0.5
        # vertical reach: col 25, rows 5..29 descending toward last row
        for r in range(5, n):
            dem[r, 25] = 50.0 - 25 * 0.5 - (r - 5) * 1.0
        filled = priority_flood_fill(dem)
        dirs = d8_directions(filled)
        path = trace_downstream(dirs, 5, 5)
        plen = path_length_m(path, 30.0)
        aerial = 30.0 * np.hypot(path[-1][0] - 5, path[-1][1] - 5)
        assert plen > aerial * 1.15              # bent path is meaningfully longer
