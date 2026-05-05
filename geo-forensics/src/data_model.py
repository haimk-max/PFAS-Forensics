"""
data_model.py - עיבוד נתונים ושדות מחושבים
============================================
המודול הזה אחראי על:
1. Pipeline מלא: מקובץ גולמי -> DataFrame מוכן לניתוח
2. חישוב שדות נגזרים (סה"כ ריכוזים, מטריצת fingerprint)
3. סיכומים סטטיסטיים בסיסיים

זהו המודול שמחבר בין data_loader (טעינה) ל-analytics (ניתוח).
"""

import pandas as pd

from src.contaminant_groups import ContaminantGroup, detect_group, get_group
from src.data_loader import clean_data, load_file, normalize_columns, validate_schema
from src.geo_utils import batch_convert


def process_file(file, group_name: str | None = None) -> tuple[pd.DataFrame, ContaminantGroup]:
    """
    Pipeline מלא: מקובץ Excel/CSV ל-DataFrame מוכן לעבודה.

    השלבים:
    1. טעינת הקובץ
    2. מיפוי שמות עמודות (עברית -> אנגלית)
    3. ולידציה (בדיקה שכל העמודות הנדרשות קיימות)
    4. ניקוי נתונים (תאריכים, מספרים, ערכי LOD)
    5. המרת קואורדינטות (ITM -> WGS84)
    6. זיהוי/הגדרת קבוצת מזהמים

    Args:
        file: קובץ שהועלה או נתיב
        group_name: שם קבוצת מזהמים (אם None - ניסיון זיהוי אוטומטי)

    Returns:
        (df, group)
        - df: DataFrame מוכן לניתוח, עם עמודות lat/lon
        - group: קבוצת המזהמים שזוהתה/נבחרה

    Raises:
        ValueError: אם חסרות עמודות נדרשות או שלא זוהתה קבוצת מזהמים
    """
    # 1. Load
    df = load_file(file)

    # 2. Normalize column names
    df = normalize_columns(df)

    # 3. Validate
    is_valid, missing = validate_schema(df)
    if not is_valid:
        raise ValueError(
            f"חסרות עמודות בקובץ: {', '.join(missing)}.\n"
            f"ודא שהקובץ מכיל את העמודות: שם תחנה, X, Y, תאריך דיגום, תרכובת, ריכוז"
        )

    # 4. Clean
    df = clean_data(df)

    # 5. Convert coordinates
    df = batch_convert(df)

    # 6. Detect/set contaminant group
    if group_name:
        group = get_group(group_name)
    else:
        compounds = df["compound"].dropna().unique().tolist()
        detected = detect_group(compounds)
        if detected:
            group = get_group(detected)
        else:
            raise ValueError(
                "לא הצלחתי לזהות את קבוצת המזהמים אוטומטית. "
                "אנא בחר קבוצה ידנית."
            )

    return df, group


def calc_total_concentration(df: pd.DataFrame, group: ContaminantGroup) -> pd.DataFrame:
    """
    מחשב סה"כ ריכוז (סכום כל התרכובות) לכל תחנה ותאריך.

    Args:
        df: DataFrame מעובד
        group: קבוצת מזהמים

    Returns:
        DataFrame עם עמודה "total_concentration" חדשה,
        שורה אחת לכל תחנה + תאריך
    """
    # Filter to known compounds in this group
    known = {c.upper() for c in group.compounds}
    mask = df["compound"].str.upper().isin(known)
    filtered = df[mask].copy()

    # Sum concentrations per station + date
    totals = (
        filtered.groupby(["station_name", "sample_date"])
        .agg(
            total_concentration=("concentration", "sum"),
            x_itm=("x_itm", "first"),
            y_itm=("y_itm", "first"),
            lat=("lat", "first"),
            lon=("lon", "first"),
            source_type=("source_type", "first"),
        )
        .reset_index()
    )

    return totals


def build_fingerprint_matrix(df: pd.DataFrame, group: ContaminantGroup) -> pd.DataFrame:
    """
    בונה מטריצת "טביעת אצבע כימית" - כל תחנה כשורה,
    כל תרכובת כעמודה, הערכים באחוזים יחסיים (סה"כ = 100%).

    לכל תחנה נבחר אירוע הדיגום (תאריך) שבו סכום הריכוזים
    הכולל הוא המירבי. זה הבסיס לניתוח PCA ו-Cosine Similarity.

    Args:
        df: DataFrame מעובד
        group: קבוצת מזהמים

    Returns:
        DataFrame: שורות = תחנות, עמודות = תרכובות (ב-%)
    """
    known = {c.upper() for c in group.compounds}
    mask = df["compound"].str.upper().isin(known)
    filtered = df[mask].copy()

    # For each station, find the sampling event (date) with max total concentration
    totals = (
        filtered.groupby(["station_name", "sample_date"])["concentration"]
        .sum()
        .reset_index(name="total")
    )
    best_event = totals.loc[totals.groupby("station_name")["total"].idxmax()]
    best_keys = set(zip(best_event["station_name"], best_event["sample_date"]))

    # Keep only rows belonging to the max-total event per station
    filtered = filtered[
        filtered.apply(lambda r: (r["station_name"], r["sample_date"]) in best_keys, axis=1)
    ]

    # Pivot: rows = station, columns = compound, values = concentration from max event
    matrix = filtered.pivot_table(
        index="station_name",
        columns="compound",
        values="concentration",
        aggfunc="sum",
        fill_value=0,
    )

    # Convert to relative percentages (each row sums to 100%)
    row_sums = matrix.sum(axis=1)
    # Avoid division by zero
    row_sums = row_sums.replace(0, 1)
    matrix = matrix.div(row_sums, axis=0) * 100

    return matrix


def get_station_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    יוצר טבלת סיכום לפי תחנות - שימושי לתצוגה ב-UI.

    Returns:
        DataFrame עם: שם תחנה, קואורדינטות, סוג מקור, מספר דיגומים,
        תאריך ראשון ואחרון
    """
    summary = (
        df.groupby("station_name")
        .agg(
            x_itm=("x_itm", "first"),
            y_itm=("y_itm", "first"),
            lat=("lat", "first"),
            lon=("lon", "first"),
            source_type=("source_type", "first"),
            n_samples=("sample_date", "nunique"),
            first_date=("sample_date", "min"),
            last_date=("sample_date", "max"),
            n_compounds=("compound", "nunique"),
        )
        .reset_index()
    )

    return summary
