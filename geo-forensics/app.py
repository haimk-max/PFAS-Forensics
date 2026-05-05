"""דשבורד GeoForensics — streamlit run app.py."""

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
    page_title=APP_NAME,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Assistant:wght@300;400;600;700;800&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Assistant:wght@300;400;600;700;800&display=swap');

/* DEBUG: remove after confirming CSS injection works */
section[data-testid="stSidebar"] { border-right: 5px solid red !important; }

/* --- Base RTL + font --- */
html, body, .stApp, .stApp * {
    direction: rtl;
    font-family: 'Assistant', 'Noto Sans Hebrew', 'Arial', system-ui, sans-serif !important;
}
.stMarkdown, .stText { text-align: right; }
.stDataFrame { direction: ltr; }
input[type="number"] { direction: ltr; text-align: left; }
section[data-testid="stSidebar"] { direction: rtl; }
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stFileUploader label,
section[data-testid="stSidebar"] .stMultiSelect label { text-align: right; }

/* --- KPI metric styling inside st.container(border=True) --- */
[data-testid="stMetric"] { text-align: center; direction: rtl; }
[data-testid="stMetricLabel"] { justify-content: center; }
[data-testid="stMetricValue"] { justify-content: center; }

/* --- Caveat note --- */
.caveat-note {
    background: #fefcf3; border: 1px solid #e8e0c8; border-radius: 6px;
    padding: 10px 14px; margin: 10px 0; direction: rtl; text-align: right;
    font-size: 0.88em; color: #6d5f3a; line-height: 1.6; font-style: italic;
}
.caveat-note::before { content: "ℹ "; font-style: normal; }

/* --- Similarity legend pills --- */
.similarity-legend { display: flex; gap: 10px; flex-wrap: wrap; direction: rtl; margin: 8px 0 14px 0; }
.sim-pill {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 4px 10px; border-radius: 12px; font-size: 0.82em;
    border: 1px solid #ddd; background: #fafafa;
}
.sim-pill .sim-dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }

/* --- Success banner --- */
.success-banner {
    background: #edf7ed; border: 1px solid #c3e6c3; border-radius: 6px;
    padding: 8px 12px; direction: rtl; text-align: right;
    color: #2e6b2e; font-size: 0.9em; margin: 6px 0;
}

/* --- Header description --- */
.header-desc { color: #5a6d78; font-size: 0.95em; margin-top: -6px; margin-bottom: 10px; direction: rtl; }

/* --- Section header --- */
.section-header {
    color: #1a8c5e; border-bottom: 2px solid #1a8c5e;
    padding-bottom: 8px; margin-top: 1.5rem;
}
.section-desc { color: #5a6d78; font-size: 0.92em; direction: rtl; margin-bottom: 10px; }

/* --- Insight banner (above chart) --- */
.insight-banner {
    background: #eef6ff; border: 1px solid #c4daf0; border-radius: 6px;
    padding: 10px 14px; direction: rtl; text-align: right;
    font-size: 0.92em; color: #2a5078; margin-bottom: 10px;
}

/* --- Finding card --- */
.finding-card {
    background: #f8f9fa; border-right: 4px solid #3498db;
    padding: 10px 15px; margin: 8px 0; border-radius: 4px;
    direction: rtl; text-align: right;
}

/* --- Method box --- */
.method-box {
    background: #f0f4f8; border: 1px solid #d0d7de; border-radius: 6px;
    padding: 12px 16px; margin: 6px 0 12px 0; direction: rtl; text-align: right;
    font-size: 0.92em; line-height: 1.7;
}
.method-box b { color: #1a5276; }
.method-box code { background: #e8ecf0; padding: 1px 5px; border-radius: 3px; direction: ltr; unicode-bidi: embed; }

/* --- Multiselect tag overrides (full chip hierarchy) --- */
section[data-testid="stSidebar"] [data-baseweb="tag"] {
    background-color: #e8f0fe !important;
    border: 1px solid #c5d6f0 !important;
    border-radius: 14px !important;
    color: #1a3a5c !important;
    padding: 2px 8px !important;
    font-size: 0.82em !important;
    height: auto !important;
    min-height: 24px !important;
}
section[data-testid="stSidebar"] [data-baseweb="tag"] span {
    color: #1a3a5c !important;
    font-weight: 500 !important;
}
section[data-testid="stSidebar"] [data-baseweb="tag"] [role="presentation"],
section[data-testid="stSidebar"] [data-baseweb="tag"] svg {
    fill: #5a6d78 !important;
    color: #5a6d78 !important;
}
section[data-testid="stSidebar"] [data-baseweb="tag"]:hover [role="presentation"] {
    fill: #d32f2f !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #fafbfc !important;
    border-color: #d0d7de !important;
}

/* --- Plotly charts: card styling --- */
[data-testid="stPlotlyChart"] {
    background: #ffffff;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.10);
    padding: 8px 4px 4px 4px;
    margin: 4px 0 14px 0;
}

/* --- Folium map container --- */
[data-testid="stCustomComponentV1"] iframe,
.element-container iframe {
    border-radius: 8px;
}

/* --- Section spacing --- */
[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
    gap: 0.5rem;
}

/* --- Dataframe: softer look --- */
[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 2px rgba(0,0,0,0.06);
}
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
    st.title(f"{PAGE_ICON} {APP_NAME}")
    st.caption(f"v{APP_VERSION} | {APP_DESCRIPTION}")
    st.divider()

    st.subheader("1. קבוצת מזהמים")
    groups = list_groups()
    if "PFAS" in groups:
        groups.remove("PFAS")
        groups.insert(0, "PFAS")
    selected_group = st.selectbox("קבוצה", options=groups, index=0)

    st.divider()

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
            if "stations_ms" in st.session_state:
                del st.session_state["stations_ms"]
            st.rerun()
        except (ValueError, KeyError, FileNotFoundError, pd.errors.EmptyDataError) as e:
            st.error(f"שגיאה בטעינת הקובץ:\n{e}")

elif load_clicked and chosen_file is None:
    st.warning("יש לבחור קובץ לפני טעינה.")


# =============================================================================
# Welcome screen
# =============================================================================
if not st.session_state.file_loaded:
    st.title(f"ברוכים הבאים ל-{APP_NAME}")
    st.markdown("""
### כלי לחקירת מקורות זיהום במים, קרקע ושפכים

**שלבי העבודה:**
1. **בחר קבוצת מזהמים** בסרגל הצד
2. **בחר או העלה קובץ** נתונים
3. **לחץ "טען נתונים"**
4. צפה במפה, גרפים וניתוחים

---
*👈 התחל מהסרגל השמאלי*
""")
    st.stop()


# =============================================================================
# Data loaded — prepare ALL-stations data (for map)
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
# Sidebar — Station selection (source-type filter + select all/clear)
# =============================================================================
with st.sidebar:
    if st.session_state.file_loaded:
        st.markdown('<div class="success-banner">✓ הנתונים נטענו בהצלחה</div>', unsafe_allow_html=True)
    st.divider()
    st.subheader("3. בחירת נקודות דיגום")

    # Source type filter
    all_source_types = sorted(df["source_type"].dropna().unique())
    if all_source_types:
        selected_source_types = st.multiselect(
            "סנן לפי סוג מקור",
            options=all_source_types,
            default=all_source_types,
        )
        if selected_source_types:
            available_stations = sorted(
                df[df["source_type"].isin(selected_source_types)]["station_name"].unique()
            )
        else:
            available_stations = sorted(df["station_name"].unique())
    else:
        available_stations = sorted(df["station_name"].unique())
        selected_source_types = []

    # Select All / Clear All
    col_all, col_clear = st.columns(2)
    with col_all:
        if st.button("בחר הכל", use_container_width=True):
            st.session_state["stations_ms"] = list(available_stations)
            st.session_state.drawn_stations = None
            st.rerun()
    with col_clear:
        if st.button("נקה הכל", use_container_width=True):
            st.session_state["stations_ms"] = []
            st.session_state.drawn_stations = None
            st.rerun()

    # Remove stale stations from widget state
    if "stations_ms" in st.session_state:
        valid = [s for s in st.session_state["stations_ms"] if s in available_stations]
        if len(valid) != len(st.session_state["stations_ms"]):
            st.session_state["stations_ms"] = valid

    selected_stations = st.multiselect(
        f"תחנות ({len(available_stations)} זמינות)",
        options=available_stations,
        key="stations_ms",
        help="סנן לפי סוג מקור למעלה, או צייר אזור על המפה",
    )

    # Counter
    total_stations = df["station_name"].nunique()
    n_selected = len(st.session_state.drawn_stations) if st.session_state.drawn_stations else len(selected_stations)
    if n_selected > 0:
        st.caption(f"**{n_selected} מתוך {total_stations}** תחנות נבחרו")
    else:
        st.caption(f"כל {total_stations} התחנות מוצגות")


# =============================================================================
# Apply filter — selected stations only for analytics
# =============================================================================
effective_stations = selected_stations or []
if st.session_state.drawn_stations:
    effective_stations = st.session_state.drawn_stations

if effective_stations:
    df_filtered = df[df["station_name"].isin(effective_stations)].copy()
else:
    df_filtered = df.copy()

# Analytics — computed from SELECTED stations only
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

# Stations with zero total concentration (below LOD / no signal)
# Excluded from sections 2, 5, 6 — kept in sections 3, 4, 7
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
# Header
# =============================================================================
st.title(f"ניתוח {group.name}")
st.caption(f"מקור נתונים: {file_name}")
st.markdown(
    '<div class="header-desc">מיפוי נקודות דיגום, בחירת תחנות והשוואת חתימות '
    f'{group.name} יחסיות בין מקורות, נחלים וקידוחים.</div>',
    unsafe_allow_html=True,
)

n_stations = df_filtered["station_name"].nunique()
n_compounds = df_filtered["compound"].nunique() if "compound" in df_filtered.columns else 0
dates = df_filtered["sample_date"].dropna()
date_min = dates.min() if len(dates) > 0 else None
date_max = dates.max() if len(dates) > 0 else None

_date_valid = (
    date_min is not None
    and date_max is not None
    and date_min.year >= 1980
)
_date_str = f"{date_min:%d/%m/%Y} — {date_max:%d/%m/%Y}" if _date_valid else "לא זוהה בקובץ"

col1, col2, col3, col4 = st.columns(4)
with col1:
    with st.container(border=True):
        st.metric("תחנות", n_stations)
with col2:
    with st.container(border=True):
        st.metric("שורות נתונים", f"{len(df_filtered):,}")
with col3:
    with st.container(border=True):
        st.metric("תרכובות", n_compounds or "—")
with col4:
    with st.container(border=True):
        st.metric("טווח תאריכים", _date_str)

# --- Quick Insights Row ---
_enough_for_insights = len(max_event_nonzero) >= 1
if _enough_for_insights:
    st.markdown('<h3 style="margin-top:1.2rem; margin-bottom:0.5rem;">תובנות מרכזיות</h3>', unsafe_allow_html=True)
    ic1, ic2, ic3, ic4, ic5 = st.columns(5)

    _top_stn = max_event_nonzero.iloc[0]["station_name"] if not max_event_nonzero.empty else "—"
    _top_val = max_event_nonzero.iloc[0]["total_concentration"] if not max_event_nonzero.empty else 0
    with ic1:
        with st.container(border=True):
            st.caption(f"תחנה עם Σ{group.name} מקסימלי")
            st.markdown(f"**{html.escape(str(_top_stn))}**")
            st.markdown(f"<span style='color:#1a5c3a; font-weight:600;'>{_top_val:.2f} {group.unit}</span>", unsafe_allow_html=True)

    _n_detected = len(max_event_nonzero)
    _n_total_stn = len(max_event_filtered)
    with ic2:
        with st.container(border=True):
            st.caption(f"תחנות עם {group.name} מזוהה")
            st.markdown(f"**{_n_detected} מתוך {_n_total_stn}**")

    _dominant = "—"
    _dominant_pct = 0.0
    if not fingerprint_nonzero.empty:
        _mean_fp = fingerprint_nonzero.mean()
        _dominant = _mean_fp.idxmax()
        _dominant_pct = _mean_fp.max()
    with ic3:
        with st.container(border=True):
            st.caption("תרכובת דומיננטית")
            st.markdown(f"**{html.escape(str(_dominant))}**")
            st.markdown(f"<span style='color:#1a5c3a; font-weight:600;'>{_dominant_pct:.1f}%</span>", unsafe_allow_html=True)

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
                    _top_pair = f"{_sim_idx[_i]} ↔ {_sim_idx[_j]}"
                    _top_pair_val = _v
    with ic4:
        with st.container(border=True):
            st.caption("זוג דומה ביותר")
            st.markdown(f"**{html.escape(_top_pair)}**")
            st.markdown(f"<span style='color:#1a5c3a; font-weight:600;'>{_top_pair_val:.0f}%</span>", unsafe_allow_html=True)
    with ic5:
        with st.container(border=True):
            st.caption("זוגות עם דמיון ≥90%")
            st.markdown(f"**{_n_high_pairs}**")

st.divider()


# =============================================================================
# 1. Map — ALL stations shown, selected highlighted
# =============================================================================
st.markdown('<h2 class="section-header">1. מפת נקודות הדיגום</h2>', unsafe_allow_html=True)
st.markdown(f'<div class="section-desc">בחרו תחנות מהמפה או מהרשימה כדי להשוות בין חתימות {group.name} בתחנות הדיגום.</div>', unsafe_allow_html=True)

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
            "polygon": {"allowIntersection": False, "shapeOptions": {"color": "#3388ff"}},
            "circle": {"shapeOptions": {"color": "#3388ff"}},
            "rectangle": {"shapeOptions": {"color": "#3388ff"}},
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
            opacity = 0.8
            radius = max(6, min(20, 6 + 4 * np.log10(max(total, 0.01) + 1)))
            tooltip = folium.Tooltip(station_name, permanent=False, sticky=True)
            _lbl = (
                f'<div style="font-size:11px;font-weight:700;color:#0d1b2a;'
                f'text-shadow:-1px -1px 0 #fff,1px -1px 0 #fff,-1px 1px 0 #fff,1px 1px 0 #fff;'
                f'white-space:nowrap;pointer-events:none;background:transparent;border:none;">'
                f'{station_name}</div>'
            )
            folium.Marker(
                location=[lat, lon],
                icon=folium.DivIcon(html=_lbl, icon_size=(150, 20), icon_anchor=(-8, 10), class_name="stn-lbl-icon"),
            ).add_to(m)
        elif is_zero:
            color = "#e0e0e0"
            opacity = 0.25
            radius = 4
            tooltip = folium.Tooltip(station_name, permanent=False, sticky=False)
        else:
            color = "#cccccc"
            opacity = 0.35
            radius = 5
            tooltip = folium.Tooltip(station_name, permanent=False, sticky=False)

        popup_html = f"""
        <div style="direction:rtl; text-align:right; min-width:200px;">
            <b>{station_name}</b><br>
            סוג: {source_type}<br>
            Σ{group.name}: {total:.3f} {group.unit}<br>
            תאריך: {row['sample_date']:%d/%m/%Y}
        </div>
        """
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

    # Zoom-aware labels with greedy anti-overlap + transparent tooltip styling
    from branca.element import Element as _Elem
    _mid = m._id
    # Zoom-aware labels: hide DivIcon labels below zoom 11, greedy anti-overlap above
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
        m, width=None, height=500, use_container_width=True,
        returned_objects=["all_drawings", "last_active_drawing"],
    )

    # Process drawn shapes → select stations inside; rerun immediately when selection changes
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

    col_legend, col_clear = st.columns([4, 1])
    with col_clear:
        if st.session_state.drawn_stations and st.button("נקה בחירה מהמפה"):
            st.session_state.drawn_stations = None
            st.rerun()
    with col_legend:
        legend_items = []
        for src, clr in SOURCE_COLORS.items():
            if src in df["source_type"].values:
                legend_items.append(
                    f'<span style="display:inline-block;width:12px;height:12px;'
                    f'background:{clr};border-radius:50%;margin-left:5px;"></span> {src}'
                )
        if legend_items:
            st.markdown(" &nbsp;|&nbsp; ".join(legend_items), unsafe_allow_html=True)

except ImportError:
    st.warning("חסרות חבילות folium / streamlit-folium. התקן: pip install folium streamlit-folium")

st.divider()


# =============================================================================
# 2. Total Concentration (Attenuation)
# =============================================================================
st.markdown(f'<h2 class="section-header">2. ריכוז סכומי של תרכובות {group.name} בנקודות הדיגום</h2>', unsafe_allow_html=True)
st.markdown(f'<div class="section-desc">סכום ריכוזי תרכובות {group.name} בכל נקודת דיגום, מסודר מהגבוה לנמוך. ציר Y מוצג בסקאלה לוגריתמית.</div>', unsafe_allow_html=True)
with st.expander("על האנליזה — ריכוז סכומי", expanded=False):
    st.markdown("""<div class="method-box">
<b>עיקרון:</b> סיכום ריכוזי כל התרכובות בכל תחנה (אירוע הדיגום המירבי), להשוואת עומס הזיהום הכולל בין נקודות.<br>
<b>נוסחה:</b> <code>Σ = Σᵢ Cᵢ</code> — סכום ריכוזי כל התרכובות i בתחנה נתונה.<br>
<b>חוזקות:</b> פשוט ואינטואיטיבי; מאפשר מיון מהיר לפי חומרת הזיהום; חשיפת דפוס דעיכה (Attenuation) לאורך מסלול הסעה.<br>
<b>חולשות:</b> לא מבחין בין תרכובות — תחנה עם תרכובת דומיננטית אחת ותחנה עם פיזור שווה יכולות להראות ריכוז זהה; ריכוזים מתחת ל-LOD נחשבים כאפס.
</div>""", unsafe_allow_html=True)

if not max_event_nonzero.empty:
    _top_stn_s2 = html.escape(str(max_event_nonzero.iloc[0]["station_name"]))
    _top_val_s2 = max_event_nonzero.iloc[0]["total_concentration"]
    st.markdown(
        f'<div class="insight-banner">נקודת הדיגום בעלת הריכוז הסכומי הגבוה ביותר היא '
        f'<b>{_top_stn_s2}</b>, עם Σ{group.name} של <b>{_top_val_s2:.2f} {group.unit}</b>.</div>',
        unsafe_allow_html=True,
    )
    fig_atten = go.Figure()
    _names_s2 = max_event_nonzero["station_name"].tolist()
    _short_names_s2 = [_short_name(n) for n in _names_s2]
    colors = [_get_source_color(s) for s in max_event_nonzero["source_type"]]
    fig_atten.add_trace(go.Bar(
        x=_short_names_s2,
        y=max_event_nonzero["total_concentration"],
        marker_color=colors,
        text=[_fmt_total(v) for v in max_event_nonzero["total_concentration"]],
        textposition="outside",
        customdata=_names_s2,
        hovertemplate="<b>%{customdata}</b><br>Σ" + group.name + ": %{y:.3f} " + group.unit + "<extra></extra>",
    ))
    fig_atten.update_layout(
        xaxis_title="תחנה",
        yaxis_title=f"ריכוז ({group.unit})",
        yaxis_type="log",
        height=500,
        template="plotly_white",
        font=dict(size=13),
    )
    st.plotly_chart(fig_atten, use_container_width=True)
    st.markdown(
        '<div class="caveat-note">הריכוז הסכומי משקף את עומס הזיהום הנקודתי. '
        'אינו מעיד בהכרח על מקור משותף או על דעיכה לאורך מסלול זרימה.</div>',
        unsafe_allow_html=True,
    )
else:
    st.info("אין נתוני ריכוז להצגה. בחר תחנות בסרגל הצד או צייר אזור על המפה.")

st.divider()


# =============================================================================
# 3. Fingerprint (Chemical Composition)
# =============================================================================
st.markdown(f'<h2 class="section-header">3. שינוי בהרכב היחסי של תרכובות {group.name}</h2>', unsafe_allow_html=True)
st.markdown(
    f'<div class="section-desc">כל עמודה מייצגת נקודת דיגום. מקטעי העמודה מייצגים את התרומה היחסית של כל תרכובת {group.name} '
    'לסך הריכוז הסכומי באותה נקודה.</div>',
    unsafe_allow_html=True,
)
with st.expander("על האנליזה — טביעת אצבע כימית", expanded=False):
    st.markdown("""<div class="method-box">
<b>עיקרון:</b> נרמול ההרכב הכימי של כל תחנה ל-100%, כך שניתן להשוות בין פרופילים ללא תלות בריכוז המוחלט. שינוי בהרכב היחסי (Chromatographic Shift) מעיד על תהליכי ריטרדציה, ספיחה סלקטיבית או מקורות שונים.<br>
<b>נוסחה:</b> <code>%ᵢ = (Cᵢ / Σ) × 100</code> — אחוז התרכובת i מסך הריכוזים.<br>
<b>חוזקות:</b> מאפשר השוואת מקורות ללא תלות בריכוז; חושף שינויי הרכב לאורך מסלול הסעה; כלי מרכזי בזיהוי פורנזי של מקורות.<br>
<b>חולשות:</b> מאבד מידע על גודל מוחלט (תחנה מאוד מזוהמת ומעט מזוהמת יכולות להיראות זהות); תרכובות מתחת ל-LOD נחשבות כאפס ועלולות להטות את ההרכב.
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
            customdata=[compound] * len(stations),
            hovertemplate="<b>" + compound + "</b><br>%{x}: %{y:.1f}%<extra></extra>",
        ))

    total_lookup = max_event_filtered.set_index("station_name")["total_concentration"]
    annotations_fp = []
    for idx, stn in enumerate(stations):
        total_val = total_lookup.get(stn, 0)
        annotations_fp.append(dict(
            x=_short_stations_fp[idx], y=100, text=_fmt_total(total_val),
            showarrow=False, yshift=12,
            font=dict(size=10, color="#555"),
        ))

    fig_fp.update_layout(
        barmode="stack",
        xaxis_title="תחנה",
        yaxis_title="אחוז (%)",
        yaxis=dict(range=[0, 100]),
        height=500,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        font=dict(size=13),
        annotations=annotations_fp,
    )
    st.plotly_chart(fig_fp, use_container_width=True)
    st.markdown(
        '<div class="caveat-note">הרכב יחסי תלוי בקיום מספיק תרכובות מעל סף הזיהוי. '
        'תחנות עם ערכים נמוכים יציגו הרכב רגיש לרעש מדידה.</div>',
        unsafe_allow_html=True,
    )
else:
    st.info("אין מספיק נתונים לבניית fingerprint. בחר תחנות בסרגל הצד או צייר אזור על המפה.")

st.divider()


# =============================================================================
# 4. Cosine Similarity Heatmap
# =============================================================================
st.markdown(f'<h2 class="section-header">4. דמיון בין חתימות {group.name} בנקודות הדיגום</h2>', unsafe_allow_html=True)
st.markdown(
    f'<div class="section-desc">כל תא במטריצה מציג את מידת הדמיון בין שתי נקודות דיגום, '
    f'על בסיס ההרכב היחסי של תרכובות {group.name}.</div>',
    unsafe_allow_html=True,
)
with st.expander("על האנליזה — Cosine Similarity", expanded=False):
    st.markdown("""<div class="method-box">
<b>עיקרון:</b> מדידת הזווית בין וקטורי ההרכב הכימי של שתי תחנות. ככל שהזווית קטנה יותר — ההרכב דומה יותר, ללא תלות בריכוז המוחלט.<br>
<b>נוסחה:</b> <code>cos(θ) = (A · B) / (‖A‖ × ‖B‖)</code> — מכפלה סקלרית מנורמלת; ערך 100% = הרכב זהה, 0% = שונה לחלוטין.<br>
<b>חוזקות:</b> אינווריאנטי לקנה מידה (scale-invariant) — משווה צורה ולא גודל; מתאים לזיהוי מקורות משותפים גם בריכוזים שונים מאוד.<br>
<b>חולשות:</b> דמיון גבוה אינו מוכיח מקור משותף — תהליכים שונים יכולים לייצר הרכב דומה; רגיש לתרכובות בעלות ריכוז אפסי (LOD) שעלולות ליצור "רעש".
</div>""", unsafe_allow_html=True)

# Textual color legend
st.markdown("""<div class="similarity-legend">
<span class="sim-pill"><span class="sim-dot" style="background:#d32f2f;"></span> 0-30% דמיון נמוך</span>
<span class="sim-pill"><span class="sim-dot" style="background:#fbc02d;"></span> 30-70% דמיון בינוני</span>
<span class="sim-pill"><span class="sim-dot" style="background:#81c784;"></span> 70-90% דמיון גבוה</span>
<span class="sim-pill"><span class="sim-dot" style="background:#2e7d32;"></span> 90-100% דמיון גבוה מאוד</span>
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

    fig_sim = go.Figure(data=go.Heatmap(
        z=sim_ordered.values,
        x=ordered_labels,
        y=ordered_labels,
        colorscale="RdYlGn",
        zmin=0, zmax=100,
        text=sim_ordered.values.round(0).astype(int),
        texttemplate="%{text}%",
        textfont=dict(size=10),
        hovertemplate="<b>%{x}</b> ↔ <b>%{y}</b><br>דמיון: %{z:.1f}%<extra></extra>",
        colorbar=dict(title="% דמיון"),
    ))
    fig_sim.update_layout(
        height=max(500, len(ordered_labels) * 35 + 150),
        template="plotly_white",
        font=dict(size=12),
        xaxis=dict(side="bottom"),
    )
    st.plotly_chart(fig_sim, use_container_width=True)

    # Top-pairs table (pairs with similarity >= 70%)
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
        st.markdown("**זוגות תחנות עם דמיון גבוה (≥70%):**")
        st.dataframe(
            pd.DataFrame(_pairs_s4[:10]),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown(
        '<div class="caveat-note">דמיון בהרכב ' + group.name + ' אינו מוכיח מקור משותף בפני עצמו. '
        'יש לפרש את הממצאים יחד עם מידע הידרולוגי, מיקום מרחבי, כיווני זרימה, מועדי דיגום ואיכות הנתונים.</div>',
        unsafe_allow_html=True,
    )
else:
    st.info("נדרשות לפחות 2 תחנות עם ריכוז מזוהה לחישוב מטריצת דמיון.")

st.divider()


# =============================================================================
# 5. PCA — Principal Component Analysis
# =============================================================================
st.markdown('<h2 class="section-header">5. PCA — ניתוח רכיבים ראשיים</h2>', unsafe_allow_html=True)
st.caption("הפחתת ממדים של ההרכב הכימי לשני רכיבים ראשיים. תחנות קרובות בגרף דומות בהרכבן הכימי.")
with st.expander("על האנליזה — Principal Component Analysis", expanded=False):
    st.markdown("""<div class="method-box">
<b>עיקרון:</b> הפחתת ממדים ליניארית — מוצאים את הצירים (רכיבים ראשיים) שלאורכם השונות במידע מקסימלית. הנתונים מוקרנים על שני הרכיבים הראשיים, כך שתחנות עם הרכב כימי דומה מופיעות קרובות בגרף.<br>
<b>נוסחה:</b> <code>X = T·Pᵀ + E</code> — X = מטריצת הנתונים, T = ציונים (scores), P = משקולות (loadings), E = שארית. הרכיבים הם הוקטורים העצמיים של מטריצת הקווריאנס.<br>
<b>חוזקות:</b> מזהה את מנועי השונות העיקריים; מפחית מידע רב-ממדי לגרף 2D קריא; אחוז השונות המוסבר מציין עד כמה הגרף מייצג את המציאות.<br>
<b>חולשות:</b> מניח קשרים ליניאריים בלבד; רגיש לקנה מידה של המשתנים; כשרכיבים מסבירים אחוז נמוך — הגרף מטעה; קשה לפרש loadings מעורבי סימן.
</div>""", unsafe_allow_html=True)

pca_data = None
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
            marker=dict(size=12, color=color, line=dict(width=1, color="white")),
            text=[stn],
            textposition="top center",
            name=src,
            legendgroup=src,
            showlegend=show_legend,
            hovertemplate=f"<b>{stn}</b><br>סוג: {src}<extra></extra>",
        ))

    label_x = f"PC1 ({var_explained[0]:.1f}%)"
    label_y = f"PC2 ({var_explained[1]:.1f}%)" if len(var_explained) > 1 else "PC2"
    fig_pca.update_layout(
        xaxis_title=label_x,
        yaxis_title=label_y,
        height=550,
        template="plotly_white",
        font=dict(size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_pca, use_container_width=True)
    st.markdown(
        '<div class="caveat-note">הקרבה בגרף PCA משקפת דמיון בהרכב היחסי. '
        'אחוז שונות נמוך (פחות מ-60%) מצביע שהגרף מייצג את המציאות בצורה חלקית בלבד.</div>',
        unsafe_allow_html=True,
    )
else:
    st.info("נדרשות לפחות 2 תחנות עם נתוני ריכוז לביצוע PCA.")

st.divider()


# =============================================================================
# 6. MDS — Multidimensional Scaling
# =============================================================================
st.markdown('<h2 class="section-header">6. MDS — מיפוי מרחק כימי</h2>', unsafe_allow_html=True)
st.caption("Multidimensional Scaling על מרחק קוסינוס. מרחק בגרף משקף שונוּת בהרכב הכימי בין התחנות.")
with st.expander("על האנליזה — Multidimensional Scaling", expanded=False):
    st.markdown("""<div class="method-box">
<b>עיקרון:</b> מיפוי התחנות במרחב דו-ממדי כך שהמרחקים בגרף ישקפו בצורה הטובה ביותר את המרחקים הכימיים המקוריים (מרחק קוסינוס). תחנות קרובות בגרף = הרכב כימי דומה.<br>
<b>נוסחה:</b> <code>min Σᵢⱼ (dᵢⱼ − δᵢⱼ)²</code> — מינימיזציה של ה-Stress: הפרש בין המרחקים במיפוי (d) למרחקים המקוריים (δ).<br>
<b>חוזקות:</b> עובד עם כל מטריקת מרחק (לא רק אוקלידית); לא מניח ליניאריות; משלים את ה-PCA בכך שהוא שומר על מרחקים זוגיים ולא על שונות.<br>
<b>חולשות:</b> הפתרון לא יחיד — סיבובים והיפוכים שרירותיים; עלול להיתקע במינימום מקומי; אין loadings — לא ניתן לדעת אילו תרכובות גורמות להפרדה.
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
            marker=dict(size=12, color=color, line=dict(width=1, color="white")),
            text=[stn],
            textposition="top center",
            name=src,
            legendgroup=src,
            showlegend=show_legend,
            hovertemplate=f"<b>{stn}</b><br>סוג: {src}<extra></extra>",
        ))

    fig_mds.update_layout(
        xaxis_title="MDS ציר 1",
        yaxis_title="MDS ציר 2",
        height=550,
        template="plotly_white",
        font=dict(size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_mds, use_container_width=True)
    st.markdown(
        '<div class="caveat-note">מיקומי הצירים שרירותיים — רק המרחקים בין נקודות הם משמעותיים. '
        'סיבוב והיפוך אינם משנים את הפירוש.</div>',
        unsafe_allow_html=True,
    )
else:
    st.info("נדרשות לפחות 2 תחנות לביצוע MDS.")

st.divider()


# =============================================================================
# 7. Findings
# =============================================================================
st.markdown('<h2 class="section-header">7. סיכום ממצאים והערות זהירות</h2>', unsafe_allow_html=True)

findings = generate_findings_summary(df_filtered, group, sim_matrix, pca_data=pca_data)
if findings:
    for f in findings:
        st.markdown(f'<div class="finding-card">{f}</div>', unsafe_allow_html=True)
else:
    st.info("אין מספיק נתונים ליצירת ממצאים.")

st.markdown(
    '<div class="caveat-note" style="border-color:#d4a84a; background:#fef9ec;">⚠ כלי זה תומך בניתוח מקצועי '
    'אך אינו מחליף שיקול דעת מומחה. ממצאים מחייבים אימות עם מידע הידרולוגי, גיאוגרפי וכימי משלים.</div>',
    unsafe_allow_html=True,
)

st.divider()


# =============================================================================
# 8. Raw Data (collapsible)
# =============================================================================
with st.expander("נתונים גולמיים", expanded=False):
    st.subheader("סיכום תחנות")
    st.dataframe(station_summary, use_container_width=True, hide_index=True)

    st.subheader("טבלת נתונים")
    st.dataframe(df_filtered, use_container_width=True, hide_index=True)

    csv = df_filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "הורד CSV",
        data=csv,
        file_name=f"{group.name}_data.csv",
        mime="text/csv",
    )


# =============================================================================
# Footer
# =============================================================================
st.sidebar.divider()
st.sidebar.caption(
    "כל הנתונים נשארים על המחשב שלך.\n"
    "רק תמונות רקע של המפה נטענות מהאינטרנט."
)
