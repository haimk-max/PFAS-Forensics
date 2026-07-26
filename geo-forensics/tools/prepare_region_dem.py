"""prepare_region_dem.py — Offline DEM → derived surface-flow layers.

Heavy-geo-offline principle: this tool runs ONCE per region (needs rasterio
and downloaded DEM tiles); the app only loads the light GeoJSON/JSON outputs
committed under regions/<name>/derived/.

Usage (from geo-forensics/):
    python tools/prepare_region_dem.py hagit /path/to/tile1.tif [tile2.tif ...]

Outputs under regions/<name>/derived/:
    channels.geojson        stream network (WGS84 polylines + accumulation)
    flow_paths.json         per station/source: downstream path (ITM) +
                            pairwise downstream relations with path distances
    dem_meta.json           provenance: tiles, date, resolution, method
"""

import glob as globmod
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import rasterio
from rasterio.merge import merge as rio_merge
from rasterio.warp import Resampling, calculate_default_transform, reproject

from src.dem_engine import (
    _OFFSETS,
    d8_directions,
    flow_accumulation,
    path_length_m,
    priority_flood_fill,
    trace_downstream,
)

CELL_M = 30.0                 # target resolution (m) in EPSG:2039
BBOX_BUFFER_M = 2000.0        # analysis buffer around the region bbox
CHANNEL_MIN_CELLS = 556       # ≥ 0.5 km² drainage (556 cells × 900 m²)
NEAR_PATH_M = 150.0           # a point is "on" a path within this distance


def _load_region(name):
    base = os.path.join(os.path.dirname(__file__), "..", "regions", name)
    with open(os.path.join(base, "region.json"), encoding="utf-8") as f:
        region = json.load(f)
    region["_base"] = base
    return region


def _mosaic_to_itm(tile_paths, bbox_itm):
    """Merge tiles (EPSG:4326) and reproject the buffered bbox to ITM @30m."""
    x0, y0, x1, y1 = bbox_itm
    x0 -= BBOX_BUFFER_M; y0 -= BBOX_BUFFER_M
    x1 += BBOX_BUFFER_M; y1 += BBOX_BUFFER_M

    datasets = [rasterio.open(p) for p in tile_paths]
    mosaic, src_transform = rio_merge(datasets)
    src_crs = datasets[0].crs
    for ds in datasets:
        ds.close()

    width = int(round((x1 - x0) / CELL_M))
    height = int(round((y1 - y0) / CELL_M))
    dst_transform = rasterio.transform.from_origin(x0, y1, CELL_M, CELL_M)
    dst = np.full((height, width), np.nan, dtype=np.float32)
    reproject(
        source=mosaic[0], destination=dst,
        src_transform=src_transform, src_crs=src_crs,
        dst_transform=dst_transform, dst_crs="EPSG:2039",
        resampling=Resampling.bilinear,
        src_nodata=None, dst_nodata=np.nan,
    )
    return dst.astype(float), dst_transform


def _rc_to_itm(transform, r, c):
    x, y = rasterio.transform.xy(transform, r, c)
    return float(x), float(y)


def _itm_to_rc(transform, x, y):
    r, c = rasterio.transform.rowcol(transform, x, y)
    return int(r), int(c)


def _itm_to_wgs(points_itm):
    from pyproj import Transformer
    t = Transformer.from_crs(2039, 4326, always_xy=True)
    return [[round(lon, 6), round(lat, 6)]
            for lon, lat in (t.transform(x, y) for x, y in points_itm)]


def _extract_channels(dirs, acc, transform):
    """Vectorize the channel network: trace from channel heads downstream."""
    channel = acc >= CHANNEL_MIN_CELLS
    rows, cols = channel.shape
    # donors: for each channel cell, count upstream channel neighbors
    donors = np.zeros_like(acc)
    for r in range(rows):
        for c in range(cols):
            if channel[r, c] and dirs[r, c] >= 0:
                dr, dc = _OFFSETS[dirs[r, c]]
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and channel[nr, nc]:
                    donors[nr, nc] += 1
    heads = [(r, c) for r in range(rows) for c in range(cols)
             if channel[r, c] and donors[r, c] == 0]

    features, visited = [], set()
    for hr, hc in heads:
        line, r, c = [(hr, hc)], hr, hc
        while True:
            k = dirs[r, c]
            if k < 0:
                break
            dr, dc = _OFFSETS[k]
            r, c = r + dr, c + dc
            if not (0 <= r < rows and 0 <= c < cols) or not channel[r, c]:
                break
            line.append((r, c))
            if (r, c) in visited:   # merged into an already-traced trunk
                break
            visited.add((r, c))
        if len(line) >= 3:
            itm_pts = [_rc_to_itm(transform, rr, cc) for rr, cc in line]
            features.append({
                "type": "Feature",
                "geometry": {"type": "LineString",
                             "coordinates": _itm_to_wgs(itm_pts)},
                "properties": {"max_acc_cells": int(acc[line[-1]])},
            })
    return features


def main(region_name, tile_paths):
    region = _load_region(region_name)
    bbox = region["bbox_itm"]
    print(f"region={region_name}  bbox={bbox}  tiles={len(tile_paths)}")

    dem, transform = _mosaic_to_itm(tile_paths, bbox)
    print(f"DEM grid: {dem.shape}, elev range "
          f"{np.nanmin(dem):.0f}..{np.nanmax(dem):.0f} m")

    filled = priority_flood_fill(dem)
    dirs = d8_directions(filled)
    acc = flow_accumulation(filled, dirs)
    print(f"filled + D8 + accumulation done; max acc={acc.max()} cells")

    # --- channels ---
    chan_features = _extract_channels(dirs, acc, transform)
    print(f"channels: {len(chan_features)} polylines "
          f"(threshold {CHANNEL_MIN_CELLS} cells ≈ {CHANNEL_MIN_CELLS*900/1e6:.1f} km²)")

    # --- points: stations from measurement file + declared sources ---
    import warnings; warnings.filterwarnings("ignore")
    from src.data_model import calc_total_concentration, process_file
    from src.contaminant_groups import get_group

    mf = os.path.join(os.path.dirname(__file__), "..", region["measurement_file"])
    df, group = process_file(mf, group_name="PFAS")
    tot = calc_total_concentration(df, group)
    me = tot.loc[tot.groupby("station_name")["total_concentration"].idxmax()]
    points = {}
    for _, row in me.iterrows():
        if not (np.isnan(row["x_itm"]) or np.isnan(row["y_itm"])):
            points[row["station_name"]] = {
                "kind": "station", "itm": [float(row["x_itm"]), float(row["y_itm"])],
                "source_type": str(row.get("source_type", "")),
            }
    with open(os.path.join(region["_base"], "sources.geojson"), encoding="utf-8") as f:
        for feat in json.load(f)["features"]:
            p = feat["properties"]
            points[p["id"]] = {"kind": "candidate_source",
                               "itm": [float(v) for v in p["itm"]],
                               "source_type": p.get("kind", "")}

    # --- downstream path per point ---
    paths = {}
    for name, meta in points.items():
        r, c = _itm_to_rc(transform, *meta["itm"])
        if not (0 <= r < dem.shape[0] and 0 <= c < dem.shape[1]):
            continue
        cells = trace_downstream(dirs, r, c)
        itm_pts = [_rc_to_itm(transform, rr, cc) for rr, cc in cells]
        paths[name] = {**meta, "path_itm": [[round(x, 1), round(y, 1)] for x, y in itm_pts],
                       "path_len_m": round(path_length_m(cells, CELL_M), 1)}

    # --- pairwise relations: A→B if B sits near A's downstream path ---
    relations = []
    names = list(paths)
    for a in names:
        pa = np.array(paths[a]["path_itm"], dtype=float)
        cum = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(pa, axis=0).T))]) \
            if len(pa) > 1 else np.array([0.0])
        for b in names:
            if a == b:
                continue
            bx, by = paths[b]["itm"]
            d2 = np.hypot(pa[:, 0] - bx, pa[:, 1] - by)
            i = int(np.argmin(d2))
            if d2[i] <= NEAR_PATH_M and cum[i] > 0:
                relations.append({"from": a, "to": b,
                                  "path_distance_m": round(float(cum[i]), 1),
                                  "offset_m": round(float(d2[i]), 1)})
    print(f"points with paths: {len(paths)}; downstream relations: {len(relations)}")

    # --- write outputs ---
    out = os.path.join(region["_base"], "derived")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "channels.geojson"), "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": chan_features}, f,
                  ensure_ascii=False)
    with open(os.path.join(out, "flow_paths.json"), "w", encoding="utf-8") as f:
        json.dump({"cell_m": CELL_M, "near_path_m": NEAR_PATH_M,
                   "points": paths, "relations": relations}, f, ensure_ascii=False)
    from datetime import date
    with open(os.path.join(out, "dem_meta.json"), "w", encoding="utf-8") as f:
        json.dump({
            "source": "Copernicus GLO-30 DSM (AWS Open Data)",
            "tiles": [os.path.basename(p) for p in tile_paths],
            "prepared_on": str(date.today()),
            "resolution_m": CELL_M,
            "method": "priority-flood fill + D8 + accumulation (src/dem_engine.py)",
            "channel_threshold_km2": CHANNEL_MIN_CELLS * 900 / 1e6,
            "quality": "derived_dem",
            "notes_he": "נגזרת עילית בלבד; DSM כולל צמחייה/מבנים — ערוצים אזוריים אמינים, מיקרו-ניקוז לא.",
        }, f, ensure_ascii=False, indent=2)
    print(f"outputs written to {out}")


if __name__ == "__main__":
    name = sys.argv[1]
    tiles = []
    for arg in sys.argv[2:]:
        tiles.extend(sorted(globmod.glob(arg)) or [arg])
    main(name, tiles)
