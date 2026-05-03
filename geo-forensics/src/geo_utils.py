"""geo_utils.py - המרת ITM↔WGS84 (arcpy→pyproj→math fallback)."""

import math

import numpy as np
import pandas as pd

from config import ITM_EPSG, ITM_X_RANGE, ITM_Y_RANGE, WGS84_EPSG

# ── Backend detection ──
_BACKEND = None

try:
    import arcpy
    _BACKEND = "arcpy"
except ImportError:
    try:
        from pyproj import Transformer
        _BACKEND = "pyproj"
    except ImportError:
        _BACKEND = "math"

# ── Setup based on backend ──
if _BACKEND == "pyproj":
    _transformer_to_wgs84 = Transformer.from_crs(
        f"EPSG:{ITM_EPSG}", f"EPSG:{WGS84_EPSG}", always_xy=True
    )
    _transformer_to_itm = Transformer.from_crs(
        f"EPSG:{WGS84_EPSG}", f"EPSG:{ITM_EPSG}", always_xy=True
    )
elif _BACKEND == "arcpy":
    _sr_itm = arcpy.SpatialReference(ITM_EPSG)
    _sr_wgs84 = arcpy.SpatialReference(WGS84_EPSG)


def itm_to_wgs84(x: float, y: float) -> tuple[float, float]:
    _validate_itm(x, y)

    if _BACKEND == "arcpy":
        point = arcpy.PointGeometry(arcpy.Point(x, y), _sr_itm)
        projected = point.projectAs(_sr_wgs84)
        return projected.firstPoint.Y, projected.firstPoint.X
    elif _BACKEND == "pyproj":
        lon, lat = _transformer_to_wgs84.transform(x, y)
        return lat, lon
    else:
        return _itm_to_wgs84_math(x, y)


def wgs84_to_itm(lat: float, lon: float) -> tuple[float, float]:
    if _BACKEND == "arcpy":
        point = arcpy.PointGeometry(arcpy.Point(lon, lat), _sr_wgs84)
        projected = point.projectAs(_sr_itm)
        return projected.firstPoint.X, projected.firstPoint.Y
    elif _BACKEND == "pyproj":
        x, y = _transformer_to_itm.transform(lon, lat)
        return x, y
    else:
        return _wgs84_to_itm_math(lat, lon)


def batch_convert(df: pd.DataFrame, x_col: str = "x_itm", y_col: str = "y_itm") -> pd.DataFrame:
    df = df.copy()

    # Filter valid rows
    valid_mask = (
        df[x_col].notna()
        & df[y_col].notna()
        & df[x_col].between(*ITM_X_RANGE)
        & df[y_col].between(*ITM_Y_RANGE)
    )

    df["lat"] = np.nan
    df["lon"] = np.nan

    if valid_mask.any():
        xs = df.loc[valid_mask, x_col].values
        ys = df.loc[valid_mask, y_col].values

        if _BACKEND == "arcpy":
            lats_out, lons_out = [], []
            for xi, yi in zip(xs, ys):
                pt = arcpy.PointGeometry(arcpy.Point(float(xi), float(yi)), _sr_itm)
                proj = pt.projectAs(_sr_wgs84)
                lats_out.append(proj.firstPoint.Y)
                lons_out.append(proj.firstPoint.X)
            df.loc[valid_mask, "lat"] = lats_out
            df.loc[valid_mask, "lon"] = lons_out
        elif _BACKEND == "pyproj":
            lons, lats = _transformer_to_wgs84.transform(xs, ys)
            df.loc[valid_mask, "lat"] = lats
            df.loc[valid_mask, "lon"] = lons
        else:
            lats_out, lons_out = [], []
            for xi, yi in zip(xs, ys):
                lat_i, lon_i = _itm_to_wgs84_math(float(xi), float(yi))
                lats_out.append(lat_i)
                lons_out.append(lon_i)
            df.loc[valid_mask, "lat"] = lats_out
            df.loc[valid_mask, "lon"] = lons_out

    invalid_count = (~valid_mask).sum()
    if invalid_count > 0:
        print(f"⚠ {invalid_count} שורות עם קואורדינטות לא תקינות - לא הומרו")

    return df


def calc_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters."""
    R = 6_371_000  # Earth radius in meters

    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def point_in_polygon(lat: float, lon: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray casting algorithm. polygon = [(lat, lon), ...]."""
    n = len(polygon)
    inside = False

    j = n - 1
    for i in range(n):
        yi, xi = polygon[i]
        yj, xj = polygon[j]

        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i

    return inside


def _itm_to_wgs84_math(x: float, y: float) -> tuple[float, float]:
    """
    המרת ITM ל-WGS84 בנוסחת Transverse Mercator הפוכה.
    דיוק ~1 מטר באזור ישראל. משמש כ-fallback כשאין arcpy/pyproj.
    """
    # ITM parameters (EPSG:2039)
    a = 6378137.0  # WGS84 semi-major axis
    f = 1 / 298.257223563  # WGS84 flattening
    e2 = 2 * f - f * f
    e = math.sqrt(e2)
    e_prime2 = e2 / (1 - e2)

    # ITM projection parameters
    lon0 = math.radians(35.2045169444444)  # Central meridian
    lat0 = math.radians(31.7343936111111)  # Latitude of origin
    k0 = 1.0000067  # Scale factor
    false_easting = 219529.584
    false_northing = 626907.39

    # Remove false easting/northing
    x_adj = x - false_easting
    y_adj = y - false_northing

    # Meridional arc length at origin latitude (M0)
    M0 = a * (
        (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * lat0
        - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * lat0)
        + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * lat0)
        - (35 * e2**3 / 3072) * math.sin(6 * lat0)
    )

    # Footpoint latitude — M must be absolute (from equator)
    M = y_adj / k0 + M0
    mu = M / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = mu + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
    phi1 += (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
    phi1 += (151 * e1**3 / 96) * math.sin(6 * mu)
    phi1 += (1097 * e1**4 / 512) * math.sin(8 * mu)

    N1 = a / math.sqrt(1 - e2 * math.sin(phi1)**2)
    T1 = math.tan(phi1)**2
    C1 = e_prime2 * math.cos(phi1)**2
    R1 = a * (1 - e2) / (1 - e2 * math.sin(phi1)**2)**1.5
    D = x_adj / (N1 * k0)

    lat = phi1 - (N1 * math.tan(phi1) / R1) * (
        D**2 / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1**2 - 9 * e_prime2) * D**4 / 24
        + (61 + 90 * T1 + 298 * C1 + 45 * T1**2 - 252 * e_prime2 - 3 * C1**2) * D**6 / 720
    )
    lon = lon0 + (D - (1 + 2 * T1 + C1) * D**3 / 6
        + (5 - 2 * C1 + 28 * T1 - 3 * C1**2 + 8 * e_prime2 + 24 * T1**2) * D**5 / 120
    ) / math.cos(phi1)

    return math.degrees(lat), math.degrees(lon)


def _wgs84_to_itm_math(lat: float, lon: float) -> tuple[float, float]:
    """
    המרת WGS84 ל-ITM בנוסחת Transverse Mercator ישירה.
    דיוק ~1 מטר באזור ישראל. משמש כ-fallback כשאין arcpy/pyproj.
    """
    a = 6378137.0
    f = 1 / 298.257223563
    e2 = 2 * f - f * f
    e_prime2 = e2 / (1 - e2)

    lon0 = math.radians(35.2045169444444)
    lat0 = math.radians(31.7343936111111)
    k0 = 1.0000067
    false_easting = 219529.584
    false_northing = 626907.39

    phi = math.radians(lat)
    lam = math.radians(lon)
    dlam = lam - lon0

    N = a / math.sqrt(1 - e2 * math.sin(phi)**2)
    T = math.tan(phi)**2
    C = e_prime2 * math.cos(phi)**2
    A = dlam * math.cos(phi)

    M = a * (
        (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * phi
        - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * phi)
        + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * phi)
        - (35 * e2**3 / 3072) * math.sin(6 * phi)
    )

    # M0: meridional arc at origin latitude — subtract to get relative northing
    M0 = a * (
        (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * lat0
        - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * lat0)
        + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * lat0)
        - (35 * e2**3 / 3072) * math.sin(6 * lat0)
    )

    x = false_easting + k0 * N * (
        A + (1 - T + C) * A**3 / 6
        + (5 - 18 * T + T**2 + 72 * C - 58 * e_prime2) * A**5 / 120
    )
    y = false_northing + k0 * (
        (M - M0) + N * math.tan(phi) * (
            A**2 / 2 + (5 - T + 9 * C + 4 * C**2) * A**4 / 24
            + (61 - 58 * T + T**2 + 600 * C - 330 * e_prime2) * A**6 / 720
        )
    )

    return x, y


def _validate_itm(x: float, y: float) -> None:
    """בודק שקואורדינטות ITM בטווח סביר לישראל."""
    if not (ITM_X_RANGE[0] <= x <= ITM_X_RANGE[1]):
        raise ValueError(
            f"X={x} מחוץ לטווח ITM הצפוי ({ITM_X_RANGE[0]:,}-{ITM_X_RANGE[1]:,}). "
            f"בדוק שהנתונים במערכת ITM."
        )
    if not (ITM_Y_RANGE[0] <= y <= ITM_Y_RANGE[1]):
        raise ValueError(
            f"Y={y} מחוץ לטווח ITM הצפוי ({ITM_Y_RANGE[0]:,}-{ITM_Y_RANGE[1]:,}). "
            f"בדוק שהנתונים במערכת ITM."
        )
