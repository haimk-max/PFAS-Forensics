"""prepare_region_hillshade.py — Offline DEM → shaded-relief backdrop.

One-time step (like prepare_region_dem): renders a grayscale hillshade of
the region bbox from the Copernicus tiles and commits it under
regions/<name>/derived/, so the case-report map can embed it as a
self-contained background image (no tiles, no network at view time).

Usage (from geo-forensics/):
    python tools/prepare_region_hillshade.py <region> <tile.tif> [<tile.tif> ...]

Outputs under regions/<name>/derived/:
    hillshade.png        — grayscale shaded relief, cropped to the bbox
    hillshade_meta.json  — ITM bbox of the image + rendering parameters
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prepare_region_dem import _load_region, _mosaic_to_itm, BBOX_BUFFER_M, CELL_M  # noqa: E402


def hillshade(z, cell_m, azimuth_deg=315.0, altitude_deg=45.0):
    """Standard Horn hillshade, values in [0, 1]."""
    az = np.radians(360.0 - azimuth_deg + 90.0)
    alt = np.radians(altitude_deg)
    gy, gx = np.gradient(z, cell_m)
    slope = np.pi / 2.0 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    shaded = (np.sin(alt) * np.sin(slope)
              + np.cos(alt) * np.cos(slope) * np.cos(az - aspect))
    return np.clip(shaded, 0, 1)


def main(region_name, tile_paths):
    region = _load_region(region_name)
    bbox = region["bbox_itm"]
    dem, transform = _mosaic_to_itm(tile_paths, bbox)
    dem = np.nan_to_num(dem, nan=float(np.nanmedian(dem)))

    hs = hillshade(dem, CELL_M)
    # crop the analysis buffer so the image aligns exactly with the bbox
    buf = int(round(BBOX_BUFFER_M / CELL_M))
    hs = hs[buf:-buf or None, buf:-buf or None]

    # soft contrast: keep it a backdrop, not a poster
    hs = 0.55 + 0.45 * hs          # lift shadows
    img = (np.clip(hs, 0, 1) * 255).astype(np.uint8)

    out_dir = os.path.join(region["_base"], "derived")
    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, "hillshade.png")
    try:
        from PIL import Image
        Image.fromarray(img, mode="L").save(png_path, optimize=True)
    except ImportError:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.imsave(png_path, img, cmap="gray", vmin=0, vmax=255)

    meta = {
        "bbox_itm": bbox,
        "azimuth_deg": 315.0, "altitude_deg": 45.0,
        "cell_m": CELL_M,
        "source": "Copernicus GLO-30 DSM (AWS Open Data)",
        "quality": "derived_dem",
        "notes_he": "רקע-תבליט לקריאות המפה בלבד — אינו שכבת-ראיה.",
    }
    with open(os.path.join(out_dir, "hillshade_meta.json"), "w",
              encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"wrote {png_path} ({os.path.getsize(png_path) // 1024} KB, "
          f"{img.shape[1]}x{img.shape[0]} px)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: prepare_region_hillshade.py <region> <tile.tif> ...")
    main(sys.argv[1], sys.argv[2:])
