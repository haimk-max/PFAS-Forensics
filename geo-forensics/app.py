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

from config import APP_DESCRIPTION, APP_NAME, APP_VERSION, PAGE_ICON
from src.contaminant_groups import get_group, list_groups
from src.data_model import (
    build_fingerprint_matrix,
    calc_total_concentration,
    get_station_summary,
    process_file,
)

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
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# Session State - שמירת מצב בין ריענוני דף
# =============================================================================
def init_session_state():
    """מאתחל את משתני ה-session אם הם לא קיימים."""
    defaults = {
        "df": None,  # DataFrame מעובד
        "group": None,  # ContaminantGroup
        "file_loaded": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# =============================================================================
# Sidebar - בחירת קבוצת מזהמים והעלאת קובץ
# =============================================================================
with st.sidebar:
    st.title(f"{PAGE_ICON} {APP_NAME}")
    st.caption(f"v{APP_VERSION} | {APP_DESCRIPTION}")
    st.divider()

    # Contaminant group selection
    st.subheader("1. בחר קבוצת מזהמים")
    groups = list_groups()
    selected_group = st.selectbox(
        "קבוצה",
        options=["זיהוי אוטומטי"] + groups,
        help="המערכת תנסה לזהות אוטומטית לפי שמות התרכובות בקובץ",
    )

    st.divider()

    # File upload
    st.subheader("2. העלה קובץ נתונים")
    uploaded_file = st.file_uploader(
        "Excel או CSV",
        type=["xlsx", "xls", "csv"],
        help="קובץ עם עמודות: שם תחנה, X, Y, תאריך דיגום, תרכובת, ריכוז",
    )

    # Quick load sample data
    st.divider()
    use_sample = st.button(
        "📂 טען נתונים לדוגמה",
        help="טוען קובץ סינתטי של PFAS באזור נחל הקישון לצורך הדגמה",
        use_container_width=True,
    )

    if use_sample:
        sample_path = os.path.join(os.path.dirname(__file__), "data", "sample", "sample_pfas.xlsx")
        if os.path.exists(sample_path):
            uploaded_file = sample_path
        else:
            st.error("קובץ הדוגמה לא נמצא. הרץ: python -m src.generate_sample_data")


# =============================================================================
# Process uploaded file
# =============================================================================
if uploaded_file and not st.session_state.file_loaded:
    group_name = None if selected_group == "זיהוי אוטומטי" else selected_group

    with st.spinner("טוען ומעבד את הנתונים..."):
        try:
            df, group = process_file(uploaded_file, group_name)
            st.session_state.df = df
            st.session_state.group = group
            st.session_state.file_loaded = True
            st.rerun()
        except ValueError as e:
            st.error(f"שגיאה בטעינת הקובץ:\n{e}")
        except Exception as e:
            st.error(f"שגיאה לא צפויה:\n{e}")

# Reset when file is removed
if not uploaded_file and st.session_state.file_loaded and not use_sample:
    st.session_state.df = None
    st.session_state.group = None
    st.session_state.file_loaded = False


# =============================================================================
# Main Content
# =============================================================================
if not st.session_state.file_loaded:
    # Welcome screen
    st.title(f"ברוכים הבאים ל-{APP_NAME}")
    st.markdown(
        """
        ### כלי לחקירת מקורות זיהום במים, קרקע ושפכים

        **שלבי העבודה:**
        1. **בחר קבוצת מזהמים** (או זיהוי אוטומטי)
        2. **העלה קובץ** Excel/CSV עם נתוני דיגום
        3. **צפה במפה** ובחר אזור לחקירה
        4. **הפעל כלי ניתוח** - Attenuation, Fingerprint, PCA, Cosine Similarity
        5. **ייצא דוח** HTML עצמאי

        ---

        **דרישות הקובץ:**

        | עמודה | דוגמה |
        |-------|-------|
        | שם תחנה | קידוח K-12 |
        | X (ITM) | 198500 |
        | Y (ITM) | 741200 |
        | תאריך דיגום | 15/03/2024 |
        | סוג מקור | קידוח ניטור |
        | סמל תרכובת | PFOS |
        | ריכוז (µg/L) | 0.85 |

        ---
        *👈 התחל מהסרגל השמאלי - בחר קבוצה והעלה קובץ*
        """
    )

else:
    # Data is loaded - show overview
    df = st.session_state.df
    group = st.session_state.group

    st.title(f"סקירת נתונים - {group.name}")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("תחנות", df["station_name"].nunique())
    with col2:
        st.metric("תרכובות", df["compound"].nunique())
    with col3:
        st.metric("שורות נתונים", len(df))
    with col4:
        source_types = df["source_type"].nunique()
        st.metric("סוגי מקור", source_types)

    st.divider()

    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["📊 סיכום תחנות", "📋 נתונים גולמיים", "🔬 טביעת אצבע"])

    with tab1:
        st.subheader("סיכום לפי תחנות")
        summary = get_station_summary(df)
        st.dataframe(summary, use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("נתונים גולמיים")
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("מטריצת טביעת אצבע כימית (%)")
        fingerprint = build_fingerprint_matrix(df, group)
        st.dataframe(
            fingerprint.style.format("{:.1f}%"),
            use_container_width=True,
        )

    # Total concentrations
    st.divider()
    st.subheader("סה\"כ ריכוזים לפי תחנה")
    totals = calc_total_concentration(df, group)
    totals_display = totals[["station_name", "source_type", "total_concentration", "sample_date"]].copy()
    totals_display = totals_display.sort_values("total_concentration", ascending=False)
    st.dataframe(totals_display, use_container_width=True, hide_index=True)


# =============================================================================
# Footer
# =============================================================================
st.sidebar.divider()
st.sidebar.caption(
    f"🔒 כל הנתונים נשארים על המחשב שלך.\n"
    f"רק תמונות רקע של המפה נטענות מהאינטרנט."
)
