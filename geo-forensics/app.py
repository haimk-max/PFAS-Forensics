"""דשבורד GeoForensics — streamlit run app.py."""

import html
import os
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(__file__))

from config import (
    APP_DESCRIPTION, APP_NAME, APP_VERSION, COMPOUND_COLORS, DATA_DIR,
    DEFAULT_COLOR, DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM, PAGE_ICON,
    SOURCE_COLORS, SUPPORTED_EXTENSIONS,
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

# RTL support
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


# =============================================================================
# Session State
# =============================================================================
def _stations_in_drawing(drawing: dict, max_event: pd.DataFrame) -> list[str]:
    """Return station names that fall inside a drawn shape (polygon or circle)."""
    geom = drawing.get("geometry", {})
    geom_type = geom.get("type", "")
    coords = geom.get("coordinates", [])
    matched = []

    if geom_type == "Polygon" and coords:
        ring = coords[0]  # GeoJSON: [[lon, lat], ...]
        polygon = [(pt[1], pt[0]) for pt in ring]  # convert to (lat, lon)
        for _, row in max_event.iterrows():
            lat, lon = row.get("lat"), row.get("lon")
            if pd.notna(lat) and pd.notna(lon) and point_in_polygon(lat, lon, polygon):
                matched.append(row["station_name"])

    elif geom_type == "Point" and coords:
        # Circle: center + radius in properties
        center_lon, center_lat = coords[0], coords[1]
        radius_m = drawing.get("properties", {}).get("radius", 0)
        if radius_m <= 0:
            radius_m = 5000  # default 5km
        for _, row in max_event.iterrows():
            lat, lon = row.get("lat"), row.get("lon")
            if pd.notna(lat) and pd.notna(lon):
                dist = calc_distance(center_lat, center_lon, lat, lon)
                if dist <= radius_m:
                    matched.append(row["station_name"])

    return matched


def init_session_state():
    defaults = {
        "df": None, "group": None, "group_name": None,
        "file_name": None, "file_loaded": False,
        "selected_stations": None,
        "drawn_stations": None,
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

    # 1. Contaminant group
    st.subheader("1. קבוצת מזהמים")
    groups = list_groups()
    if "PFAS" in groups:
        groups.remove("PFAS")
        groups.insert(0, "PFAS")
    selected_group = st.selectbox("קבוצה", options=groups, index=0)

    st.divider()

    # 2. Data source
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
            st.session_state.selected_stations = None
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
# Data loaded — prepare analytics
# =============================================================================
df = st.session_state.df
group = st.session_state.group
file_name = st.session_state.file_name

# Station filter in sidebar
with st.sidebar:
    st.divider()
    st.subheader("3. סינון תחנות")
    all_stations = sorted(df["station_name"].unique())
    selected_stations = st.multiselect(
        "בחר תחנות (ריק = הכל)",
        options=all_stations,
        default=st.session_state.selected_stations or [],
        help="השאר ריק כדי להציג את כל התחנות",
    )
    st.session_state.selected_stations = selected_stations if selected_stations else None

# Apply filter (sidebar selection OR map drawing)
effective_stations = selected_stations or []
if st.session_state.drawn_stations:
    effective_stations = st.session_state.drawn_stations

if effective_stations:
    df_filtered = df[df["station_name"].isin(effective_stations)].copy()
else:
    df_filtered = df.copy()

# Compute analytics
totals = calc_total_concentration(df_filtered, group)
totals_sorted = totals.sort_values("total_concentration", ascending=False)

# Max event per station (for display)
max_event = (
    totals_sorted
    .loc[totals_sorted.groupby("station_name")["total_concentration"].idxmax()]
    .sort_values("total_concentration", ascending=False)
)

fingerprint = build_fingerprint_matrix(df_filtered, group)
sim_matrix = cosine_similarity_matrix(df_filtered, group)

# Station summary
station_summary = get_station_summary(df_filtered)

# =============================================================================
# Header
# =============================================================================
st.title(f"ניתוח {group.name} — {file_name}")

# Summary metrics
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
# Tab layout
# =============================================================================
tab_map, tab_atten, tab_finger, tab_sim, tab_findings, tab_data = st.tabs([
    "מפה", "ריכוז כולל", "הרכב כימי", "Cosine Similarity", "ממצאים", "נתונים"
])

# =============================================================================
# TAB 1: Map
# =============================================================================
with tab_map:
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

        # Add stations
        for _, row in max_event.iterrows():
            lat, lon = row.get("lat"), row.get("lon")
            if pd.isna(lat) or pd.isna(lon):
                continue

            source_type = row.get("source_type", "")
            color = _get_source_color(source_type)
            total = row["total_concentration"]

            radius = max(6, min(20, 6 + 4 * np.log10(max(total, 0.01) + 1)))

            popup_html = f"""
            <div style="direction:rtl; text-align:right; min-width:200px;">
                <b>{row['station_name']}</b><br>
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
                fill_opacity=0.7,
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=row["station_name"],
            ).add_to(m)

        lats = max_event["lat"].dropna()
        lons = max_event["lon"].dropna()
        if len(lats) > 0:
            m.fit_bounds([[lats.min(), lons.min()], [lats.max(), lons.max()]])

        map_data = st_folium(
            m, width=None, height=500, use_container_width=True,
            returned_objects=["all_drawings", "last_active_drawing"],
        )

        # Process drawn shapes → select stations inside them
        drawings = map_data.get("all_drawings") if map_data else None
        if drawings:
            drawn_names = []
            for d in drawings:
                drawn_names.extend(_stations_in_drawing(d, max_event))
            if drawn_names:
                unique_drawn = sorted(set(drawn_names))
                st.session_state.drawn_stations = unique_drawn
                st.success(f"נבחרו {len(unique_drawn)} תחנות דרך ציור על המפה")
        elif map_data and map_data.get("all_drawings") == []:
            st.session_state.drawn_stations = None

        col_legend, col_clear = st.columns([4, 1])
        with col_clear:
            if st.session_state.drawn_stations and st.button("נקה בחירה מהמפה"):
                st.session_state.drawn_stations = None
                st.rerun()
        with col_legend:
            legend_items = []
            for src, color in SOURCE_COLORS.items():
                if src in df_filtered["source_type"].values:
                    legend_items.append(
                        f'<span style="display:inline-block;width:12px;height:12px;'
                        f'background:{color};border-radius:50%;margin-left:5px;"></span> {src}'
                    )
            if legend_items:
                st.markdown(" &nbsp;|&nbsp; ".join(legend_items), unsafe_allow_html=True)

    except ImportError:
        st.warning("חסרות חבילות folium / streamlit-folium. התקן: pip install folium streamlit-folium")

# =============================================================================
# TAB 2: Attenuation (Total Concentration)
# =============================================================================
with tab_atten:
    if not max_event.empty:
        fig_atten = go.Figure()
        colors = [_get_source_color(s) for s in max_event["source_type"]]
        fig_atten.add_trace(go.Bar(
            x=max_event["station_name"],
            y=max_event["total_concentration"],
            marker_color=colors,
            text=[f"{v:.3f}" for v in max_event["total_concentration"]],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Σ" + group.name + ": %{y:.3f} " + group.unit + "<extra></extra>",
        ))
        fig_atten.update_layout(
            title=f"ריכוז כולל Σ{group.name} לפי תחנה (סדר יורד)",
            xaxis_title="תחנה",
            yaxis_title=f"ריכוז ({group.unit})",
            yaxis_type="log",
            height=500,
            template="plotly_white",
            font=dict(size=13),
        )
        st.plotly_chart(fig_atten, use_container_width=True)
    else:
        st.info("אין נתוני ריכוז להצגה.")

# =============================================================================
# TAB 3: Fingerprint (Chemical Composition)
# =============================================================================
with tab_finger:
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

        fig_fp.update_layout(
            title="הרכב כימי יחסי (Fingerprint) — אירוע מקסימלי לכל תחנה",
            barmode="stack",
            xaxis_title="תחנה",
            yaxis_title="אחוז (%)",
            yaxis=dict(range=[0, 100]),
            height=500,
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            font=dict(size=13),
        )
        st.plotly_chart(fig_fp, use_container_width=True)
    else:
        st.info("אין מספיק נתונים לבניית fingerprint.")

# =============================================================================
# TAB 4: Cosine Similarity Heatmap
# =============================================================================
with tab_sim:
    if not sim_matrix.empty and len(sim_matrix) >= 2:
        # Reorder by hierarchical clustering
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
            title="מטריצת Cosine Similarity בין תחנות",
            height=max(500, len(ordered_labels) * 35 + 150),
            template="plotly_white",
            font=dict(size=12),
            xaxis=dict(side="bottom"),
        )
        st.plotly_chart(fig_sim, use_container_width=True)
    else:
        st.info("נדרשות לפחות 2 תחנות לחישוב Cosine Similarity.")

# =============================================================================
# TAB 5: Findings
# =============================================================================
with tab_findings:
    st.subheader("סיכום ממצאים")
    findings = generate_findings_summary(df_filtered, group, sim_matrix)
    if findings:
        for f in findings:
            st.markdown(f'<div class="finding-card">{f}</div>', unsafe_allow_html=True)
    else:
        st.info("אין מספיק נתונים ליצירת ממצאים.")

# =============================================================================
# TAB 6: Data Table
# =============================================================================
with tab_data:
    st.subheader("נתונים גולמיים")

    # Station summary
    with st.expander("סיכום תחנות", expanded=False):
        st.dataframe(station_summary, use_container_width=True, hide_index=True)

    # Full data
    st.dataframe(df_filtered, use_container_width=True, hide_index=True)

    # CSV export
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
