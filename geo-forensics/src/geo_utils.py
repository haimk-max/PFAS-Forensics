"""
geo_utils.py - המרת קואורדינטות ופונקציות גיאוגרפיות
=====================================================
המודול הזה ממיר קואורדינטות בין מערכת ITM (Israel Transverse Mercator)
שבה רשות המים עובדת, למערכת WGS84 (lat/lon) שמפות אינטרנט משתמשות בה.

מושגים:
- ITM = מערכת קואורדינטות ישראלית (X = מזרחה, Y = צפונה), מטרים
- WGS84 = מערכת עולמית (latitude, longitude), מעלות
- EPSG:2039 = קוד ITM הרשמי
- EPSG:4326 = קוד WGS84 הרשמי
"""

import math

import numpy as np
import pandas as pd
from pyproj import Transformer

from config import ITM_EPSG, ITM_X_RANGE, ITM_Y_RANGE, WGS84_EPSG

# Transformer object - ממיר מ-ITM ל-WGS84
# always_xy=True means: input is (x, y), output is (lon, lat)
_transformer_to_wgs84 = Transformer.from_crs(
    f"EPSG:{ITM_EPSG}", f"EPSG:{WGS84_EPSG}", always_xy=True
)

_transformer_to_itm = Transformer.from_crs(
    f"EPSG:{WGS84_EPSG}", f"EPSG:{ITM_EPSG}", always_xy=True
)


def itm_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """
    ממיר נקודה אחת מ-ITM ל-WGS84.

    Args:
        x: קואורדינטת X (מזרחה) ב-ITM
        y: קואורדינטת Y (צפונה) ב-ITM

    Returns:
        (lat, lon) - קו רוחב וקו אורך ב-WGS84

    Raises:
        ValueError: אם הקואורדינטות מחוץ לטווח הסביר של ישראל

    דוגמה:
        lat, lon = itm_to_wgs84(200000, 600000)
        # -> (32.07..., 34.77...)  # בערך תל אביב
    """
    _validate_itm(x, y)
    lon, lat = _transformer_to_wgs84.transform(x, y)
    return lat, lon


def wgs84_to_itm(lat: float, lon: float) -> tuple[float, float]:
    """
    ממיר נקודה אחת מ-WGS84 ל-ITM.

    Args:
        lat: קו רוחב
        lon: קו אורך

    Returns:
        (x, y) - קואורדינטות ITM
    """
    x, y = _transformer_to_itm.transform(lon, lat)
    return x, y


def batch_convert(df: pd.DataFrame, x_col: str = "x_itm", y_col: str = "y_itm") -> pd.DataFrame:
    """
    ממיר עמודות ITM שלמות ל-WGS84, מוסיף עמודות lat ו-lon ל-DataFrame.

    Args:
        df: טבלת נתונים עם עמודות x_itm ו-y_itm
        x_col: שם עמודת X
        y_col: שם עמודת Y

    Returns:
        אותו DataFrame עם עמודות lat ו-lon חדשות

    דוגמה:
        df = batch_convert(df)
        # df כעת מכיל עמודות "lat" ו-"lon"
    """
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
        lons, lats = _transformer_to_wgs84.transform(
            df.loc[valid_mask, x_col].values,
            df.loc[valid_mask, y_col].values,
        )
        df.loc[valid_mask, "lat"] = lats
        df.loc[valid_mask, "lon"] = lons

    invalid_count = (~valid_mask).sum()
    if invalid_count > 0:
        print(f"⚠ {invalid_count} שורות עם קואורדינטות לא תקינות - לא הומרו")

    return df


def calc_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    מחשב מרחק בין שתי נקודות בנוסחת Haversine.

    Args:
        lat1, lon1: נקודה ראשונה (WGS84)
        lat2, lon2: נקודה שנייה (WGS84)

    Returns:
        מרחק במטרים

    דוגמה:
        d = calc_distance(32.07, 34.77, 32.08, 34.78)
        # -> ~1400 מטר (בערך)
    """
    R = 6_371_000  # Earth radius in meters

    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def point_in_polygon(lat: float, lon: float, polygon: list[tuple[float, float]]) -> bool:
    """
    בודק אם נקודה נמצאת בתוך פוליגון (Ray casting algorithm).

    Args:
        lat, lon: הנקודה לבדיקה
        polygon: רשימת קודקודים [(lat, lon), ...] - הפוליגון חייב להיות סגור

    Returns:
        True אם הנקודה בתוך הפוליגון
    """
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
