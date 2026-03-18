"""
app.py - נקודת הכניסה הראשית של GeoForensics
==============================================
זהו הקובץ שמריצים: streamlit run app.py

האפליקציה רצה מקומית בלבד (localhost:8501).
אין שימוש ב-API חיצוני, אין שליחת נתונים לשום מקום.
"""

import os
import sys

import streamlit as st

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(__file__))

from config import APP_DESCRIPTION, APP_NAME, APP_VERSION, DATA_DIR, PAGE_ICON, SUPPORTED_EXTENSIONS
from src.contaminant_groups import get_group, list_groups
from src.data_loader import load_file, normalize_columns, validate_schema, clean_data

# =============================================================================
# Page Config - must be first Streamlit command
# =============================================================================
st.set_page_config(
    page_title=APP_NAME,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# RTL support for Hebrew
st.markdown(
    """
    <style>
    .stApp { direction: rtl; }
    .stMarkdown, .stText { text-align: right; }
    /* Keep data tables LTR for readability */
    .stDataFrame { direction: ltr; }
    /* Keep number inputs LTR */
    input[type="number"] { direction: ltr; text-align: left; }
    /* Sidebar RTL adjustments */
    section[data-testid="stSidebar"] { direction: rtl; }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stFileUploader label { text-align: right; }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# Helpers
# =============================================================================
def _list_data_files() -> list[str]:
    """מחזיר רשימת קבצי Excel/CSV מתיקיית DATA_DIR."""
    data_path = os.path.join(os.path.dirname(__file__), DATA_DIR)
    if not os.path.isdir(data_path):
        return []
    files = []
    for f in sorted(os.listdir(data_path)):
        ext = os.path.splitext(f)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            files.append(f)
    return files


def _load_and_process(file_path_or_obj):
    """טוען קובץ, מנרמל עמודות, מוולד ומנקה. מחזיר (df, missing)."""
    raw = load_file(file_path_or_obj)
    df = normalize_columns(raw)
    is_valid, missing = validate_schema(df)
    if not is_valid:
        return None, missing
    df = clean_data(df)
    return df, []


# =============================================================================
# Session State
# =============================================================================
def init_session_state():
    defaults = {
        "df": None,
        "raw_df": None,
        "group_name": None,
        "file_name": None,
        "file_loaded": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# =============================================================================
# Sidebar
# =============================================================================
with st.sidebar:
    st.title(f"{PAGE_ICON} {APP_NAME}")
    st.caption(f"v{APP_VERSION} | {APP_DESCRIPTION}")
    st.divider()

    # --- 1. Contaminant group ---
    st.subheader("1. קבוצת מזהמים")
    groups = list_groups()
    # PFAS first, then the rest
    if "PFAS" in groups:
        groups.remove("PFAS")
        groups.insert(0, "PFAS")
    selected_group = st.selectbox(
        "קבוצה",
        options=groups,
        index=0,
        help="בחר את קבוצת המזהמים לניתוח",
    )

    st.divider()

    # --- 2. Data source ---
    st.subheader("2. מקור נתונים")

    data_files = _list_data_files()
    source_mode = st.radio(
        "טעינת קובץ",
        options=["מתיקיית נתונים", "העלאה ידנית"],
        horizontal=True,
        label_visibility="collapsed",
    )

    chosen_file = None

    if source_mode == "מתיקיית נתונים":
        if data_files:
            chosen_name = st.selectbox(
                "בחר קובץ",
                options=data_files,
                index=0,
                help=f"קבצים מתוך {DATA_DIR}/",
            )
            chosen_file = os.path.join(os.path.dirname(__file__), DATA_DIR, chosen_name)
        else:
            st.warning(f"לא נמצאו קבצים בתיקייה {DATA_DIR}/")
    else:
        uploaded = st.file_uploader(
            "העלה קובץ Excel או CSV",
            type=["xlsx", "xls", "csv"],
            help="קובץ עם עמודות: שם תחנה, X, Y, תאריך דיגום, תרכובת, ריכוז",
        )
        if uploaded:
            chosen_file = uploaded

    # Load button
    load_clicked = st.button("טען נתונים", use_container_width=True, type="primary")


# =============================================================================
# Process file on button click
# =============================================================================
if load_clicked and chosen_file is not None:
    with st.spinner("טוען ומעבד את הנתונים..."):
        try:
            df, missing = _load_and_process(chosen_file)
            if df is None:
                st.error(f"עמודות חסרות בקובץ: {', '.join(missing)}")
            else:
                st.session_state.df = df
                st.session_state.raw_df = df.copy()
                st.session_state.group_name = selected_group
                st.session_state.file_name = (
                    chosen_file.name if hasattr(chosen_file, "name")
                    else os.path.basename(str(chosen_file))
                )
                st.session_state.file_loaded = True
                st.rerun()
        except Exception as e:
            st.error(f"שגיאה בטעינת הקובץ:\n{e}")

elif load_clicked and chosen_file is None:
    st.warning("יש לבחור קובץ לפני טעינה.")


# =============================================================================
# Main Content
# =============================================================================
if not st.session_state.file_loaded:
    st.title(f"ברוכים הבאים ל-{APP_NAME}")
    st.markdown(
        """
        ### כלי לחקירת מקורות זיהום במים, קרקע ושפכים

        **שלבי העבודה:**
        1. **בחר קבוצת מזהמים** בסרגל הצד
        2. **בחר או העלה קובץ** נתונים
        3. **לחץ "טען נתונים"**
        4. צפה בסיכום התחנות, טווח תאריכים והנתונים הגולמיים

        ---
        *👈 התחל מהסרגל השמאלי*
        """
    )

else:
    df = st.session_state.df
    group_name = st.session_state.group_name
    group = get_group(group_name)
    file_name = st.session_state.file_name

    st.title(f"סקירת נתונים — {group.name}")
    st.caption(f"קובץ: {file_name}")

    # --- Summary metrics ---
    n_stations = df["station_name"].nunique()

    date_min = date_max = None
    if "sample_date" in df.columns:
        dates = df["sample_date"].dropna()
        if len(dates) > 0:
            date_min = dates.min()
            date_max = dates.max()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("תחנות", n_stations)
    with col2:
        st.metric("שורות נתונים", f"{len(df):,}")
    with col3:
        if "compound" in df.columns:
            st.metric("תרכובות", df["compound"].nunique())
        else:
            st.metric("תרכובות", "—")
    with col4:
        if date_min and date_max:
            st.metric("טווח תאריכים", f"{date_min:%d/%m/%Y} — {date_max:%d/%m/%Y}")
        else:
            st.metric("טווח תאריכים", "—")

    st.divider()

    # --- Raw data table ---
    st.subheader("נתונים גולמיים")
    st.dataframe(df, use_container_width=True, hide_index=True)


# =============================================================================
# Footer
# =============================================================================
st.sidebar.divider()
st.sidebar.caption(
    f"כל הנתונים נשארים על המחשב שלך.\n"
    f"רק תמונות רקע של המפה נטענות מהאינטרנט."
)
