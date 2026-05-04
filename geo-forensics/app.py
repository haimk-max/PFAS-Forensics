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
<style>
.stApp { direction: rtl; }
.stMarkdown, .stText { text-align: right; }
.stDataFrame { direction: ltr; }
input[type="number"] { direction: ltr; text-align: left; }
section[data-testid="stSidebar"] { direction: rtl; }
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stFileUploader label,
section[data-testid="stSidebar"] .stMultiSelect label { text-align: right; }
.finding-card {
    background: #f8f9fa; border-right: 4px solid #3498db;
    padding: 10px 15px; margin: 8px 0; border-radius: 4px;
    direction: rtl; text-align: right;
}
.section-header {
    color: #1a8c5e; border-bottom: 2px solid #1a8c5e;
    padding-bottom: 8px; margin-top: 1.5rem;
}
.method-box {
    background: #f0f4f8; border: 1px solid #d0d7de; border-radius: 6px;
    padding: 12px 16px; margin: 6px 0 12px 0; direction: rtl; text-align: right;
    font-size: 0.92em; line-height: 1.7;
}
.method-box b { color: #1a5276; }
.method-box code { background: #e8ecf0; padding: 1px 5px; border-radius: 3px; direction: ltr; unicode-bidi: embed; }
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
st.title(f"ניתוח {group.name} — {file_name}")

n_stations = df_filtered["station_name"].nunique()
dates = df_filtered["sample_date"].dropna()
date_min = dates.min() if len(dates) > 0 else None
date_max = dates.max() if len(dates) > 0 else None

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("תחנות", n_stations)
with col2:
    st.metric("שורות נתונים", f"{len(df_filtered):,}")
with col3:
    st.metric("תרכובות", df_filtered["compound"].nunique() if "compound" in df_filtered.columns else "—")
with col4:
    if date_min is not None and date_max is not None:
        st.metric("טווח תאריכים", f"{date_min:%d/%m/%Y} — {date_max:%d/%m/%Y}")
    else:
        st.metric("טווח תאריכים", "—")

st.divider()


# =============================================================================
# 1. Map — ALL stations shown, selected highlighted
# =============================================================================
st.markdown('<h2 class="section-header">1. מפת נקודות דיגום</h2>', unsafe_allow_html=True)

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
            tooltip = folium.Tooltip(station_name, permanent=True, sticky=False)
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

    # Zoom-aware labels with greedy anti-overlap
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
            var tt=Array.from(c.querySelectorAll('.leaflet-tooltip-permanent'));
            if(z<10){{tt.forEach(function(t){{t.style.opacity='0';}});return;}}
            tt.forEach(function(t){{t.style.opacity='1';}});
            var placed=[];
            var cr=c.getBoundingClientRect();
            tt.forEach(function(t){{
                var r=t.getBoundingClientRect();
                var b={{l:r.left-cr.left,r:r.right-cr.left,t:r.top-cr.top,b:r.bottom-cr.top}};
                var ov=placed.some(function(p){{
                    return b.l<p.r+3&&b.r>p.l-3&&b.t<p.b+3&&b.b>p.t-3;
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
st.markdown(f'<h2 class="section-header">2. ריכוז כולל — Σ{group.name} Attenuation</h2>', unsafe_allow_html=True)
st.caption("ציר לוגריתמי. עמודה אחת לכל תחנה (אירוע מירבי). בחינת דעיכת מסת המזהם לאורך מסלולי הסעה.")
with st.expander("על האנליזה — ריכוז סכומי", expanded=False):
    st.markdown("""<div class="method-box">
<b>עיקרון:</b> סיכום ריכוזי כל התרכובות בכל תחנה (אירוע הדיגום המירבי), להשוואת עומס הזיהום הכולל בין נקודות.<br>
<b>נוסחה:</b> <code>Σ = Σᵢ Cᵢ</code> — סכום ריכוזי כל התרכובות i בתחנה נתונה.<br>
<b>חוזקות:</b> פשוט ואינטואיטיבי; מאפשר מיון מהיר לפי חומרת הזיהום; חשיפת דפוס דעיכה (Attenuation) לאורך מסלול הסעה.<br>
<b>חולשות:</b> לא מבחין בין תרכובות — תחנה עם תרכובת דומיננטית אחת ותחנה עם פיזור שווה יכולות להראות ריכוז זהה; ריכוזים מתחת ל-LOD נחשבים כאפס.
</div>""", unsafe_allow_html=True)

if not max_event_nonzero.empty:
    fig_atten = go.Figure()
    colors = [_get_source_color(s) for s in max_event_nonzero["source_type"]]
    fig_atten.add_trace(go.Bar(
        x=max_event_nonzero["station_name"],
        y=max_event_nonzero["total_concentration"],
        marker_color=colors,
        text=[f"{v:.3f}" for v in max_event_nonzero["total_concentration"]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Σ" + group.name + ": %{y:.3f} " + group.unit + "<extra></extra>",
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
else:
    st.info("אין נתוני ריכוז להצגה. בחר תחנות בסרגל הצד או צייר אזור על המפה.")

st.divider()


# =============================================================================
# 3. Fingerprint (Chemical Composition)
# =============================================================================
st.markdown('<h2 class="section-header">3. הרכב כימי יחסי — Chromatographic Shift</h2>', unsafe_allow_html=True)
st.caption("מנורמל ל-100%. מעל כל עמודה מוצג הריכוז הסכומי (µg/L). התרכובות ממוינות לפי שיעורן בתחנה המרוכזת ביותר.")
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

    for compound in compounds:
        fig_fp.add_trace(go.Bar(
            name=compound,
            x=stations,
            y=fingerprint[compound],
            marker_color=_get_color(compound),
            hovertemplate=f"<b>{compound}</b><br>" + "%{x}: %{y:.1f}%<extra></extra>",
        ))

    total_lookup = max_event_filtered.set_index("station_name")["total_concentration"]
    annotations_fp = []
    for stn in stations:
        total_val = total_lookup.get(stn, 0)
        annotations_fp.append(dict(
            x=stn, y=100, text=f"{total_val:.3f}",
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
else:
    st.info("אין מספיק נתונים לבניית fingerprint. בחר תחנות בסרגל הצד או צייר אזור על המפה.")

st.divider()


# =============================================================================
# 4. Cosine Similarity Heatmap
# =============================================================================
st.markdown('<h2 class="section-header">4. Cosine Similarity — מטריצת דמיון</h2>', unsafe_allow_html=True)
st.caption("התחנות ממוינות לפי Hierarchical Clustering. צבע ירוק = דמיון גבוה, אדום = דמיון נמוך.")
with st.expander("על האנליזה — Cosine Similarity", expanded=False):
    st.markdown("""<div class="method-box">
<b>עיקרון:</b> מדידת הזווית בין וקטורי ההרכב הכימי של שתי תחנות. ככל שהזווית קטנה יותר — ההרכב דומה יותר, ללא תלות בריכוז המוחלט.<br>
<b>נוסחה:</b> <code>cos(θ) = (A · B) / (‖A‖ × ‖B‖)</code> — מכפלה סקלרית מנורמלת; ערך 100% = הרכב זהה, 0% = שונה לחלוטין.<br>
<b>חוזקות:</b> אינווריאנטי לקנה מידה (scale-invariant) — משווה צורה ולא גודל; מתאים לזיהוי מקורות משותפים גם בריכוזים שונים מאוד.<br>
<b>חולשות:</b> דמיון גבוה אינו מוכיח מקור משותף — תהליכים שונים יכולים לייצר הרכב דומה; רגיש לתרכובות בעלות ריכוז אפסי (LOD) שעלולות ליצור "רעש".
</div>""", unsafe_allow_html=True)

if not sim_matrix.empty and len(sim_matrix) >= 2:
    try:
        from scipy.cluster.hierarchy import linkage, leaves_list
        from scipy.spatial.distance import squareform

        dist = 1 - sim_matrix.values / 100
        np.fill_diagonal(dist, 0)
        dist = (dist + dist.T) / 2
        condensed = squareform(dist, checks=False)
        Z = linkage(condensed, method="average")
        order = leaves_list(Z)
        ordered_labels = [sim_matrix.index[i] for i in order]
        sim_ordered = sim_matrix.loc[ordered_labels, ordered_labels]
    except (ValueError, np.linalg.LinAlgError):
        sim_ordered = sim_matrix
        ordered_labels = sim_matrix.index.tolist()

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
else:
    st.info("נדרשות לפחות 2 תחנות לחישוב Cosine Similarity.")

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
else:
    st.info("נדרשות לפחות 2 תחנות לביצוע MDS.")

st.divider()


# =============================================================================
# 7. Findings
# =============================================================================
st.markdown('<h2 class="section-header">7. סיכום ממצאים</h2>', unsafe_allow_html=True)

findings = generate_findings_summary(df_filtered, group, sim_matrix, pca_data=pca_data)
if findings:
    for f in findings:
        st.markdown(f'<div class="finding-card">{f}</div>', unsafe_allow_html=True)
else:
    st.info("אין מספיק נתונים ליצירת ממצאים.")

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
