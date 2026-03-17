"""
data_loader.py - טעינת קבצי נתונים (Excel / CSV)
==================================================
המודול הזה אחראי על:
1. קריאת קבצי Excel ו-CSV
2. זיהוי קידוד עברית (UTF-8 או CP1255)
3. מיפוי שמות עמודות מעברית לאנגלית (לשימוש פנימי)
4. ולידציה שכל העמודות הנדרשות קיימות

המשתמש מעלה קובץ Excel כמו שהוא מקבל אותו מרשות המים,
והמודול דואג להתאים אותו למבנה הפנימי של המערכת.
"""

import io

import pandas as pd

from config import DEFAULT_ENCODING, FALLBACK_ENCODING, SUPPORTED_EXTENSIONS

# =============================================================================
# מיפוי שמות עמודות: עברית -> אנגלית (שמות פנימיים)
# כל וריאציה אפשרית ממופה לשם פנימי אחיד
# =============================================================================

COLUMN_MAPPING: dict[str, str] = {
    # Station name
    "שם תחנה": "station_name",
    "שם התחנה": "station_name",
    "תחנה": "station_name",
    "station": "station_name",
    "station_name": "station_name",
    "water_source_name": "station_name",
    "שם מקור מים": "station_name",
    # X coordinate (ITM)
    "x": "x_itm",
    "x_itm": "x_itm",
    "x (itm)": "x_itm",
    "איקס": "x_itm",
    "קואורדינטה x": "x_itm",
    "x_coordinate": "x_itm",
    # Y coordinate (ITM)
    "y": "y_itm",
    "y_itm": "y_itm",
    "y (itm)": "y_itm",
    "וואי": "y_itm",
    "קואורדינטה y": "y_itm",
    "y_coordinate": "y_itm",
    # Sample date
    "תאריך דיגום": "sample_date",
    "תאריך": "sample_date",
    "date": "sample_date",
    "sample_date": "sample_date",
    # Source type
    "סוג מקור": "source_type",
    "סוג": "source_type",
    "מקור": "source_type",
    "source_type": "source_type",
    "water_source_type": "source_type",
    "סוג מקור מים": "source_type",
    # Compound
    "סמל תרכובת": "compound",
    "תרכובת": "compound",
    "שם תרכובת": "compound",
    "compound": "compound",
    "parameter": "compound",
    "param_symbol": "compound",
    "סמל פרמטר": "compound",
    # Concentration
    "ריכוז": "concentration",
    "ריכוז (µg/l)": "concentration",
    "ריכוז (mg/l)": "concentration",
    "תוצאה": "concentration",
    "concentration": "concentration",
    "result": "concentration",
    # Unit
    "יחידה": "unit",
    "יחידות": "unit",
    "unit": "unit",
    "units": "unit",
    "measure_unit": "unit",
    "יחידת מדידה": "unit",
}

# עמודות חובה - חייבות להיות בכל קובץ
REQUIRED_COLUMNS = ["station_name", "x_itm", "y_itm", "sample_date", "compound", "concentration"]


def load_file(file) -> pd.DataFrame:
    """
    טוען קובץ Excel או CSV ומחזיר DataFrame.

    Args:
        file: קובץ שהועלה (UploadedFile מ-Streamlit, או נתיב לקובץ)

    Returns:
        pd.DataFrame עם הנתונים הגולמיים

    Raises:
        ValueError: אם סוג הקובץ לא נתמך
    """
    # Determine file name
    if hasattr(file, "name"):
        filename = file.name.lower()
    else:
        filename = str(file).lower()

    if filename.endswith((".xlsx", ".xls")):
        return _load_excel(file)
    elif filename.endswith(".csv"):
        return _load_csv(file)
    else:
        raise ValueError(
            f"סוג קובץ לא נתמך. סוגים נתמכים: {', '.join(SUPPORTED_EXTENSIONS)}"
        )


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    ממפה שמות עמודות מעברית לשמות פנימיים באנגלית.

    Args:
        df: DataFrame עם שמות עמודות מקוריים (בעברית או באנגלית)

    Returns:
        DataFrame עם שמות עמודות פנימיים

    דוגמה:
        df עם עמודה "שם תחנה" -> df עם עמודה "station_name"
    """
    df = df.copy()

    new_columns = {}
    for col in df.columns:
        normalized_key = str(col).strip().lower()
        if normalized_key in COLUMN_MAPPING:
            new_columns[col] = COLUMN_MAPPING[normalized_key]
        # Keep original name if not in mapping

    df = df.rename(columns=new_columns)
    return df


def validate_schema(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """
    בודק שכל העמודות הנדרשות קיימות ב-DataFrame.

    Args:
        df: DataFrame לבדיקה (אחרי normalize_columns)

    Returns:
        (is_valid, missing_columns)
        - is_valid: True אם הכל תקין
        - missing_columns: רשימת עמודות חסרות (ריקה אם הכל תקין)

    דוגמה:
        ok, missing = validate_schema(df)
        if not ok:
            print(f"חסרות עמודות: {missing}")
    """
    existing = set(df.columns)
    missing = [col for col in REQUIRED_COLUMNS if col not in existing]
    return len(missing) == 0, missing


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    ניקוי בסיסי של הנתונים:
    - המרת תאריכים
    - המרת ריכוזים למספרים (כולל טיפול ב"<LOD")
    - הסרת שורות ריקות

    Args:
        df: DataFrame עם שמות עמודות פנימיים

    Returns:
        DataFrame נקי
    """
    df = df.copy()

    # Drop fully empty rows
    df = df.dropna(how="all")

    # Parse dates
    if "sample_date" in df.columns:
        df["sample_date"] = pd.to_datetime(df["sample_date"], dayfirst=True, errors="coerce")

    # Parse concentrations - handle "<LOD" values (below limit of detection)
    if "concentration" in df.columns:
        df["concentration"] = df["concentration"].apply(_parse_concentration)

    # Ensure numeric coordinates
    for col in ["x_itm", "y_itm"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _load_excel(file) -> pd.DataFrame:
    """טוען קובץ Excel."""
    return pd.read_excel(file, engine="openpyxl")


def _load_csv(file) -> pd.DataFrame:
    """טוען קובץ CSV, מנסה UTF-8 ואם נכשל - CP1255 (עברית Windows)."""
    if hasattr(file, "read"):
        content = file.read()
        if isinstance(content, str):
            return pd.read_csv(io.StringIO(content))
        # bytes - try encodings
        try:
            return pd.read_csv(io.BytesIO(content), encoding=DEFAULT_ENCODING)
        except UnicodeDecodeError:
            return pd.read_csv(io.BytesIO(content), encoding=FALLBACK_ENCODING)
    else:
        # File path
        try:
            return pd.read_csv(file, encoding=DEFAULT_ENCODING)
        except UnicodeDecodeError:
            return pd.read_csv(file, encoding=FALLBACK_ENCODING)


def _parse_concentration(value) -> float | None:
    """
    ממיר ערך ריכוז למספר.
    מטפל במקרים כמו:
    - "<0.01" (מתחת לסף זיהוי) -> 0.0 (נחשב כאפס)
    - "N.D." / "ND" (לא זוהה) -> 0.0
    - מספר רגיל -> float
    """
    if pd.isna(value):
        return None

    s = str(value).strip()

    # Below detection limit
    if s.startswith("<"):
        return 0.0

    # Not detected
    if s.upper() in ("N.D.", "ND", "LOD", "BDL", "לא זוהה"):
        return 0.0

    try:
        return float(s)
    except ValueError:
        return None
