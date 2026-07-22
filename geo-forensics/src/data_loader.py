"""data_loader.py - טעינת קבצי Excel/CSV ומיפוי עמודות עברית→אנגלית."""

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

# פרמטרים מצרפיים (סכום כולל) — לא תרכובות בודדות.
# TPFAS = סכום כל הקונגנרים; אם נכנס לניתוח הוא סופר-כפול את הריכוז ומשתלט על
# טביעת האצבע. חייב להיסנן כבר בטעינה כך שלא ייכנס ל-df כלל.
# ההשוואה נעשית על ערך מנורמל (strip + upper).
AGGREGATE_PARAMETERS = {
    "TPFAS", "PFAS TOTAL", "TOTAL PFAS", "SUM PFAS", "ΣPFAS",
    'סה"כ PFAS', "PFAS סה\"כ",
}


def load_file(file) -> pd.DataFrame:
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
    existing = set(df.columns)
    missing = [col for col in REQUIRED_COLUMNS if col not in existing]
    return len(missing) == 0, missing


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Drop fully empty rows
    df = df.dropna(how="all")

    # Drop aggregate/total parameters (e.g. TPFAS = sum of congeners).
    # They must never enter the DataFrame — otherwise they inflate ΣPFAS and
    # dominate the fingerprint. Filtered here so no downstream code sees them.
    if "compound" in df.columns:
        _agg = {a.strip().upper() for a in AGGREGATE_PARAMETERS}
        df = df[~df["compound"].astype(str).str.strip().str.upper().isin(_agg)]

    # Parse dates (handles both regular date strings and Excel serial numbers)
    if "sample_date" in df.columns:
        df["sample_date"] = _parse_dates(df["sample_date"])

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


# Excel serial-date range guard: ~1970-01-01 (25569) .. ~2069 (73415).
# Values inside this window that arrive as bare numbers are Excel serials,
# not nanosecond timestamps — pd.to_datetime would otherwise misread them
# (e.g. 45840 -> 1970-01-01 00:00:00.000045840). Some Water Authority Excel
# exports store the sample date as a raw serial number instead of a date cell.
_EXCEL_SERIAL_MIN = 25569   # 1970-01-01
_EXCEL_SERIAL_MAX = 73415   # ~2070-01-01


def _parse_dates(series: pd.Series) -> pd.Series:
    """Parse a date column, converting Excel serial numbers correctly.

    Regular date strings/datetimes go through pd.to_datetime as usual; bare
    numbers within the plausible Excel-serial range are converted with the
    1899-12-30 origin.
    """
    numeric = pd.to_numeric(series, errors="coerce")
    is_serial = numeric.notna() & numeric.between(_EXCEL_SERIAL_MIN, _EXCEL_SERIAL_MAX)

    parsed = pd.to_datetime(series, dayfirst=True, errors="coerce")
    if is_serial.any():
        serial_dates = pd.to_datetime(
            numeric.where(is_serial), unit="D", origin="1899-12-30", errors="coerce"
        )
        parsed = parsed.where(~is_serial, serial_dates)
    return parsed


def _parse_concentration(value) -> float | None:
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
