"""dem_engine.py — Pure-numpy D8 surface-flow engine.

Priority-flood depression filling, D8 flow directions, flow accumulation and
downstream tracing. No GIS dependencies — operates on plain 2D arrays so it
is unit-testable on toy DEMs; rasterio IO lives in tools/prepare_region_dem.py.

Conventions: row 0 is the array's first row; the caller owns georeferencing.
Cells drain to the lowest of their 8 neighbors (steepest descent on the
FILLED surface). Direction encoding: index 0..7 into _OFFSETS, -1 = outlet
(drains off-grid or undefined).
"""

import heapq

import numpy as np

_OFFSETS = [(-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1)]
# Distance factor per direction (diagonal = sqrt(2)), multiplied by cell size.
_DIST = np.array([1.41421356, 1.0, 1.41421356,
                  1.0,              1.0,
                  1.41421356, 1.0, 1.41421356])

_EPS = 1e-4  # epsilon-gradient applied while filling, resolves flats


def priority_flood_fill(dem: np.ndarray) -> np.ndarray:
    """Fill depressions so every cell drains to the grid edge.

    Barnes et al. (2014) priority-flood with an epsilon gradient: cells are
    raised to (spill elevation + eps) so filled areas still drain outward.
    NaNs are treated as nodata and left untouched.
    """
    rows, cols = dem.shape
    filled = dem.astype(float).copy()
    closed = np.zeros(dem.shape, dtype=bool)
    heap = []

    valid = ~np.isnan(filled)
    # Seed: all edge cells (and cells adjacent to nodata act as drains too)
    for r in range(rows):
        for c in range(cols):
            if not valid[r, c]:
                closed[r, c] = True
                continue
            on_edge = r in (0, rows - 1) or c in (0, cols - 1)
            if not on_edge:
                on_edge = any(
                    not (0 <= r + dr < rows and 0 <= c + dc < cols)
                    or not valid[r + dr, c + dc]
                    for dr, dc in _OFFSETS)
            if on_edge:
                heapq.heappush(heap, (filled[r, c], r, c))
                closed[r, c] = True

    while heap:
        elev, r, c = heapq.heappop(heap)
        for dr, dc in _OFFSETS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not closed[nr, nc]:
                closed[nr, nc] = True
                filled[nr, nc] = max(filled[nr, nc], elev + _EPS)
                heapq.heappush(heap, (filled[nr, nc], nr, nc))
    return filled


def d8_directions(filled: np.ndarray) -> np.ndarray:
    """Steepest-descent D8 direction per cell (index into _OFFSETS; -1=outlet)."""
    rows, cols = filled.shape
    dirs = np.full(filled.shape, -1, dtype=np.int8)
    for r in range(rows):
        for c in range(cols):
            if np.isnan(filled[r, c]):
                continue
            best_drop, best_k = 0.0, -1
            for k, (dr, dc) in enumerate(_OFFSETS):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < rows and 0 <= nc < cols):
                    continue
                if np.isnan(filled[nr, nc]):
                    # neighbor is nodata → acts as a drain (e.g., the sea)
                    drop = np.inf
                else:
                    drop = (filled[r, c] - filled[nr, nc]) / _DIST[k]
                if drop > best_drop:
                    best_drop, best_k = drop, k
            # cells with no downhill neighbor keep -1 (edge outlets)
            if best_k >= 0 and best_drop > 0:
                dirs[r, c] = best_k
    return dirs


def flow_accumulation(filled: np.ndarray, dirs: np.ndarray) -> np.ndarray:
    """Number of upstream cells draining through each cell (incl. itself).

    Cells are processed from highest to lowest filled elevation, so every
    donor is added before its receiver is visited.
    """
    rows, cols = filled.shape
    acc = np.ones(filled.shape, dtype=np.int64)
    acc[np.isnan(filled)] = 0
    order = np.argsort(filled, axis=None, kind="stable")[::-1]
    for idx in order:
        r, c = divmod(idx, cols)
        k = dirs[r, c]
        if k < 0 or np.isnan(filled[r, c]):
            continue
        dr, dc = _OFFSETS[k]
        acc[r + dr, c + dc] += acc[r, c]
    return acc


def trace_downstream(dirs: np.ndarray, row: int, col: int,
                     max_steps: int | None = None) -> list[tuple[int, int]]:
    """Follow D8 directions from (row, col) to the outlet. Returns cell list
    including the start. Guards against cycles (shouldn't exist post-fill)."""
    rows, cols = dirs.shape
    if max_steps is None:
        max_steps = rows * cols
    path = [(row, col)]
    seen = {(row, col)}
    r, c = row, col
    for _ in range(max_steps):
        k = dirs[r, c]
        if k < 0:
            break
        dr, dc = _OFFSETS[k]
        r, c = r + dr, c + dc
        if not (0 <= r < rows and 0 <= c < cols) or (r, c) in seen:
            break
        path.append((r, c))
        seen.add((r, c))
    return path


def path_length_m(path: list[tuple[int, int]], cell_size_m: float) -> float:
    """Cumulative along-path distance in meters."""
    total = 0.0
    for (r0, c0), (r1, c1) in zip(path, path[1:]):
        total += cell_size_m * (1.41421356 if (r0 != r1 and c0 != c1) else 1.0)
    return total
