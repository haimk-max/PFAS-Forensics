"""
generate_report.py - יצירת דוח HTML סטטי מקצועי
=================================================
מייצר קובץ HTML עצמאי הכולל:
1. מפה אינטראקטיבית (Leaflet) עם כל נקודות הדיגום
2. גרף ריכוז כולל (ΣPFAS Attenuation) - ציר לוגריתמי
3. גרף הרכב כימי יחסי (Chromatographic Shift) - stacked bar 100%
4. מטריצת Cosine Similarity - heatmap צבעוני
5. סיכום ממצאים אוטומטי

שימוש:
    python generate_report.py
    -> יוצר report.html
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd

from config import APP_NAME, APP_VERSION, PAGE_ICON
from src.analytics import cosine_similarity_matrix, generate_findings_summary
from src.data_model import (
    build_fingerprint_matrix,
    calc_total_concentration,
    get_station_summary,
    process_file,
)


# =============================================================================
# Color palette matching the screenshots
# =============================================================================
COMPOUND_COLORS = {
    "PFOS": "#e74c3c",
    "PFOA": "#e91e9e",
    "PFHxS": "#3498db",
    "PFNA": "#2ecc71",
    "PFDA": "#f39c12",
    "PFUnDA": "#9b59b6",
    "PFBS": "#1abc9c",
    "GenX": "#e67e22",
    "PFPeS": "#8e44ad",
    "PFHpA": "#d35400",
    "6:2FT": "#7f8c8d",
    "PFHpS": "#c0392b",
    "PFPeA": "#16a085",
}

SOURCE_COLORS = {
    "קידוח ניטור": "#3498db",
    "קידוח הפקה": "#2ecc71",
    "מט\"ש": "#e74c3c",
    "מעיין": "#9b59b6",
    "מים עיליים": "#f39c12",
}

DEFAULT_COLOR = "#95a5a6"


def _get_compound_color(compound: str) -> str:
    return COMPOUND_COLORS.get(compound, DEFAULT_COLOR)


def _get_source_color(source: str) -> str:
    return SOURCE_COLORS.get(source, DEFAULT_COLOR)


# =============================================================================
# Build map section (Leaflet)
# =============================================================================
def _build_map_html(df: pd.DataFrame) -> str:
    """Build Leaflet map with station markers."""
    stations = df.groupby("station_name").agg(
        lat=("lat", "first"),
        lon=("lon", "first"),
        source_type=("source_type", "first"),
        n_compounds=("compound", "nunique"),
        total_conc=("concentration", "sum"),
    ).reset_index()

    center_lat = stations["lat"].mean()
    center_lon = stations["lon"].mean()

    markers_js = ""
    for _, row in stations.iterrows():
        color = _get_source_color(row["source_type"])
        popup = (
            f"<b>{row['station_name']}</b><br>"
            f"סוג: {row['source_type']}<br>"
            f"תרכובות: {row['n_compounds']}"
        )
        markers_js += f"""
        L.circleMarker([{row['lat']:.6f}, {row['lon']:.6f}], {{
            radius: 8, fillColor: '{color}', color: '#fff',
            weight: 2, opacity: 1, fillOpacity: 0.85
        }}).addTo(map).bindPopup('{popup}');
        """

    # Legend items
    legend_items = ""
    for stype, color in SOURCE_COLORS.items():
        legend_items += f'<div style="display:flex;align-items:center;gap:6px;margin:3px 0"><span style="width:12px;height:12px;border-radius:50%;background:{color};display:inline-block;border:1px solid #fff"></span><span style="font-size:12px">{stype}</span></div>'

    return f"""
    <div id="map" style="height:450px;border-radius:8px;"></div>
    <script>
        var map = L.map('map').setView([{center_lat:.6f}, {center_lon:.6f}], 12);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }}).addTo(map);
        {markers_js}
        var legend = L.control({{position: 'bottomright'}});
        legend.onAdd = function(m) {{
            var div = L.DomUtil.create('div', 'legend');
            div.style.cssText = 'background:rgba(255,255,255,0.92);padding:10px 14px;border-radius:8px;font-family:sans-serif;box-shadow:0 2px 8px rgba(0,0,0,0.2);direction:rtl';
            div.innerHTML = '<b style="font-size:13px">סוג מקור</b>{legend_items}';
            return div;
        }};
        legend.addTo(map);
    </script>
    """


# =============================================================================
# Build attenuation bar chart (Plotly-style with pure JS)
# =============================================================================
def _build_attenuation_chart(df: pd.DataFrame, group) -> str:
    """Build total concentration bar chart with log scale."""
    totals = calc_total_concentration(df, group)
    totals = totals.sort_values("total_concentration", ascending=False)

    stations = totals["station_name"].tolist()
    concentrations = totals["total_concentration"].tolist()
    source_types = totals["source_type"].tolist()
    colors = [_get_source_color(s) for s in source_types]

    return f"""
    <div id="attenuation-chart" style="width:100%;height:420px;"></div>
    <script>
        Plotly.newPlot('attenuation-chart', [{{
            x: {json.dumps(stations, ensure_ascii=False)},
            y: {json.dumps(concentrations)},
            type: 'bar',
            marker: {{ color: {json.dumps(colors)} }},
            hovertemplate: '<b>%{{x}}</b><br>Σ{group.name}: %{{y:.2f}} {group.unit}<extra></extra>'
        }}], {{
            yaxis: {{
                type: 'log',
                title: {{ text: 'ריכוז כולל ({group.unit})', font: {{ size: 13 }} }},
                gridcolor: '#e0e0e0'
            }},
            xaxis: {{ tickangle: -35, tickfont: {{ size: 11 }} }},
            margin: {{ t: 20, b: 120, l: 60, r: 20 }},
            plot_bgcolor: '#fafafa',
            paper_bgcolor: 'white',
            hoverlabel: {{ font: {{ size: 13 }} }}
        }}, {{ responsive: true }});
    </script>
    """


# =============================================================================
# Build stacked bar chart (Chromatographic Shift)
# =============================================================================
def _build_fingerprint_chart(df: pd.DataFrame, group) -> str:
    """Build 100% stacked bar chart showing chemical composition per station."""
    fingerprint = build_fingerprint_matrix(df, group)

    stations = fingerprint.index.tolist()
    traces = []
    for compound in fingerprint.columns:
        values = fingerprint[compound].tolist()
        color = _get_compound_color(compound)
        traces.append(f"""{{
            x: {json.dumps(stations, ensure_ascii=False)},
            y: {json.dumps([round(v, 2) for v in values])},
            name: '{compound}',
            type: 'bar',
            marker: {{ color: '{color}' }},
            hovertemplate: '<b>{compound}</b>: %{{y:.1f}}%<extra></extra>'
        }}""")

    traces_js = ",".join(traces)

    return f"""
    <div id="fingerprint-chart" style="width:100%;height:420px;"></div>
    <script>
        Plotly.newPlot('fingerprint-chart', [{traces_js}], {{
            barmode: 'stack',
            yaxis: {{
                title: {{ text: 'הרכב יחסי (%)', font: {{ size: 13 }} }},
                range: [0, 100],
                gridcolor: '#e0e0e0'
            }},
            xaxis: {{ tickangle: -35, tickfont: {{ size: 11 }} }},
            margin: {{ t: 20, b: 120, l: 50, r: 20 }},
            plot_bgcolor: '#fafafa',
            paper_bgcolor: 'white',
            legend: {{ orientation: 'v', x: 1.02, y: 1, font: {{ size: 11 }} }},
            hoverlabel: {{ font: {{ size: 13 }} }}
        }}, {{ responsive: true }});
    </script>
    """


# =============================================================================
# Build Cosine Similarity Heatmap
# =============================================================================
def _build_heatmap(sim_matrix: pd.DataFrame) -> str:
    """Build Cosine Similarity heatmap table."""
    stations = sim_matrix.index.tolist()
    n = len(stations)

    # Build table rows
    rows_html = ""
    for i, station_row in enumerate(stations):
        cells = f'<td class="hm-station">{station_row}</td>'
        for j, station_col in enumerate(stations):
            val = sim_matrix.iloc[i, j]
            # Color: blue intensity based on value
            if i == j:
                bg = "#0066cc"
                text_color = "#fff"
            elif val >= 90:
                bg = f"rgba(0, 102, 204, {val/100 * 0.9:.2f})"
                text_color = "#fff"
            elif val >= 70:
                bg = f"rgba(0, 102, 204, {val/100 * 0.7:.2f})"
                text_color = "#fff"
            elif val >= 50:
                bg = f"rgba(0, 102, 204, {val/100 * 0.5:.2f})"
                text_color = "#333"
            else:
                bg = f"rgba(0, 102, 204, {val/100 * 0.3:.2f})"
                text_color = "#333"

            cells += f'<td class="hm-cell" style="background:{bg};color:{text_color}">{val:.0f}%</td>'
        rows_html += f"<tr>{cells}</tr>\n"

    # Header row
    header_cells = '<th class="hm-corner"></th>'
    for s in stations:
        header_cells += f'<th class="hm-header">{s}</th>'

    return f"""
    <div class="table-wrap">
    <table class="heatmap">
        <thead><tr>{header_cells}</tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    </div>
    """


# =============================================================================
# Build methodology box
# =============================================================================
def _build_methodology_box(n_stations: int) -> str:
    return f"""
    <div class="method-box">
        <h3>מתודולוגיה: מדד דמיון הקוסינוס (Cosine Similarity)</h3>
        <p>השוואת {n_stations} תחנות המפתח מבוצעת על בסיס פרופיל ההרכב
        הכימי כווקטור נתונים, תוך נטרול השפעת גודל הריכוזים. מידת
        הדמיון מחושבת על בסיס הזווית (θ) שבין הווקטורים:</p>
        <div class="formula">
            Similarity = cos(θ) = <span class="frac">
                <span class="num">Σ (A<sub>i</sub> × B<sub>i</sub>)</span>
                <span class="den">√Σ(A<sub>i</sub>)² × √Σ(B<sub>i</sub>)²</span>
            </span>
        </div>
        <p>ערך הקרוב ל-100% מצביע על חותמת כימית זהה. ניתוח
        אובייקטיבי זה מאפשר לאמת קיומו של נתיב זרימה (Pathway)
        בין מוקדי ההזנה לקולטנים השונים בסביבה התת-קרקעית
        והעילית.</p>
    </div>
    """


# =============================================================================
# Main HTML assembly
# =============================================================================
def generate_html_report(output_path: str = "report.html"):
    """Generate a professional standalone HTML report."""
    sample_path = os.path.join(os.path.dirname(__file__), "data", "sample", "sample_pfas.xlsx")

    if not os.path.exists(sample_path):
        print("שגיאה: קובץ הדוגמה לא נמצא. הרץ: python -m src.generate_sample_data")
        sys.exit(1)

    print("טוען ומעבד נתונים...")
    df, group = process_file(sample_path)

    print("מחשב Cosine Similarity...")
    sim_matrix = cosine_similarity_matrix(df, group)

    print("מייצר ממצאים...")
    findings = generate_findings_summary(df, group, sim_matrix)

    n_stations = df["station_name"].nunique()
    n_compounds = df["compound"].nunique()
    n_rows = len(df)
    n_sources = df["source_type"].nunique()

    print("בונה דוח HTML...")

    # Build sections
    map_html = _build_map_html(df)
    attenuation_html = _build_attenuation_chart(df, group)
    fingerprint_html = _build_fingerprint_chart(df, group)
    heatmap_html = _build_heatmap(sim_matrix)
    methodology_html = _build_methodology_box(n_stations)

    # Findings HTML
    findings_html = "\n".join(f"<li>{f}</li>" for f in findings)

    html = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{PAGE_ICON} אפיון סביבתי ופורנזי של פלומת {group.name}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                 'Helvetica Neue', Arial, sans-serif;
    background: #f0f2f5;
    color: #333;
    direction: rtl;
    line-height: 1.6;
  }}

  /* ── Header ── */
  .report-header {{
    background: linear-gradient(135deg, #0066cc 0%, #004999 100%);
    color: white;
    text-align: center;
    padding: 35px 20px 28px;
  }}
  .report-header h1 {{
    font-size: 1.9em;
    margin-bottom: 6px;
    font-weight: 700;
  }}
  .report-header .subtitle {{
    font-size: 1.05em;
    opacity: 0.9;
  }}
  .report-header .badge {{
    display: inline-block;
    background: rgba(255,255,255,0.2);
    padding: 4px 16px;
    border-radius: 20px;
    margin-top: 10px;
    font-size: 0.85em;
  }}

  /* ── Layout ── */
  .container {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 25px 20px;
  }}

  .section {{
    background: white;
    border-radius: 12px;
    padding: 28px;
    margin-bottom: 25px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  }}

  .section h2 {{
    color: #0066cc;
    font-size: 1.35em;
    margin-bottom: 8px;
    font-weight: 700;
  }}

  .section .section-desc {{
    color: #666;
    font-size: 0.92em;
    margin-bottom: 18px;
  }}

  /* ── Two column layout ── */
  .two-col {{
    display: grid;
    grid-template-columns: 1fr 1.5fr;
    gap: 25px;
  }}
  @media (max-width: 850px) {{
    .two-col {{ grid-template-columns: 1fr; }}
  }}

  .two-col-equal {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 25px;
  }}
  @media (max-width: 850px) {{
    .two-col-equal {{ grid-template-columns: 1fr; }}
  }}

  /* ── Metrics ── */
  .metrics {{
    display: flex;
    gap: 15px;
    justify-content: center;
    flex-wrap: wrap;
    margin: 20px 0;
  }}
  .metric {{
    background: #f7f9fc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px 28px;
    text-align: center;
    min-width: 140px;
  }}
  .metric .value {{
    font-size: 2em;
    font-weight: 700;
    color: #0066cc;
  }}
  .metric .label {{
    color: #666;
    font-size: 0.9em;
    margin-top: 3px;
  }}

  /* ── Methodology box ── */
  .method-box {{
    background: #f7f9fc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 22px;
  }}
  .method-box h3 {{
    color: #333;
    font-size: 1.1em;
    margin-bottom: 12px;
  }}
  .method-box p {{
    font-size: 0.92em;
    color: #555;
    margin-bottom: 10px;
  }}

  /* ── Formula ── */
  .formula {{
    background: white;
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 15px;
    text-align: center;
    font-size: 1.15em;
    margin: 14px 0;
    direction: ltr;
  }}
  .frac {{
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    vertical-align: middle;
  }}
  .frac .num {{
    border-bottom: 2px solid #333;
    padding-bottom: 4px;
  }}
  .frac .den {{
    padding-top: 4px;
  }}

  /* ── Heatmap table ── */
  .table-wrap {{ overflow-x: auto; }}

  .heatmap {{
    border-collapse: collapse;
    width: 100%;
    direction: ltr;
    text-align: center;
    font-size: 0.85em;
  }}
  .heatmap th, .heatmap td {{
    padding: 8px 6px;
    border: 1px solid #e0e0e0;
    white-space: nowrap;
  }}
  .hm-corner {{ background: #f7f9fc; }}
  .hm-header {{
    background: #f7f9fc;
    color: #333;
    font-weight: 600;
    writing-mode: vertical-rl;
    text-orientation: mixed;
    padding: 12px 6px;
    font-size: 0.85em;
    max-height: 150px;
  }}
  .hm-station {{
    background: #f7f9fc;
    font-weight: 600;
    text-align: right;
    padding: 8px 10px;
    direction: rtl;
  }}
  .hm-cell {{
    font-weight: 600;
    min-width: 52px;
  }}

  /* ── Findings ── */
  .findings {{
    background: #f0f7ff;
    border: 1px solid #b3d4fc;
    border-radius: 10px;
    padding: 22px 28px;
  }}
  .findings h3 {{
    color: #0066cc;
    margin-bottom: 14px;
    font-size: 1.15em;
  }}
  .findings ul {{
    list-style: none;
    padding: 0;
  }}
  .findings li {{
    padding: 8px 0;
    border-bottom: 1px solid #d6e8fa;
    font-size: 0.93em;
    line-height: 1.7;
  }}
  .findings li:last-child {{ border-bottom: none; }}

  /* ── Footer ── */
  .footer {{
    text-align: center;
    color: #888;
    padding: 20px;
    font-size: 0.85em;
  }}

  /* ── Leaflet fixes for RTL ── */
  .leaflet-container {{ direction: ltr; }}
</style>
</head>
<body>

<!-- ════════════════════════ HEADER ════════════════════════ -->
<div class="report-header">
    <h1>אפיון סביבתי ופורנזי של פלומת {group.name}</h1>
    <div class="subtitle">ניתוח הידרוגיאולוגי והשוואה סטטיסטית של פרופילים כימיים במרחב דליה - מעין צבי</div>
    <div class="badge">דו"ח עצמאי (Standalone HTML)</div>
</div>

<div class="container">

    <!-- ════════════════════════ METRICS ════════════════════════ -->
    <div class="metrics">
        <div class="metric">
            <div class="value">{n_stations}</div>
            <div class="label">תחנות דיגום</div>
        </div>
        <div class="metric">
            <div class="value">{n_compounds}</div>
            <div class="label">תרכובות {group.name}</div>
        </div>
        <div class="metric">
            <div class="value">{n_rows}</div>
            <div class="label">שורות נתונים</div>
        </div>
        <div class="metric">
            <div class="value">{n_sources}</div>
            <div class="label">סוגי מקור</div>
        </div>
    </div>

    <!-- ════════════════════════ 1. MAP ════════════════════════ -->
    <div class="two-col">
        <div class="section">
            {methodology_html}
        </div>
        <div class="section">
            <h2>1. פריסת כלל נקודות הדיגום במרחב הגיאוגרפי</h2>
            <p class="section-desc">המפה מציגה את {n_stations} התחנות הנדגמות (קואורדינטות ITM מומרות ל-WGS84), מסווגות לפי מדיום הידרולוגי.</p>
            {map_html}
        </div>
    </div>

    <!-- ════════════════════════ 2+3. CHARTS ════════════════════════ -->
    <div class="two-col-equal">
        <div class="section">
            <h2>2. ריכוז כולל בתחנות נבחרות (Σ{group.name} Attenuation)</h2>
            <p class="section-desc">ציר לוגריתמי. בחינת דעיכת מסת המזהם לאורך מסלולי הסעה שונים.</p>
            {attenuation_html}
        </div>
        <div class="section">
            <h2>3. הרכב כימי יחסי (Chromatographic Shift)</h2>
            <p class="section-desc">מנורמל ל-100%. התפלגות התרכובות העיקריות ב-{n_stations} תחנות המפתח.</p>
            {fingerprint_html}
        </div>
    </div>

    <!-- ════════════════════════ 4. HEATMAP ════════════════════════ -->
    <div class="section">
        <h2>4. מטריצת דמיון סטטיסטית אובייקטיבית (Cosine Similarity Heatmap)</h2>
        <p class="section-desc">חישוב מתמטי ישיר לבחינת התאמת תבניות (Pattern Matching). תחנות הרקע הדורות מסודרות משמאל להדגשת שונות.</p>
        {heatmap_html}
    </div>

    <!-- ════════════════════════ 5. FINDINGS ════════════════════════ -->
    <div class="section">
        <div class="findings">
            <h3>סיכום ממצאים מתצפיות והרכביות:</h3>
            <ul>
                {findings_html}
            </ul>
        </div>
    </div>

</div>

<!-- ════════════════════════ FOOTER ════════════════════════ -->
<div class="footer">
    <p>🔒 דוח זה נוצר מנתוני דוגמה סינתטיים | {APP_NAME} v{APP_VERSION} | נוצר אוטומטית</p>
</div>

</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"✅ הדוח נוצר בהצלחה: {output_path} ({size_kb:.0f} KB)")
    print(f"   פתח את הקובץ בדפדפן כדי לצפות בו.")


if __name__ == "__main__":
    output = os.path.join(os.path.dirname(__file__), "report.html")
    generate_html_report(output)
