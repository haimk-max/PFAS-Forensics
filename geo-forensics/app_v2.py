"""דשבורד GeoForensics v2 — עיצוב Claude Design Clinical.

streamlit run app_v2.py
"""

import html
import os
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from config import (
    APP_DESCRIPTION, APP_NAME, APP_VERSION, COMPOUND_COLORS, DATA_DIR,
    DEFAULT_COLOR, DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM, PAGE_ICON,
    PFAS_COMPOUND_ORDER, SOURCE_COLORS, SUPPORTED_EXTENSIONS,
)
from src.analytics import cosine_similarity_matrix, generate_findings_summary
from src.contaminant_groups import list_groups
from src.data_model import (
    build_fingerprint_matrix,
    calc_total_concentration,
    get_station_summary,
    process_file,
)
from src.geo_utils import calc_distance, point_in_polygon


# =============================================================================
# Page Config
# =============================================================================
st.set_page_config(
    page_title=f"{APP_NAME} v2",
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Fonts ---
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Assistant:wght@400;500;600;700&family=Frank+Ruhl+Libre:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

# --- Design System CSS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;500;600;700&family=Frank+Ruhl+Libre:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ---- Design Tokens (Clinical) ---- */
:root {
    --bg: #f5f3ee;
    --bg-2: #ebe7df;
    --surface: #ffffff;
    --surface-2: #faf8f4;
    --ink: #1c1f24;
    --ink-2: #4a4f57;
    --ink-3: #7d8189;
    --line: #e2ddd2;
    --line-2: #d4cdbe;
    --accent: #2a9d8f;
    --accent-2: #e07b39;
    --warn: #d97a2c;
    --ok: #2d8b5e;
    --high: #7a3d9e;
    --sim-90: #1f7a4d;
    --sim-70: #4ea66b;
    --sim-30: #d8c84a;
    --sim-low: #c64a3b;
    --radius: 4px;
    --radius-lg: 6px;
    --shadow-sm: 0 1px 2px rgba(28,31,36,0.05);
    --font-sans: "Assistant", system-ui, sans-serif;
    --font-display: "Frank Ruhl Libre", Georgia, serif;
    --font-mono: "JetBrains Mono", ui-monospace, monospace;
}

/* ---- Base ---- */
html, body, .stApp {
    direction: rtl;
    background: var(--bg) !important;
    font-family: var(--font-sans) !important;
    color: var(--ink);
}
.stApp * { font-family: var(--font-sans) !important; }
.stMarkdown, .stText { text-align: right; }
.stDataFrame { direction: ltr; }
input[type="number"] { direction: ltr; text-align: left; }

/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-left: 1px solid var(--line) !important;
    direction: rtl;
}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stFileUploader label,
section[data-testid="stSidebar"] .stMultiSelect label { text-align: right; }

/* Multiselect chips */
section[data-testid="stSidebar"] [data-baseweb="tag"] {
    background-color: color-mix(in srgb, var(--accent) 12%, white) !important;
    border: 1px solid color-mix(in srgb, var(--accent) 30%, white) !important;
    border-radius: 100px !important;
    color: var(--ink-2) !important;
    padding: 2px 8px !important;
    font-size: 0.81em !important;
    height: auto !important;
    min-height: 22px !important;
}
section[data-testid="stSidebar"] [data-baseweb="tag"] span { color: var(--ink-2) !important; }
section[data-testid="stSidebar"] [data-baseweb="tag"] [role="presentation"],
section[data-testid="stSidebar"] [data-baseweb="tag"] svg { fill: var(--ink-3) !important; }
section[data-testid="stSidebar"] [data-baseweb="tag"]:hover [role="presentation"] { fill: #d32f2f !important; }
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: var(--surface-2) !important;
    border-color: var(--line-2) !important;
}

/* ---- Main content area ---- */
.main > .block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 100% !important;
}

/* ---- Tabs ---- */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: var(--surface);
    border-bottom: 1px solid var(--line);
    padding: 0 4px;
    gap: 0;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-family: var(--font-sans) !important;
    font-size: 13px;
    color: var(--ink-3);
    background: transparent;
    border-bottom: 2px solid transparent;
    padding: 10px 16px;
    margin-bottom: -1px;
}
[data-testid="stTabs"] [data-baseweb="tab"]:hover { color: var(--ink-2); }
[data-testid="stTabs"] [aria-selected="true"] {
    color: var(--ink) !important;
    border-bottom-color: var(--accent) !important;
    font-weight: 600;
    background: transparent !important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: transparent !important; }
[data-testid="stTabs"] [data-baseweb="tab-border"] { background: var(--line) !important; }

/* ---- Panel ---- */
.v2-panel {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    padding: 22px 24px;
    margin-bottom: 20px;
}
.v2-panel-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 18px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--line);
    direction: rtl;
}
.v2-panel-num {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-3);
    letter-spacing: 0.1em;
    margin-bottom: 3px;
    text-transform: uppercase;
}
.v2-panel-title {
    font-family: var(--font-display);
    font-size: 20px;
    font-weight: 600;
    margin: 0;
    letter-spacing: -0.01em;
    color: var(--ink);
}
.v2-panel-sub {
    font-size: 12.5px;
    color: var(--ink-2);
    margin-top: 4px;
    max-width: 60ch;
}

/* ---- App header ---- */
.v2-app-header {
    background: var(--surface);
    border-bottom: 1px solid var(--line);
    padding: 14px 0 14px 0;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    direction: rtl;
}
.v2-brand {
    display: flex;
    align-items: center;
    gap: 10px;
}
.v2-brand-mark {
    width: 38px; height: 38px;
    border-radius: var(--radius);
    background: var(--ink);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    flex-shrink: 0;
}
.v2-brand-name {
    font-family: var(--font-display);
    font-size: 18px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--ink);
}
.v2-brand-sub {
    font-size: 11px;
    color: var(--ink-3);
    margin-top: -2px;
}
.v2-meta-bar {
    display: flex;
    gap: 20px;
    font-size: 12px;
    color: var(--ink-2);
    margin-right: auto;
}
.v2-meta .dim { color: var(--ink-3); margin-left: 5px; }

/* ---- KPI Strip ---- */
.v2-kpi-strip {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 16px;
    direction: rtl;
}
.v2-kpi-card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    padding: 18px 20px;
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow-sm);
}
.v2-kpi-card::before {
    content: '';
    position: absolute;
    top: 0; right: 0; bottom: 0;
    width: 3px;
}
.v2-kpi-a::before { background: #2a9d8f; }
.v2-kpi-b::before { background: #e07b39; }
.v2-kpi-c::before { background: #7a3d9e; }
.v2-kpi-d::before { background: #2d8b5e; }
.v2-kpi-label {
    font-size: 11px;
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 10px;
}
.v2-kpi-value {
    font-family: var(--font-display);
    font-size: 32px;
    font-weight: 600;
    line-height: 1;
    letter-spacing: -0.02em;
    color: var(--ink);
}
.v2-kpi-value.mono {
    font-family: var(--font-mono);
    font-size: 16px;
    font-weight: 500;
    letter-spacing: 0;
}
.v2-kpi-unit {
    font-size: 11px;
    color: var(--ink-3);
    margin-top: 6px;
}

/* ---- Insights ---- */
.v2-section-title {
    font-family: var(--font-display);
    font-size: 16px;
    font-weight: 600;
    color: var(--ink);
    margin: 0 0 10px 0;
    direction: rtl;
}
.v2-insight-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin-bottom: 20px;
    direction: rtl;
}
.v2-insight-card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    padding: 14px 16px;
    border-top: 3px solid var(--accent);
    box-shadow: var(--shadow-sm);
}
.v2-insight-card.tone-warn { border-top-color: var(--warn); }
.v2-insight-card.tone-ok   { border-top-color: var(--ok); }
.v2-insight-card.tone-high { border-top-color: var(--high); }
.v2-insight-kicker {
    font-size: 10.5px;
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 6px;
}
.v2-insight-main {
    font-family: var(--font-display);
    font-size: 17px;
    font-weight: 600;
    line-height: 1.2;
    color: var(--ink);
    word-break: break-word;
}
.v2-insight-detail {
    font-family: var(--font-mono);
    font-size: 11.5px;
    color: var(--ink-2);
    margin-top: 6px;
}

/* ---- Caveat ---- */
.v2-caveat {
    background: color-mix(in srgb, #d97a2c 8%, white);
    border: 1px solid color-mix(in srgb, #d97a2c 30%, #e2ddd2);
    padding: 10px 14px 10px 14px;
    border-radius: var(--radius);
    display: flex;
    align-items: flex-start;
    gap: 10px;
    font-size: 12.5px;
    color: var(--ink-2);
    line-height: 1.55;
    margin-top: 12px;
    direction: rtl;
}
.v2-caveat-icon {
    width: 22px; height: 22px;
    border-radius: 50%;
    background: var(--warn);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 13px;
    flex-shrink: 0;
}

/* ---- Success banner ---- */
.v2-success {
    background: color-mix(in srgb, var(--ok) 10%, white);
    border: 1px solid color-mix(in srgb, var(--ok) 30%, #e2ddd2);
    border-radius: var(--radius);
    padding: 8px 12px;
    color: var(--ok);
    font-size: 0.88em;
    direction: rtl;
    margin: 6px 0;
}

/* ---- Similarity legend pills ---- */
.v2-sim-legend {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    direction: rtl;
    margin: 8px 0 14px 0;
}
.v2-sim-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 10px;
    border-radius: 100px;
    font-size: 11px;
    border: 1px solid var(--line-2);
    background: var(--surface-2);
    font-family: var(--font-mono);
}
.v2-sim-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    display: inline-block;
    flex-shrink: 0;
}

/* ---- Findings ---- */
.v2-finding {
    background: var(--surface-2);
    border-radius: var(--radius);
    border-right: 3px solid var(--accent);
    padding: 11px 14px;
    margin-bottom: 8px;
    direction: rtl;
    font-size: 13px;
    line-height: 1.55;
}
.v2-finding.tone-warn { border-right-color: var(--warn); }
.v2-finding.tone-ok   { border-right-color: var(--ok); }

/* ---- Method box ---- */
.v2-method {
    background: var(--surface-2);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 14px 16px;
    font-size: 12.5px;
    line-height: 1.7;
    direction: rtl;
    color: var(--ink-2);
}
.v2-method b { color: var(--ink); }
.v2-method code {
    background: var(--bg-2);
    padding: 1px 5px;
    border-radius: 3px;
    font-family: var(--font-mono);
    font-size: 11.5px;
    direction: ltr;
    unicode-bidi: embed;
}

/* ---- Plotly card ---- */
[data-testid="stPlotlyChart"] {
    background: var(--surface);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    padding: 4px;
}

/* ---- Folium map ---- */
[data-testid="stCustomComponentV1"] iframe,
.element-container iframe { border-radius: var(--radius-lg); }

/* ---- Dataframe ---- */
[data-testid="stDataFrame"] {
    border-radius: var(--radius-lg);
    overflow: hidden;
    box-shadow: var(--shadow-sm);
}

/* ---- Streamlit metric override ---- */
[data-testid="stMetric"] { text-align: center; direction: rtl; }
[data-testid="stMetricLabel"] { justify-content: center; }
[data-testid="stMetricValue"] {
    font-family: var(--font-display) !important;
    letter-spacing: -0.02em;
}

/* ---- Scrollbar ---- */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--line-2); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--ink-3); }

/* ---- divider ---- */
hr { border-color: var(--line) !important; margin: 10px 0 !important; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# Helpers
# =============================================================================
def _list_data_files() -> list[str]:
    data_path = os.path.join(os.path.dirname(__file__), DATA_DIR)
    if not os.path.isdir(data_path):
        return []
    return sorted(
        f for f in os.listdir(data_path)
        if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
    )


def _get_color(compound: str) -> str:
    return COMPOUND_COLORS.get(compound, DEFAULT_COLOR)


def _get_source_color(source_type: str) -> str:
    return SOURCE_COLORS.get(source_type, DEFAULT_COLOR)


def _short_name(name: str, max_len: int = 18) -> str:
    return name[:max_len] + "…" if len(name) > max_len else name


def _fmt_total(v: float) -> str:
    if v >= 1000:
        return f"{v:.0f}"
    if v >= 100:
        return f"{v:.1f}"
    if v >= 10:
        return f"{v:.2f}"
    return f"{v:.3f}"


def _stations_in_drawing(drawing: dict, max_event: pd.DataFrame) -> list[str]:
    geom = drawing.get("geometry", {})
    geom_type = geom.get("type", "")
    coords = geom.get("coordinates", [])
    matched = []

    if geom_type == "Polygon" and coords:
        ring = coords[0]
        polygon = [(pt[1], pt[0]) for pt in ring]
        for _, row in max_event.iterrows():
            lat, lon = row.get("lat"), row.get("lon")
            if pd.notna(lat) and pd.notna(lon) and point_in_polygon(lat, lon, polygon):
                matched.append(row["station_name"])

    elif geom_type == "Point" and coords:
        center_lon, center_lat = coords[0], coords[1]
        radius_m = drawing.get("properties", {}).get("radius", 0)
        if radius_m <= 0:
            radius_m = 5000
        for _, row in max_event.iterrows():
            lat, lon = row.get("lat"), row.get("lon")
            if pd.notna(lat) and pd.notna(lon):
                dist = calc_distance(center_lat, center_lon, lat, lon)
                if dist <= radius_m:
                    matched.append(row["station_name"])

    return matched


def _panel_head(num: str, title: str, sub: str = "") -> str:
    sub_html = f'<div class="v2-panel-sub">{sub}</div>' if sub else ""
    return f"""<div class="v2-panel-head">
  <div>
    <div class="v2-panel-num">{num}</div>
    <h2 class="v2-panel-title">{title}</h2>
    {sub_html}
  </div>
</div>"""


def _caveat(text: str) -> str:
    return f"""<div class="v2-caveat">
  <div class="v2-caveat-icon">!</div>
  <div>{text}</div>
</div>"""


# =============================================================================
# Session State
# =============================================================================
def init_session_state():
    defaults = {
        "df": None, "group": None, "group_name": None,
        "file_name": None, "file_loaded": False,
        "drawn_stations": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# =============================================================================
# Sidebar — File loading
# =============================================================================
with st.sidebar:
    # Brand in sidebar
    st.markdown(f"""<div class="v2-brand" style="margin-bottom:12px;">
  <div class="v2-brand-mark">🔬</div>
  <div>
    <div class="v2-brand-name">{APP_NAME}</div>
    <div class="v2-brand-sub">v{APP_VERSION} • {APP_DESCRIPTION}</div>
  </div>
</div>""", unsafe_allow_html=True)
    st.divider()

    st.subheader("קבוצת מזהמים")
    groups = list_groups()
    if "PFAS" in groups:
        groups.remove("PFAS")
        groups.insert(0, "PFAS")
    selected_group = st.selectbox("קבוצה", options=groups, index=0, label_visibility="collapsed")

    st.divider()

    st.subheader("מקור נתונים")
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
            chosen_name = st.selectbox("בחר קובץ", options=data_files, index=0)
            chosen_file = os.path.join(os.path.dirname(__file__), DATA_DIR, chosen_name)
        else:
            st.warning(f"לא נמצאו קבצים בתיקייה {DATA_DIR}/")
    else:
        uploaded = st.file_uploader("העלה קובץ", type=["xlsx", "xls", "csv"])
        if uploaded:
            chosen_file = uploaded

    load_clicked = st.button("טען נתונים", use_container_width=True, type="primary")


# =============================================================================
# Load data
# =============================================================================
if load_clicked and chosen_file is not None:
    with st.spinner("טוען ומעבד את הנתונים..."):
        try:
            df, group = process_file(chosen_file, group_name=selected_group)
            st.session_state.df = df
            st.session_state.group = group
            st.session_state.group_name = selected_group
            st.session_state.file_name = (
                chosen_file.name if hasattr(chosen_file, "name")
                else os.path.basename(str(chosen_file))
            )
            st.session_state.file_loaded = True
            st.session_state.drawn_stations = None
            if "stations_ms_v2" in st.session_state:
                del st.session_state["stations_ms_v2"]
            st.rerun()
        except (ValueError, KeyError, FileNotFoundError, pd.errors.EmptyDataError) as e:
            st.error(f"שגיאה בטעינת הקובץ:\n{e}")

elif load_clicked and chosen_file is None:
    st.warning("יש לבחור קובץ לפני טעינה.")


# =============================================================================
# Welcome screen
# =============================================================================
if not st.session_state.file_loaded:
    st.markdown("""<div style="max-width:520px; margin:60px auto; text-align:center; direction:rtl;">
<div style="font-size:48px; margin-bottom:16px;">🔬</div>
<h1 style="font-family:'Frank Ruhl Libre',Georgia,serif; font-size:2rem; font-weight:600; color:#1c1f24; margin-bottom:8px;">
  PFAS Forensics Dashboard
</h1>
<p style="color:#7d8189; font-size:0.95em; margin-bottom:32px;">
  כלי לניתוח גיאו-פורנזי של מזהמי PFAS — חתימות כימיות, דמיון בין מקורות, PCA ו-MDS
</p>
<div style="background:#ffffff; border:1px solid #e2ddd2; border-radius:8px; padding:24px; text-align:right; box-shadow:0 1px 2px rgba(28,31,36,0.05);">
  <div style="font-weight:600; margin-bottom:12px; color:#1c1f24;">שלבי העבודה:</div>
  <ol style="color:#4a4f57; line-height:2.2; padding-right:20px; margin:0;">
    <li>בחר <b>קבוצת מזהמים</b> בסרגל הצד</li>
    <li>בחר או העלה <b>קובץ Excel</b></li>
    <li>לחץ <b>"טען נתונים"</b></li>
    <li>צפה במפה, גרפים וניתוחים</li>
  </ol>
</div>
</div>""", unsafe_allow_html=True)
    st.stop()


# =============================================================================
# Data loaded
# =============================================================================
df = st.session_state.df
group = st.session_state.group
file_name = st.session_state.file_name

totals_all = calc_total_concentration(df, group)
max_event_all = (
    totals_all
    .loc[totals_all.groupby("station_name")["total_concentration"].idxmax()]
    .sort_values("total_concentration", ascending=False)
)


# =============================================================================
# Sidebar — Station selection
# =============================================================================
with st.sidebar:
    st.markdown('<div class="v2-success">✓ הנתונים נטענו בהצלחה</div>', unsafe_allow_html=True)
    st.divider()
    st.subheader("תחנות דיגום")

    all_source_types = sorted(df["source_type"].dropna().unique())
    if all_source_types:
        selected_source_types = st.multiselect(
            "סנן לפי סוג מקור",
            options=all_source_types,
            default=all_source_types,
        )
        available_stations = sorted(
            df[df["source_type"].isin(selected_source_types)]["station_name"].unique()
        ) if selected_source_types else sorted(df["station_name"].unique())
    else:
        available_stations = sorted(df["station_name"].unique())
        selected_source_types = []

    col_all, col_clear = st.columns(2)
    with col_all:
        if st.button("בחר הכל", use_container_width=True):
            st.session_state["stations_ms_v2"] = list(available_stations)
            st.session_state.drawn_stations = None
            st.rerun()
    with col_clear:
        if st.button("נקה הכל", use_container_width=True):
            st.session_state["stations_ms_v2"] = []
            st.session_state.drawn_stations = None
            st.rerun()

    if "stations_ms_v2" in st.session_state:
        valid = [s for s in st.session_state["stations_ms_v2"] if s in available_stations]
        if len(valid) != len(st.session_state["stations_ms_v2"]):
            st.session_state["stations_ms_v2"] = valid

    selected_stations = st.multiselect(
        f"תחנות ({len(available_stations)} זמינות)",
        options=available_stations,
        key="stations_ms_v2",
    )

    total_stations = df["station_name"].nunique()
    n_selected = len(st.session_state.drawn_stations) if st.session_state.drawn_stations else len(selected_stations)
    if n_selected > 0:
        st.caption(f"**{n_selected} מתוך {total_stations}** נבחרו")
    else:
        st.caption(f"כל {total_stations} התחנות מוצגות")


# =============================================================================
# Filter + analytics
# =============================================================================
effective_stations = selected_stations or []
if st.session_state.drawn_stations:
    effective_stations = st.session_state.drawn_stations

df_filtered = df[df["station_name"].isin(effective_stations)].copy() if effective_stations else df.copy()

totals_filtered = calc_total_concentration(df_filtered, group)
max_event_filtered = (
    totals_filtered
    .loc[totals_filtered.groupby("station_name")["total_concentration"].idxmax()]
    .sort_values("total_concentration", ascending=False)
)
fingerprint = build_fingerprint_matrix(df_filtered, group)
if st.session_state.group_name == "PFAS":
    ordered = [c for c in PFAS_COMPOUND_ORDER if c in fingerprint.columns]
    remaining = [c for c in fingerprint.columns if c not in ordered]
    fingerprint = fingerprint[ordered + remaining]
sim_matrix = cosine_similarity_matrix(df_filtered, group)
station_summary = get_station_summary(df_filtered)

_nz_mask = max_event_filtered["total_concentration"] > 0
max_event_nonzero = max_event_filtered[_nz_mask]
zero_stn_names = set(max_event_filtered.loc[~_nz_mask, "station_name"])
fingerprint_nonzero = fingerprint.loc[~fingerprint.index.isin(zero_stn_names)]
if zero_stn_names:
    _nz_keep = [s for s in sim_matrix.index if s not in zero_stn_names]
    sim_matrix_nonzero = sim_matrix.loc[_nz_keep, _nz_keep]
else:
    sim_matrix_nonzero = sim_matrix


# =============================================================================
# App Header
# =============================================================================
n_stations = df_filtered["station_name"].nunique()
n_compounds = df_filtered["compound"].nunique() if "compound" in df_filtered.columns else 0
dates = df_filtered["sample_date"].dropna()
date_min = dates.min() if len(dates) > 0 else None
date_max = dates.max() if len(dates) > 0 else None
_date_valid = date_min is not None and date_max is not None and date_min.year >= 1980
_date_str = f"{date_min:%d/%m/%Y} — {date_max:%d/%m/%Y}" if _date_valid else "לא זוהה"

st.markdown(f"""<div class="v2-app-header">
  <div class="v2-brand">
    <div class="v2-brand-mark">🔬</div>
    <div>
      <div class="v2-brand-name">ניתוח {html.escape(group.name)}</div>
      <div class="v2-brand-sub">{html.escape(file_name)}</div>
    </div>
  </div>
  <div class="v2-meta-bar">
    <span class="v2-meta"><span class="dim">תחנות</span>{n_stations}</span>
    <span class="v2-meta"><span class="dim">תרכובות</span>{n_compounds}</span>
    <span class="v2-meta"><span class="dim">עודכן</span>{_date_str}</span>
  </div>
</div>""", unsafe_allow_html=True)


# =============================================================================
# KPI Strip
# =============================================================================
n_rows = len(df_filtered)
_top_stn = max_event_nonzero.iloc[0]["station_name"] if not max_event_nonzero.empty else "—"
_top_val = max_event_nonzero.iloc[0]["total_concentration"] if not max_event_nonzero.empty else 0

st.markdown(f"""<div class="v2-kpi-strip">
  <div class="v2-kpi-card v2-kpi-a">
    <div class="v2-kpi-label">תחנות</div>
    <div class="v2-kpi-value">{n_stations}</div>
    <div class="v2-kpi-unit">נקודות דיגום</div>
  </div>
  <div class="v2-kpi-card v2-kpi-b">
    <div class="v2-kpi-label">שורות נתונים</div>
    <div class="v2-kpi-value">{n_rows:,}</div>
    <div class="v2-kpi-unit">רשומות</div>
  </div>
  <div class="v2-kpi-card v2-kpi-c">
    <div class="v2-kpi-label">תרכובות</div>
    <div class="v2-kpi-value">{n_compounds}</div>
    <div class="v2-kpi-unit">{group.name}</div>
  </div>
  <div class="v2-kpi-card v2-kpi-d">
    <div class="v2-kpi-label">טווח תאריכים</div>
    <div class="v2-kpi-value mono">{_date_str}</div>
  </div>
</div>""", unsafe_allow_html=True)


# =============================================================================
# Insights Row
# =============================================================================
if not max_event_nonzero.empty:
    _n_detected = len(max_event_nonzero)
    _n_total_stn = len(max_event_filtered)
    _detect_rate = f"{_n_detected}/{_n_total_stn}"

    _dominant = "—"
    _dominant_pct = 0.0
    if not fingerprint_nonzero.empty:
        _mean_fp = fingerprint_nonzero.mean()
        _dominant = _mean_fp.idxmax()
        _dominant_pct = _mean_fp.max()

    _top_pair = "—"
    _top_pair_val = 0.0
    _n_high_pairs = 0
    if not sim_matrix_nonzero.empty and len(sim_matrix_nonzero) >= 2:
        _sim_vals = sim_matrix_nonzero.values
        _sim_idx = sim_matrix_nonzero.index.tolist()
        _best_v = -1
        for _i in range(len(_sim_vals)):
            for _j in range(_i + 1, len(_sim_vals)):
                _v = _sim_vals[_i, _j]
                if _v >= 90:
                    _n_high_pairs += 1
                if _v > _best_v:
                    _best_v = _v
                    _top_pair = f"{_sim_idx[_i]} · {_sim_idx[_j]}"
                    _top_pair_val = _v

    st.markdown(f"""<div class="v2-section-title">תובנות מרכזיות</div>
<div class="v2-insight-grid">
  <div class="v2-insight-card tone-warn">
    <div class="v2-insight-kicker">Σ{group.name} מקסימלי</div>
    <div class="v2-insight-main">{html.escape(str(_top_stn))}</div>
    <div class="v2-insight-detail">{_top_val:.2f} {group.unit}</div>
  </div>
  <div class="v2-insight-card tone-ok">
    <div class="v2-insight-kicker">שיעור גילוי</div>
    <div class="v2-insight-main">{_detect_rate}</div>
    <div class="v2-insight-detail">תחנות עם {group.name} &gt;LOD</div>
  </div>
  <div class="v2-insight-card">
    <div class="v2-insight-kicker">תרכובת דומיננטית</div>
    <div class="v2-insight-main">{html.escape(str(_dominant))}</div>
    <div class="v2-insight-detail">{_dominant_pct:.1f}% ממוצע</div>
  </div>
  <div class="v2-insight-card tone-high">
    <div class="v2-insight-kicker">זוג דומה ביותר</div>
    <div class="v2-insight-main" style="font-size:13px;">{html.escape(_top_pair)}</div>
    <div class="v2-insight-detail">{_top_pair_val:.0f}% דמיון</div>
  </div>
  <div class="v2-insight-card">
    <div class="v2-insight-kicker">זוגות ≥90% דמיון</div>
    <div class="v2-insight-main">{_n_high_pairs}</div>
    <div class="v2-insight-detail">זוגות חשודים במקור משותף</div>
  </div>
</div>""", unsafe_allow_html=True)


# =============================================================================
# Section Tabs
# =============================================================================
tab_map, tab_conc, tab_fp, tab_sim, tab_pca, tab_findings, tab_raw = st.tabs([
    "🗺 מפה",
    "📊 ריכוז סכומי",
    "🧪 הרכב יחסי",
    "🔗 דמיון",
    "📐 PCA / MDS",
    "📋 ממצאים",
    "🗂 נתונים גולמיים",
])


# ─── TAB: Map ────────────────────────────────────────────────────────────────
with tab_map:
    st.markdown(_panel_head(
        "01", "מפת נקודות הדיגום",
        f"בחרו תחנות מהמפה או מהרשימה כדי להשוות בין חתימות {group.name}."
    ), unsafe_allow_html=True)

    try:
        import folium
        from folium.plugins import Draw
        from streamlit_folium import st_folium

        m = folium.Map(location=DEFAULT_MAP_CENTER, zoom_start=DEFAULT_MAP_ZOOM)
        Draw(
            export=False,
            position="topleft",
            draw_options={
                "polyline": False,
                "polygon": {"allowIntersection": False, "shapeOptions": {"color": "#2a9d8f"}},
                "circle": {"shapeOptions": {"color": "#2a9d8f"}},
                "rectangle": {"shapeOptions": {"color": "#2a9d8f"}},
                "marker": False,
                "circlemarker": False,
            },
        ).add_to(m)

        selected_set = set(effective_stations) if effective_stations else set()
        has_selection = len(selected_set) > 0

        for _, row in max_event_all.iterrows():
            lat, lon = row.get("lat"), row.get("lon")
            if pd.isna(lat) or pd.isna(lon):
                continue

            station_name = row["station_name"]
            source_type = row.get("source_type", "")
            total = row["total_concentration"]
            is_selected = station_name in selected_set or not has_selection
            is_zero = total == 0

            if is_selected and not is_zero:
                color = _get_source_color(source_type)
                opacity = 0.85
                radius = max(6, min(20, 6 + 4 * np.log10(max(total, 0.01) + 1)))
                tooltip = folium.Tooltip(station_name, permanent=False, sticky=True)
                _lbl = (
                    f'<div style="font-size:11px;font-weight:700;color:#1c1f24;'
                    f'text-shadow:-1px -1px 0 #fff,1px -1px 0 #fff,-1px 1px 0 #fff,1px 1px 0 #fff;'
                    f'white-space:nowrap;pointer-events:none;background:transparent;border:none;'
                    f'font-family:Assistant,sans-serif;">'
                    f'{html.escape(station_name)}</div>'
                )
                folium.Marker(
                    location=[lat, lon],
                    icon=folium.DivIcon(html=_lbl, icon_size=(160, 20), icon_anchor=(-8, 10), class_name="stn-lbl-icon"),
                ).add_to(m)
            elif is_zero:
                color = "#c8c4bc"
                opacity = 0.25
                radius = 4
                tooltip = folium.Tooltip(station_name, permanent=False, sticky=False)
            else:
                color = "#9e9b94"
                opacity = 0.35
                radius = 5
                tooltip = folium.Tooltip(station_name, permanent=False, sticky=False)

            popup_html = f"""<div style="direction:rtl; text-align:right; min-width:200px;
              font-family:Assistant,sans-serif; font-size:13px;">
              <b>{html.escape(station_name)}</b><br>
              סוג: {html.escape(source_type)}<br>
              Σ{group.name}: {total:.3f} {group.unit}<br>
              תאריך: {row['sample_date']:%d/%m/%Y}
            </div>"""
            folium.CircleMarker(
                location=[lat, lon],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=opacity,
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=tooltip,
            ).add_to(m)

        lats = max_event_all["lat"].dropna()
        lons = max_event_all["lon"].dropna()
        if len(lats) > 0:
            m.fit_bounds([[lats.min(), lons.min()], [lats.max(), lons.max()]])

        from branca.element import Element as _Elem
        _mid = m._id
        m.get_root().html.add_child(_Elem(f"""<script>
(function(){{
    var _t=0;
    function _init(){{
        var _m=window['map_{_mid}'];
        if(!_m){{if(++_t<40)setTimeout(_init,150);return;}}
        function _upd(){{
            var z=_m.getZoom();
            var c=document.getElementById('map_{_mid}');
            if(!c)return;
            var tt=Array.from(c.querySelectorAll('.stn-lbl-icon'));
            if(z<11){{tt.forEach(function(t){{t.style.opacity='0';}});return;}}
            var placed=[];
            var cr=c.getBoundingClientRect();
            tt.forEach(function(t){{
                var r=t.getBoundingClientRect();
                var b={{l:r.left-cr.left,r:r.right-cr.left,t:r.top-cr.top,b:r.bottom-cr.top}};
                var ov=placed.some(function(p){{
                    return b.l<p.r+2&&b.r>p.l-2&&b.t<p.b+2&&b.b>p.t-2;
                }});
                t.style.opacity=ov?'0':'1';
                if(!ov)placed.push(b);
            }});
        }}
        _m.on('zoomend moveend',_upd);
        setTimeout(_upd,600);
    }}
    _init();
}})();
</script>"""))

        map_data = st_folium(
            m, width=None, height=520, use_container_width=True,
            returned_objects=["all_drawings", "last_active_drawing"],
        )

        drawings = map_data.get("all_drawings") if map_data else None
        if drawings:
            drawn_names = []
            for d in drawings:
                drawn_names.extend(_stations_in_drawing(d, max_event_all))
            if drawn_names:
                unique_drawn = sorted(set(drawn_names))
                if unique_drawn != (st.session_state.drawn_stations or []):
                    st.session_state.drawn_stations = unique_drawn
                    st.rerun()
                else:
                    st.success(f"נבחרו {len(unique_drawn)} תחנות דרך ציור על המפה")
        elif map_data and map_data.get("all_drawings") == []:
            if st.session_state.drawn_stations is not None:
                st.session_state.drawn_stations = None
                st.rerun()

        col_legend, col_clear_map = st.columns([4, 1])
        with col_clear_map:
            if st.session_state.drawn_stations and st.button("נקה בחירה"):
                st.session_state.drawn_stations = None
                st.rerun()
        with col_legend:
            legend_items = []
            for src, clr in SOURCE_COLORS.items():
                if src in df["source_type"].values:
                    legend_items.append(
                        f'<span style="display:inline-block;width:10px;height:10px;'
                        f'background:{clr};border-radius:50%;margin-left:5px;"></span> {html.escape(src)}'
                    )
            if legend_items:
                st.markdown(
                    '<span style="font-size:12px; color:#7d8189;">' +
                    " &nbsp;|&nbsp; ".join(legend_items) + "</span>",
                    unsafe_allow_html=True
                )

    except ImportError:
        st.warning("חסרות חבילות folium / streamlit-folium. התקן: pip install folium streamlit-folium")


# ─── TAB: Total Concentration ─────────────────────────────────────────────────
with tab_conc:
    st.markdown(_panel_head(
        "02", f"ריכוז סכומי — {group.name}",
        "סכום ריכוזי כל התרכובות בכל תחנה (אירוע מקסימלי), בסקאלה לוגריתמית."
    ), unsafe_allow_html=True)

    with st.expander("מתודולוגיה", expanded=False):
        st.markdown("""<div class="v2-method">
<b>עיקרון:</b> סיכום ריכוזי כל התרכובות בכל תחנה להשוואת עומס הזיהום הכולל.<br>
<b>נוסחה:</b> <code>Σ = Σᵢ Cᵢ</code><br>
<b>חולשות:</b> לא מבחין בין תרכובות — תחנה עם תרכובת דומיננטית אחת ותחנה עם פיזור שווה יכולות להראות ריכוז זהה.
</div>""", unsafe_allow_html=True)

    if not max_event_nonzero.empty:
        _top_stn_s2 = html.escape(str(max_event_nonzero.iloc[0]["station_name"]))
        _top_val_s2 = max_event_nonzero.iloc[0]["total_concentration"]
        st.markdown(f"""<div style="background:color-mix(in srgb,#2a9d8f 8%,white);
          border:1px solid color-mix(in srgb,#2a9d8f 25%,#e2ddd2);
          border-radius:4px; padding:10px 14px; font-size:13px;
          color:#1c1f24; direction:rtl; margin-bottom:12px;">
          תחנה מובילה: <b>{_top_stn_s2}</b> — Σ{group.name} = <b>{_top_val_s2:.2f} {group.unit}</b>
        </div>""", unsafe_allow_html=True)

        _names_s2 = max_event_nonzero["station_name"].tolist()
        _short_names_s2 = [_short_name(n) for n in _names_s2]
        colors_s2 = [_get_source_color(s) for s in max_event_nonzero["source_type"]]

        fig_atten = go.Figure()
        fig_atten.add_trace(go.Bar(
            x=_short_names_s2,
            y=max_event_nonzero["total_concentration"],
            marker_color=colors_s2,
            marker_line_width=0,
            text=[_fmt_total(v) for v in max_event_nonzero["total_concentration"]],
            textposition="outside",
            customdata=_names_s2,
            hovertemplate="<b>%{customdata}</b><br>Σ" + group.name + ": %{y:.3f} " + group.unit + "<extra></extra>",
        ))
        fig_atten.update_layout(
            xaxis_title="תחנה",
            yaxis_title=f"ריכוז ({group.unit})",
            yaxis_type="log",
            height=480,
            template="plotly_white",
            font=dict(family="Assistant, sans-serif", size=13),
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
        )
        st.plotly_chart(fig_atten, use_container_width=True)
        st.markdown(_caveat(
            "הריכוז הסכומי משקף עומס זיהום נקודתי — אינו מעיד בהכרח על מקור משותף."
        ), unsafe_allow_html=True)
    else:
        st.info("אין נתוני ריכוז להצגה.")


# ─── TAB: Fingerprint ─────────────────────────────────────────────────────────
with tab_fp:
    st.markdown(_panel_head(
        "03", f"הרכב יחסי — {group.name}",
        "כל עמודה מייצגת תחנה; מקטעי העמודה — תרומה יחסית של כל תרכובת לסך הריכוז."
    ), unsafe_allow_html=True)

    with st.expander("מתודולוגיה", expanded=False):
        st.markdown("""<div class="v2-method">
<b>עיקרון:</b> נרמול ההרכב הכימי של כל תחנה ל-100% להשוואת פרופילים ללא תלות בריכוז המוחלט.<br>
<b>נוסחה:</b> <code>%ᵢ = (Cᵢ / Σ) × 100</code><br>
<b>חולשות:</b> מאבד מידע על גודל מוחלט; תרכובות מתחת ל-LOD עלולות להטות את ההרכב.
</div>""", unsafe_allow_html=True)

    if not fingerprint.empty:
        fig_fp = go.Figure()
        compounds = fingerprint.columns.tolist()
        stations = fingerprint.index.tolist()
        _short_stations_fp = [_short_name(s) for s in stations]

        for compound in compounds:
            fig_fp.add_trace(go.Bar(
                name=compound,
                x=_short_stations_fp,
                y=fingerprint[compound],
                marker_color=_get_color(compound),
                marker_line_width=0,
                customdata=[compound] * len(stations),
                hovertemplate="<b>" + html.escape(compound) + "</b><br>%{x}: %{y:.1f}%<extra></extra>",
            ))

        total_lookup = max_event_filtered.set_index("station_name")["total_concentration"]
        annotations_fp = []
        for idx, stn in enumerate(stations):
            total_val = total_lookup.get(stn, 0)
            annotations_fp.append(dict(
                x=_short_stations_fp[idx], y=100, text=_fmt_total(total_val),
                showarrow=False, yshift=12,
                font=dict(size=10, color="#7d8189"),
            ))

        fig_fp.update_layout(
            barmode="stack",
            xaxis_title="תחנה",
            yaxis_title="אחוז (%)",
            yaxis=dict(range=[0, 100]),
            height=480,
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            font=dict(family="Assistant, sans-serif", size=13),
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
            annotations=annotations_fp,
        )
        st.plotly_chart(fig_fp, use_container_width=True)
        st.markdown(_caveat(
            "הרכב יחסי תלוי בקיום מספיק תרכובות מעל סף הזיהוי (LOD)."
        ), unsafe_allow_html=True)
    else:
        st.info("אין מספיק נתונים לבניית fingerprint.")


# ─── TAB: Similarity ──────────────────────────────────────────────────────────
with tab_sim:
    st.markdown(_panel_head(
        "04", f"דמיון בין חתימות {group.name}",
        "מידת הדמיון בין פרופילי התרכובות של כל זוג תחנות (Cosine Similarity)."
    ), unsafe_allow_html=True)

    with st.expander("מתודולוגיה", expanded=False):
        st.markdown("""<div class="v2-method">
<b>עיקרון:</b> מדידת הזווית בין וקטורי ההרכב הכימי של שתי תחנות — ללא תלות בריכוז המוחלט.<br>
<b>נוסחה:</b> <code>cos(θ) = (A · B) / (‖A‖ × ‖B‖)</code><br>
<b>חולשות:</b> דמיון גבוה אינו מוכיח מקור משותף; רגיש לתרכובות מתחת ל-LOD.
</div>""", unsafe_allow_html=True)

    st.markdown("""<div class="v2-sim-legend">
<span class="v2-sim-pill"><span class="v2-sim-dot" style="background:#c64a3b;"></span>0–30% נמוך</span>
<span class="v2-sim-pill"><span class="v2-sim-dot" style="background:#d8c84a;"></span>30–70% בינוני</span>
<span class="v2-sim-pill"><span class="v2-sim-dot" style="background:#4ea66b;"></span>70–90% גבוה</span>
<span class="v2-sim-pill"><span class="v2-sim-dot" style="background:#1f7a4d;"></span>90–100% גבוה מאוד</span>
</div>""", unsafe_allow_html=True)

    if not sim_matrix_nonzero.empty and len(sim_matrix_nonzero) >= 2:
        try:
            from scipy.cluster.hierarchy import linkage, leaves_list
            from scipy.spatial.distance import squareform

            dist = 1 - sim_matrix_nonzero.values / 100
            np.fill_diagonal(dist, 0)
            dist = (dist + dist.T) / 2
            condensed = squareform(dist, checks=False)
            Z = linkage(condensed, method="average")
            order = leaves_list(Z)
            ordered_labels = [sim_matrix_nonzero.index[i] for i in order]
            sim_ordered = sim_matrix_nonzero.loc[ordered_labels, ordered_labels]
        except (ValueError, np.linalg.LinAlgError):
            sim_ordered = sim_matrix_nonzero
            ordered_labels = sim_matrix_nonzero.index.tolist()

        # Custom colorscale matching design tokens
        sim_colorscale = [
            [0.0,  "#c64a3b"],
            [0.30, "#d8c84a"],
            [0.70, "#4ea66b"],
            [0.90, "#1f7a4d"],
            [1.0,  "#0d4a2e"],
        ]

        fig_sim = go.Figure(data=go.Heatmap(
            z=sim_ordered.values,
            x=ordered_labels,
            y=ordered_labels,
            colorscale=sim_colorscale,
            zmin=0, zmax=100,
            text=sim_ordered.values.round(0).astype(int),
            texttemplate="%{text}%",
            textfont=dict(size=11, family="JetBrains Mono, monospace", color="white"),
            hovertemplate="<b>%{x}</b> ↔ <b>%{y}</b><br>דמיון: %{z:.1f}%<extra></extra>",
            showscale=False,
        ))
        fig_sim.update_layout(
            height=max(480, len(ordered_labels) * 38 + 150),
            template="plotly_white",
            font=dict(family="Assistant, sans-serif", size=12),
            xaxis=dict(side="bottom"),
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
        )
        st.plotly_chart(fig_sim, use_container_width=True)

        # Top pairs table
        _pairs_s4 = []
        for _i in range(len(sim_matrix_nonzero)):
            for _j in range(_i + 1, len(sim_matrix_nonzero)):
                _v = sim_matrix_nonzero.iloc[_i, _j]
                if _v >= 70:
                    _note = "דמיון גבוה מאוד" if _v >= 90 else "דמיון גבוה"
                    _pairs_s4.append({
                        "תחנה א׳": sim_matrix_nonzero.index[_i],
                        "תחנה ב׳": sim_matrix_nonzero.columns[_j],
                        "דמיון (%)": round(_v, 1),
                        "הערה": _note,
                    })
        _pairs_s4.sort(key=lambda x: -x["דמיון (%)"])
        if _pairs_s4:
            st.markdown("<div style='font-size:13px; font-weight:600; margin:12px 0 8px; direction:rtl;'>זוגות עם דמיון ≥70%</div>", unsafe_allow_html=True)
            st.dataframe(
                pd.DataFrame(_pairs_s4[:12]),
                use_container_width=True,
                hide_index=True,
            )

        st.markdown(_caveat(
            f"דמיון בהרכב {group.name} אינו מוכיח מקור משותף — יש לפרש יחד עם מידע הידרולוגי ומרחבי."
        ), unsafe_allow_html=True)
    else:
        st.info("נדרשות לפחות 2 תחנות עם ריכוז מזוהה.")


# ─── TAB: PCA / MDS ───────────────────────────────────────────────────────────
with tab_pca:
    st.markdown(_panel_head(
        "05", "PCA / MDS — ניתוח מרחבי",
        "הפחתת ממדים של הרכב התרכובות. תחנות קרובות בגרף — הרכב כימי דומה."
    ), unsafe_allow_html=True)

    pca_data = None
    pca_col, mds_col = st.columns(2)

    # --- PCA ---
    with pca_col:
        st.markdown('<div style="font-family:\'Frank Ruhl Libre\',serif; font-size:15px; font-weight:600; margin-bottom:8px; direction:rtl;">PCA — רכיבים ראשיים</div>', unsafe_allow_html=True)
        with st.expander("מתודולוגיה", expanded=False):
            st.markdown("""<div class="v2-method">
<b>עיקרון:</b> הפחתת ממדים ליניארית — ציר X/Y = הוקטורים העצמיים של מטריצת הקווריאנס.<br>
<b>נוסחה:</b> <code>X = T·Pᵀ + E</code><br>
<b>חולשות:</b> מניח קשרים ליניאריים; רגיש לקנה מידה.
</div>""", unsafe_allow_html=True)

        if not fingerprint_nonzero.empty and len(fingerprint_nonzero) >= 2:
            from sklearn.decomposition import PCA

            fp_values = fingerprint_nonzero.values
            n_components = min(2, fp_values.shape[0], fp_values.shape[1])
            pca = PCA(n_components=n_components)
            coords_pca = pca.fit_transform(fp_values)
            var_explained = (pca.explained_variance_ratio_ * 100).tolist()

            pca_data = {
                "stations": fingerprint_nonzero.index.tolist(),
                "pc1": coords_pca[:, 0].tolist(),
                "pc2": coords_pca[:, 1].tolist() if n_components == 2 else [0.0] * len(fingerprint_nonzero),
                "var_explained": var_explained,
            }

            source_types_pca = []
            for stn in pca_data["stations"]:
                st_rows = df_filtered[df_filtered["station_name"] == stn]["source_type"].dropna()
                source_types_pca.append(st_rows.iloc[0] if len(st_rows) > 0 else "")

            fig_pca = go.Figure()
            seen_sources = set()
            for i, stn in enumerate(pca_data["stations"]):
                src = source_types_pca[i]
                color = _get_source_color(src)
                show_legend = src not in seen_sources
                seen_sources.add(src)
                fig_pca.add_trace(go.Scatter(
                    x=[pca_data["pc1"][i]],
                    y=[pca_data["pc2"][i]],
                    mode="markers+text",
                    marker=dict(size=11, color=color, line=dict(width=1.5, color="white")),
                    text=[stn],
                    textposition="top center",
                    textfont=dict(size=10, family="Assistant, sans-serif"),
                    name=src,
                    legendgroup=src,
                    showlegend=show_legend,
                    hovertemplate=f"<b>{html.escape(stn)}</b><br>סוג: {html.escape(src)}<extra></extra>",
                ))

            label_x = f"PC1 ({var_explained[0]:.1f}%)"
            label_y = f"PC2 ({var_explained[1]:.1f}%)" if len(var_explained) > 1 else "PC2"
            fig_pca.update_layout(
                xaxis_title=label_x,
                yaxis_title=label_y,
                height=400,
                template="plotly_white",
                font=dict(family="Assistant, sans-serif", size=12),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                plot_bgcolor="#ffffff",
                paper_bgcolor="#ffffff",
            )
            st.plotly_chart(fig_pca, use_container_width=True)
        else:
            st.info("נדרשות לפחות 2 תחנות עם נתוני ריכוז.")

    # --- MDS ---
    with mds_col:
        st.markdown('<div style="font-family:\'Frank Ruhl Libre\',serif; font-size:15px; font-weight:600; margin-bottom:8px; direction:rtl;">MDS — מיפוי מרחק כימי</div>', unsafe_allow_html=True)
        with st.expander("מתודולוגיה", expanded=False):
            st.markdown("""<div class="v2-method">
<b>עיקרון:</b> מיפוי תחנות כך שמרחקי הגרף משקפים מרחקי Cosine.<br>
<b>נוסחה:</b> <code>min Σᵢⱼ (dᵢⱼ − δᵢⱼ)²</code><br>
<b>חולשות:</b> סיבובים שרירותיים; עלול להיתקע במינימום מקומי.
</div>""", unsafe_allow_html=True)

        if not sim_matrix_nonzero.empty and len(sim_matrix_nonzero) >= 2:
            from sklearn.manifold import MDS

            dist_mds = 1 - sim_matrix_nonzero.values / 100
            np.fill_diagonal(dist_mds, 0)
            dist_mds = (dist_mds + dist_mds.T) / 2

            mds = MDS(n_components=2, metric="precomputed", random_state=42, normalized_stress="auto", n_init=4)
            coords_mds = mds.fit_transform(dist_mds)

            mds_stations = sim_matrix_nonzero.index.tolist()
            source_types_mds = []
            for stn in mds_stations:
                st_rows = df_filtered[df_filtered["station_name"] == stn]["source_type"].dropna()
                source_types_mds.append(st_rows.iloc[0] if len(st_rows) > 0 else "")

            fig_mds = go.Figure()
            seen_sources_mds = set()
            for i, stn in enumerate(mds_stations):
                src = source_types_mds[i]
                color = _get_source_color(src)
                show_legend = src not in seen_sources_mds
                seen_sources_mds.add(src)
                fig_mds.add_trace(go.Scatter(
                    x=[coords_mds[i, 0]],
                    y=[coords_mds[i, 1]],
                    mode="markers+text",
                    marker=dict(size=11, color=color, line=dict(width=1.5, color="white")),
                    text=[stn],
                    textposition="top center",
                    textfont=dict(size=10, family="Assistant, sans-serif"),
                    name=src,
                    legendgroup=src,
                    showlegend=show_legend,
                    hovertemplate=f"<b>{html.escape(stn)}</b><br>סוג: {html.escape(src)}<extra></extra>",
                ))

            fig_mds.update_layout(
                xaxis_title="ציר 1",
                yaxis_title="ציר 2",
                height=400,
                template="plotly_white",
                font=dict(family="Assistant, sans-serif", size=12),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                plot_bgcolor="#ffffff",
                paper_bgcolor="#ffffff",
            )
            st.plotly_chart(fig_mds, use_container_width=True)
        else:
            st.info("נדרשות לפחות 2 תחנות.")

    st.markdown(_caveat(
        "הקרבה בגרף משקפת דמיון בהרכב היחסי — לא בהכרח מקור זיהום משותף. "
        "אחוז שונות נמוך ב-PCA מצביע שהגרף מייצג חלקית בלבד."
    ), unsafe_allow_html=True)


# ─── TAB: Findings ────────────────────────────────────────────────────────────
with tab_findings:
    st.markdown(_panel_head(
        "06", "סיכום ממצאים והערות זהירות",
        "ממצאים אוטומטיים המבוססים על הנתונים שנטענו."
    ), unsafe_allow_html=True)

    findings = generate_findings_summary(df_filtered, group, sim_matrix, pca_data=pca_data)
    if findings:
        for f in findings:
            st.markdown(f'<div class="v2-finding">{f}</div>', unsafe_allow_html=True)
    else:
        st.info("אין מספיק נתונים ליצירת ממצאים.")

    st.markdown(_caveat(
        "כלי זה תומך בניתוח מקצועי אך אינו מחליף שיקול דעת מומחה. "
        "ממצאים מחייבים אימות עם מידע הידרולוגי, גיאוגרפי וכימי משלים."
    ), unsafe_allow_html=True)


# ─── TAB: Raw Data ────────────────────────────────────────────────────────────
with tab_raw:
    st.markdown(_panel_head("07", "נתונים גולמיים"), unsafe_allow_html=True)

    st.subheader("סיכום תחנות")
    st.dataframe(station_summary, use_container_width=True, hide_index=True)

    st.subheader("טבלת נתונים")
    st.dataframe(df_filtered, use_container_width=True, hide_index=True)

    csv = df_filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇ הורד CSV",
        data=csv,
        file_name=f"{group.name}_data.csv",
        mime="text/csv",
    )
