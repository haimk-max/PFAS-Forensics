"""prepare_region_basemap.py — Offline satellite backdrop for the case map.

One-time step (like prepare_region_dem / _hillshade): builds a true-colour
Sentinel-2 image of the region bbox and commits it under
regions/<name>/derived/, so the case report can embed it as a self-contained
backdrop. No tile server is involved at view time — an Artifact page cannot
reach one.

Imagery: Copernicus Sentinel-2 L2A COGs on AWS Open Data (public bucket
`sentinel-cogs`, anonymous access). Free to use with attribution
("Contains modified Copernicus Sentinel data").

Usage (from geo-forensics/):
    python tools/prepare_region_basemap.py <region> [--res 15] [--max-cloud 5]
                                           [--months 2025-08 2025-07 ...]

Outputs under regions/<name>/derived/:
    basemap.jpg        — true-colour image, exactly the region bbox in ITM
    basemap_meta.json  — bbox, scenes used (id, date, cloud), attribution
"""

import argparse
import io
import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")

import rasterio  # noqa: E402
from rasterio.warp import Resampling, reproject  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402

from prepare_region_dem import _load_region  # noqa: E402

BUCKET = "https://sentinel-cogs.s3.us-west-2.amazonaws.com"
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
UTM_EPSG = 32636          # UTM 36N — covers Israel
ITM_EPSG = 2039


def _list_prefixes(prefix, max_keys=400):
    url = (f"{BUCKET}/?list-type=2&delimiter=/"
           f"&prefix={urllib.parse.quote(prefix)}&max-keys={max_keys}")
    with urllib.request.urlopen(url, timeout=60) as r:
        root = ET.fromstring(r.read())
    return [p.find("s3:Prefix", NS).text
            for p in root.findall("s3:CommonPrefixes", NS)]


def _lat_bands(lat0, lat1):
    """MGRS latitude-band letters covering a latitude range."""
    letters = "CDEFGHJKLMNPQRSTUVWX"
    lo = max(0, min(19, int((lat0 + 80) // 8)))
    hi = max(0, min(19, int((lat1 + 80) // 8)))
    return [letters[i] for i in range(lo, hi + 1)]


def _tiles_for(bbox_utm, bands):
    """MGRS tiles whose imagery actually covers the bbox.

    The column letter follows from the easting, but the row letter depends on
    the band's origin — instead of re-deriving the MGRS rules, probe every
    square the bucket offers in the band and test the real raster bounds.
    Returns [(band, square)]."""
    x0, y0, x1, y1 = bbox_utm
    cols = "STUVWXYZ"                       # zone 36 column set
    want_cols = {cols[(int(e // 100000) - 1) % 8] for e in (x0, x1)}
    out = []
    for band in bands:
        squares = [p.rstrip("/").split("/")[-1]
                   for p in _list_prefixes(f"sentinel-s2-l2a-cogs/36/{band}/",
                                           200)]
        for sq in squares:
            if sq[0] not in want_cols:
                continue
            scene = _any_scene(band, sq)
            if not scene:
                continue
            try:
                with rasterio.open(f"/vsicurl/{BUCKET}/{scene}B04.tif") as ds:
                    b = ds.bounds
            except Exception:
                continue
            if b.right > x0 and b.left < x1 and b.top > y0 and b.bottom < y1:
                out.append((band, sq))
    return out


def _any_scene(band, square):
    """Path of one arbitrary (recent) scene, used only for a bounds probe."""
    years = _list_prefixes(f"sentinel-s2-l2a-cogs/36/{band}/{square}/", 60)
    if not years:
        return None
    months = _list_prefixes(years[-1], 30)
    if not months:
        return None
    scenes = _list_prefixes(months[-1], 10)
    return scenes[0] if scenes else None


def _data_coverage(scene, bbox_utm):
    """Fraction of the bbox window that actually carries data.

    Consecutive Sentinel-2 scenes over one MGRS tile alternate orbits, so
    roughly half of them are empty over any given corner of the tile —
    cloud cover alone is not enough to pick a usable scene."""
    x0, y0, x1, y1 = bbox_utm
    try:
        with rasterio.open(f"/vsicurl/{BUCKET}/{scene}B04.tif") as ds:
            b = ds.bounds
            wx0, wy0 = max(x0, b.left), max(y0, b.bottom)
            wx1, wy1 = min(x1, b.right), min(y1, b.top)
            if wx1 <= wx0 or wy1 <= wy0:
                return 0.0
            win = from_bounds(wx0, wy0, wx1, wy1, ds.transform)
            a = ds.read(1, window=win, out_shape=(96, 96))
            return float((a > 0).mean())
    except Exception:
        return 0.0


def _best_scene(band, square, months, max_cloud, bbox_utm):
    """Usable (data-covering) low-cloud scene for a tile."""
    best = None
    for ym in months:
        y, m = ym.split("-")
        prefix = (f"sentinel-s2-l2a-cogs/36/{band}/{square}/"
                  f"{int(y)}/{int(m)}/")
        for scene in _list_prefixes(prefix, 40):
            sid = scene.rstrip("/").split("/")[-1]
            try:
                with urllib.request.urlopen(f"{BUCKET}/{scene}{sid}.json",
                                            timeout=60) as r:
                    meta = json.load(r)
            except Exception:
                continue
            cloud = float(meta["properties"].get("eo:cloud_cover", 100))
            if cloud > max_cloud:
                continue
            cov = _data_coverage(scene, bbox_utm)
            if cov < 0.5:
                continue
            cand = {"scene": scene, "id": sid, "cloud": cloud, "cov": cov,
                    "datetime": meta["properties"]["datetime"]}
            if best is None or cloud < best["cloud"]:
                best = cand
            if cloud <= 1.0:
                return best
        if best:
            break
    return best


def _read_rgb(scene, bbox_utm, pad=2000):
    """Read B04/B03/B02 for the bbox window from one scene."""
    x0, y0, x1, y1 = bbox_utm
    bands = []
    prof = None
    for band in ("B04", "B03", "B02"):
        with rasterio.open(f"/vsicurl/{BUCKET}/{scene}{band}.tif") as ds:
            b = ds.bounds
            wx0, wy0 = max(x0 - pad, b.left), max(y0 - pad, b.bottom)
            wx1, wy1 = min(x1 + pad, b.right), min(y1 + pad, b.top)
            if wx1 <= wx0 or wy1 <= wy0:
                return None, None
            win = from_bounds(wx0, wy0, wx1, wy1, ds.transform)
            arr = ds.read(1, window=win).astype(np.float32)
            if prof is None:
                prof = {"transform": ds.window_transform(win),
                        "crs": ds.crs, "shape": arr.shape}
            bands.append(arr)
    return np.stack(bands), prof


def main(region_name, res_m, max_cloud, months):
    region = _load_region(region_name)
    bbox = region["bbox_itm"]
    from pyproj import Transformer
    to_utm = Transformer.from_crs(ITM_EPSG, UTM_EPSG, always_xy=True)
    corners = [to_utm.transform(x, y)
               for x in (bbox[0], bbox[2]) for y in (bbox[1], bbox[3])]
    ux = [c[0] for c in corners]
    uy = [c[1] for c in corners]
    bbox_utm = (min(ux), min(uy), max(ux), max(uy))

    to_wgs = Transformer.from_crs(ITM_EPSG, 4326, always_xy=True)
    lats = [to_wgs.transform(x, y)[1]
            for x in (bbox[0], bbox[2]) for y in (bbox[1], bbox[3])]
    bands = _lat_bands(min(lats), max(lats))
    tiles = _tiles_for(bbox_utm, bands)
    print(f"tiles: {[b + s for b, s in tiles]}")
    scenes = []
    for band, sq in tiles:
        s = _best_scene(band, sq, months, max_cloud, bbox_utm)
        if s:
            print(f"  {band}{sq}: {s['id']} cloud={s['cloud']:.1f}% cov={100*s['cov']:.0f}%")
            scenes.append(s)
    if not scenes:
        sys.exit("no scene found — widen --months or --max-cloud")

    # target ITM grid
    w = int(round((bbox[2] - bbox[0]) / res_m))
    h = int(round((bbox[3] - bbox[1]) / res_m))
    dst_transform = rasterio.transform.from_origin(bbox[0], bbox[3],
                                                   res_m, res_m)
    dst = np.zeros((3, h, w), dtype=np.float32)
    filled = np.zeros((h, w), dtype=bool)

    for s in scenes:
        rgb, prof = _read_rgb(s["scene"], bbox_utm)
        if rgb is None:
            continue
        tmp = np.zeros((3, h, w), dtype=np.float32)
        for i in range(3):
            reproject(source=rgb[i], destination=tmp[i],
                      src_transform=prof["transform"], src_crs=prof["crs"],
                      dst_transform=dst_transform, dst_crs=f"EPSG:{ITM_EPSG}",
                      resampling=Resampling.bilinear,
                      src_nodata=0, dst_nodata=0)
        got = tmp.sum(axis=0) > 0
        take = got & ~filled
        for i in range(3):
            dst[i][take] = tmp[i][take]
        filled |= got
        print(f"  merged {s['id']}: coverage {100*filled.mean():.0f}%")

    # percentile stretch per band (robust to bright roofs / dark water)
    img = np.zeros((h, w, 3), dtype=np.uint8)
    valid = filled
    for i in range(3):
        band = dst[i]
        vals = band[valid & (band > 0)]
        if vals.size == 0:
            continue
        lo, hi = np.percentile(vals, [2, 98])
        stretched = np.clip((band - lo) / max(hi - lo, 1e-6), 0, 1)
        stretched = np.power(stretched, 0.85)      # gentle gamma
        img[:, :, i] = (stretched * 255).astype(np.uint8)

    out_dir = os.path.join(region["_base"], "derived")
    os.makedirs(out_dir, exist_ok=True)
    jpg = os.path.join(out_dir, "basemap.jpg")
    from PIL import Image
    Image.fromarray(img, mode="RGB").save(jpg, quality=82, optimize=True)

    meta = {
        "bbox_itm": bbox, "res_m": res_m,
        "scenes": [{"id": s["id"], "datetime": s["datetime"],
                    "cloud_cover": round(s["cloud"], 2)} for s in scenes],
        "source": "Copernicus Sentinel-2 L2A (AWS Open Data, sentinel-cogs)",
        "attribution_he": "מכיל נתוני Copernicus Sentinel-2 מעובדים (ESA)",
        "quality": "satellite_imagery",
        "notes_he": ("רקע-תצ\"א לקריאוּת בלבד — אינו שכבת-ראיה; "
                     "התאריך שונה מתאריכי הדיגום."),
    }
    with open(os.path.join(out_dir, "basemap_meta.json"), "w",
              encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"wrote {jpg} ({os.path.getsize(jpg)//1024} KB, {w}x{h} px)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("region")
    ap.add_argument("--res", type=float, default=15.0)
    ap.add_argument("--max-cloud", type=float, default=5.0)
    ap.add_argument("--months", nargs="+",
                    default=["2025-08", "2025-07", "2025-09", "2025-06"])
    a = ap.parse_args()
    main(a.region, a.res, a.max_cloud, a.months)
