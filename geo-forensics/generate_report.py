"""
generate_report.py - יצירת דוח HTML סטטי מקצועי
=================================================
מייצר קובץ HTML עצמאי הכולל:
1. פאנל בחירת תחנות אינטראקטיבי
2. מפה אינטראקטיבית (Leaflet) עם כל נקודות הדיגום
3. גרף ריכוז כולל (ΣPFAS Attenuation) - ציר לוגריתמי
4. גרף הרכב כימי יחסי (Chromatographic Shift) - stacked bar 100%
5. מטריצת Cosine Similarity - heatmap צבעוני
6. סיכום ממצאים אוטומטי

כל הנתונים מוטמעים כ-JSON בתוך ה-HTML, וכל הגרפים נבנים
דינמית ב-JavaScript כך שבחירת תחנות מעדכנת את כל התצוגה.

שימוש:
    python generate_report.py [input.xlsx] [-o output.html]
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
# Color palette
# =============================================================================
COMPOUND_COLORS = {
    "PFOS": "#e74c3c",
    "PFOA": "#e91e9e",
    "PFHxS": "#3498db",
    "PFNA": "#2ecc71",
    "PFDA": "#f39c12",
    "PFUnDA": "#9b59b6",
    "PFUnA": "#9b59b6",
    "PFBS": "#1abc9c",
    "GenX": "#e67e22",
    "PFPeS": "#8e44ad",
    "PFHpA": "#d35400",
    "6:2FT": "#7f8c8d",
    "PFHpS": "#c0392b",
    "PFPeA": "#16a085",
    "PFHxA": "#2980b9",
    "PFDoA": "#c0392b",
    "PFBA": "#27ae60",
    "ADONA": "#f1c40f",
    "PFESA": "#8e44ad",
    "PFTDA": "#d35400",
}

SOURCE_COLORS = {
    "קידוח ניטור": "#3498db",
    "קידוח הפקה": "#2ecc71",
    "קידוח": "#2980b9",
    "מט\"ש": "#e74c3c",
    "מעיין": "#9b59b6",
    "מים עיליים": "#f39c12",
    "נקודה מזוהה בנחל": "#e67e22",
    "תחנה הידרומטרית": "#1abc9c",
    "מאגר": "#8e44ad",
}

DEFAULT_COLOR = "#95a5a6"


# =============================================================================
# Prepare data for embedding as JSON
# =============================================================================
def _prepare_report_data(df, group):
    """Prepare all data structures for the report."""
    totals = calc_total_concentration(df, group)
    totals = totals.sort_values("total_concentration", ascending=False)
    fingerprint = build_fingerprint_matrix(df, group)
    sim_matrix = cosine_similarity_matrix(df, group)
    findings = generate_findings_summary(df, group, sim_matrix)

    # Station info
    stations_info = df.groupby("station_name").agg(
        lat=("lat", "first"),
        lon=("lon", "first"),
        source_type=("source_type", "first"),
        n_compounds=("compound", "nunique"),
    ).reset_index()

    stations_list = []
    for _, r in stations_info.iterrows():
        stations_list.append({
            "name": r["station_name"],
            "lat": round(r["lat"], 6),
            "lon": round(r["lon"], 6),
            "source_type": r["source_type"],
            "n_compounds": int(r["n_compounds"]),
        })

    # Totals for attenuation chart
    attenuation_list = []
    for _, r in totals.iterrows():
        attenuation_list.append({
            "name": r["station_name"],
            "total": round(r["total_concentration"], 4),
            "source_type": r["source_type"],
        })

    # Fingerprint matrix
    fp_data = {
        "stations": fingerprint.index.tolist(),
        "compounds": fingerprint.columns.tolist(),
        "values": [[round(v, 2) for v in row] for row in fingerprint.values.tolist()],
    }

    # Similarity matrix
    sim_data = {
        "stations": sim_matrix.index.tolist(),
        "values": [[round(v, 1) for v in row] for row in sim_matrix.values.tolist()],
    }

    return {
        "stations": stations_list,
        "attenuation": attenuation_list,
        "fingerprint": fp_data,
        "similarity": sim_data,
        "findings": findings,
    }


# =============================================================================
# Build methodology box (static HTML)
# =============================================================================
def _build_methodology_box(n_stations):
    return f"""
    <div class="method-box">
        <h3>מתודולוגיה: מדד דמיון הקוסינוס (Cosine Similarity)</h3>
        <p>השוואת {n_stations} תחנות המפתח מבוצעת על בסיס פרופיל ההרכב
        הכימי כווקטור נתונים, תוך נטרול השפעת גודל הריכוזים. מידת
        הדמיון מחושבת על בסיס הזווית (&theta;) שבין הווקטורים:</p>
        <div class="formula">
            Similarity = cos(&theta;) = <span class="frac">
                <span class="num">&Sigma; (A<sub>i</sub> &times; B<sub>i</sub>)</span>
                <span class="den">&radic;&Sigma;(A<sub>i</sub>)&sup2; &times; &radic;&Sigma;(B<sub>i</sub>)&sup2;</span>
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
def generate_html_report(input_path=None, output_path="report.html"):
    """Generate a professional standalone HTML report."""
    if input_path is None:
        input_path = os.path.join(os.path.dirname(__file__), "data", "sample", "sample_pfas.xlsx")

    if not os.path.exists(input_path):
        print(f"שגיאה: קובץ לא נמצא: {input_path}")
        sys.exit(1)

    print(f"טוען ומעבד נתונים מ: {os.path.basename(input_path)}...")
    df, group = process_file(input_path)

    print("מחשב ניתוחים...")
    report_data = _prepare_report_data(df, group)

    n_stations = df["station_name"].nunique()
    n_compounds = df["compound"].nunique()
    n_rows = len(df)
    n_sources = df["source_type"].nunique()

    methodology_html = _build_methodology_box(n_stations)

    # JSON data for embedding
    data_json = json.dumps(report_data, ensure_ascii=False)
    compound_colors_json = json.dumps(COMPOUND_COLORS, ensure_ascii=False)
    source_colors_json = json.dumps(SOURCE_COLORS, ensure_ascii=False)

    print("בונה דוח HTML...")

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
    color: white; text-align: center; padding: 35px 20px 28px;
  }}
  .report-header h1 {{ font-size: 1.9em; margin-bottom: 6px; font-weight: 700; }}
  .report-header .subtitle {{ font-size: 1.05em; opacity: 0.9; }}
  .report-header .badge {{
    display: inline-block; background: rgba(255,255,255,0.2);
    padding: 4px 16px; border-radius: 20px; margin-top: 10px; font-size: 0.85em;
  }}

  /* ── Layout ── */
  .container {{ max-width: 1200px; margin: 0 auto; padding: 25px 20px; }}
  .section {{
    background: white; border-radius: 12px; padding: 28px;
    margin-bottom: 25px; box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  }}
  .section h2 {{ color: #0066cc; font-size: 1.35em; margin-bottom: 8px; font-weight: 700; }}
  .section .section-desc {{ color: #666; font-size: 0.92em; margin-bottom: 18px; }}

  .two-col {{ display: grid; grid-template-columns: 1fr 1.5fr; gap: 25px; }}
  .two-col-equal {{ display: grid; grid-template-columns: 1fr 1fr; gap: 25px; }}
  @media (max-width: 850px) {{
    .two-col, .two-col-equal {{ grid-template-columns: 1fr; }}
  }}

  /* ── Metrics ── */
  .metrics {{ display: flex; gap: 15px; justify-content: center; flex-wrap: wrap; margin: 20px 0; }}
  .metric {{
    background: #f7f9fc; border: 1px solid #e2e8f0; border-radius: 10px;
    padding: 16px 28px; text-align: center; min-width: 140px;
  }}
  .metric .value {{ font-size: 2em; font-weight: 700; color: #0066cc; }}
  .metric .label {{ color: #666; font-size: 0.9em; margin-top: 3px; }}

  /* ── Station filter panel ── */
  .filter-panel {{
    background: white; border-radius: 12px; padding: 20px 24px;
    margin-bottom: 25px; box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  }}
  .filter-header {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 14px; flex-wrap: wrap; gap: 10px;
  }}
  .filter-header h2 {{ color: #0066cc; font-size: 1.2em; font-weight: 700; margin: 0; }}
  .filter-actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
  .filter-actions button {{
    padding: 5px 14px; border-radius: 6px; border: 1px solid #ccc;
    background: #f7f9fc; cursor: pointer; font-size: 0.85em;
    font-family: inherit; transition: all 0.15s;
  }}
  .filter-actions button:hover {{ background: #e8f0fe; border-color: #0066cc; }}
  .filter-actions button.active {{ background: #0066cc; color: white; border-color: #0066cc; }}

  .filter-grid {{
    display: flex; flex-wrap: wrap; gap: 6px;
  }}
  .station-chip {{
    display: inline-flex; align-items: center; gap: 5px;
    padding: 5px 12px; border-radius: 18px;
    border: 2px solid #ddd; background: #f9f9f9;
    cursor: pointer; font-size: 0.85em; transition: all 0.15s;
    user-select: none;
  }}
  .station-chip:hover {{ border-color: #0066cc; background: #f0f5ff; }}
  .station-chip.selected {{
    border-color: #0066cc; background: #e8f0fe; font-weight: 600;
  }}
  .station-chip .dot {{
    width: 10px; height: 10px; border-radius: 50%; display: inline-block;
  }}
  .filter-count {{
    font-size: 0.88em; color: #666; margin-top: 10px;
  }}

  /* ── Methodology box ── */
  .method-box {{
    background: #f7f9fc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 22px;
  }}
  .method-box h3 {{ color: #333; font-size: 1.1em; margin-bottom: 12px; }}
  .method-box p {{ font-size: 0.92em; color: #555; margin-bottom: 10px; }}
  .formula {{
    background: white; border: 1px solid #ddd; border-radius: 8px;
    padding: 15px; text-align: center; font-size: 1.15em; margin: 14px 0; direction: ltr;
  }}
  .frac {{ display: inline-flex; flex-direction: column; align-items: center; vertical-align: middle; }}
  .frac .num {{ border-bottom: 2px solid #333; padding-bottom: 4px; }}
  .frac .den {{ padding-top: 4px; }}

  /* ── Heatmap table ── */
  .table-wrap {{ overflow-x: auto; }}
  .heatmap {{
    border-collapse: collapse; width: 100%; direction: ltr;
    text-align: center; font-size: 0.85em;
  }}
  .heatmap th, .heatmap td {{ padding: 8px 6px; border: 1px solid #e0e0e0; white-space: nowrap; }}
  .hm-corner {{ background: #f7f9fc; }}
  .hm-header {{
    background: #f7f9fc; color: #333; font-weight: 600;
    writing-mode: vertical-rl; text-orientation: mixed;
    padding: 12px 6px; font-size: 0.85em; max-height: 150px;
  }}
  .hm-station {{
    background: #f7f9fc; font-weight: 600; text-align: right;
    padding: 8px 10px; direction: rtl;
  }}
  .hm-cell {{ font-weight: 600; min-width: 52px; }}

  /* ── Findings ── */
  .findings {{
    background: #f0f7ff; border: 1px solid #b3d4fc;
    border-radius: 10px; padding: 22px 28px;
  }}
  .findings h3 {{ color: #0066cc; margin-bottom: 14px; font-size: 1.15em; }}
  .findings ul {{ list-style: none; padding: 0; }}
  .findings li {{
    padding: 8px 0; border-bottom: 1px solid #d6e8fa;
    font-size: 0.93em; line-height: 1.7;
  }}
  .findings li:last-child {{ border-bottom: none; }}

  .footer {{ text-align: center; color: #888; padding: 20px; font-size: 0.85em; }}
  .leaflet-container {{ direction: ltr; }}
</style>
</head>
<body>

<!-- ════════════════════════ HEADER ════════════════════════ -->
<div class="report-header">
    <h1>אפיון סביבתי ופורנזי של פלומת {group.name}</h1>
    <div class="subtitle">ניתוח הידרוגיאולוגי והשוואה סטטיסטית של פרופילים כימיים</div>
    <div class="badge">דו"ח עצמאי (Standalone HTML)</div>
</div>

<div class="container">

    <!-- ════════════════════════ METRICS ════════════════════════ -->
    <div class="metrics">
        <div class="metric"><div class="value">{n_stations}</div><div class="label">תחנות דיגום</div></div>
        <div class="metric"><div class="value">{n_compounds}</div><div class="label">תרכובות {group.name}</div></div>
        <div class="metric"><div class="value">{n_rows}</div><div class="label">שורות נתונים</div></div>
        <div class="metric"><div class="value">{n_sources}</div><div class="label">סוגי מקור</div></div>
    </div>

    <!-- ════════════════════════ STATION FILTER ════════════════════════ -->
    <div class="filter-panel">
        <div class="filter-header">
            <h2>בחירת נקודות דיגום</h2>
            <div class="filter-actions">
                <button onclick="selectAll()">בחר הכל</button>
                <button onclick="selectNone()">נקה הכל</button>
            </div>
        </div>
        <div class="filter-actions" id="source-filters" style="margin-bottom:12px"></div>
        <div class="filter-grid" id="station-chips"></div>
        <div class="filter-count" id="filter-count"></div>
    </div>

    <!-- ════════════════════════ MAP + METHODOLOGY ════════════════════════ -->
    <div class="two-col">
        <div class="section">
            {methodology_html}
        </div>
        <div class="section">
            <h2>1. פריסת נקודות הדיגום במרחב הגיאוגרפי</h2>
            <p class="section-desc">המפה מציגה את התחנות הנבחרות (קואורדינטות ITM מומרות ל-WGS84), מסווגות לפי מדיום הידרולוגי.</p>
            <div id="map" style="height:450px;border-radius:8px;"></div>
        </div>
    </div>

    <!-- ════════════════════════ CHARTS ════════════════════════ -->
    <div class="two-col-equal">
        <div class="section">
            <h2>2. ריכוז כולל בתחנות נבחרות (&Sigma;{group.name} Attenuation)</h2>
            <p class="section-desc">ציר לוגריתמי. בחינת דעיכת מסת המזהם לאורך מסלולי הסעה שונים.</p>
            <div id="attenuation-chart" style="width:100%;height:420px;"></div>
        </div>
        <div class="section">
            <h2>3. הרכב כימי יחסי (Chromatographic Shift)</h2>
            <p class="section-desc">מנורמל ל-100%. התפלגות התרכובות העיקריות בתחנות הנבחרות.</p>
            <div id="fingerprint-chart" style="width:100%;height:420px;"></div>
        </div>
    </div>

    <!-- ════════════════════════ HEATMAP ════════════════════════ -->
    <div class="section">
        <h2>4. מטריצת דמיון סטטיסטית אובייקטיבית (Cosine Similarity Heatmap)</h2>
        <p class="section-desc">חישוב מתמטי ישיר לבחינת התאמת תבניות (Pattern Matching).</p>
        <div class="table-wrap" id="heatmap-container"></div>
    </div>

    <!-- ════════════════════════ FINDINGS ════════════════════════ -->
    <div class="section">
        <div class="findings">
            <h3>סיכום ממצאים מתצפיות והרכביות:</h3>
            <ul id="findings-list"></ul>
        </div>
    </div>

</div>

<div class="footer">
    <p>{APP_NAME} v{APP_VERSION} | נוצר אוטומטית מקובץ: {os.path.basename(input_path)}</p>
</div>

<!-- ════════════════════════ DATA + LOGIC ════════════════════════ -->
<script>
// ── Embedded data ──
const DATA = {data_json};
const COMPOUND_COLORS = {compound_colors_json};
const SOURCE_COLORS = {source_colors_json};
const DEFAULT_COLOR = '{DEFAULT_COLOR}';
const GROUP_UNIT = '{group.unit}';
const GROUP_NAME = '{group.name}';

// ── State ──
let selectedStations = new Set(DATA.stations.map(s => s.name));
let map, markers = [];

// ── Helpers ──
function getSourceColor(s) {{ return SOURCE_COLORS[s] || DEFAULT_COLOR; }}
function getCompoundColor(c) {{ return COMPOUND_COLORS[c] || DEFAULT_COLOR; }}

// ── Filter panel ──
function buildFilterPanel() {{
    // Source type filter buttons
    const sourceTypes = [...new Set(DATA.stations.map(s => s.source_type))];
    const srcDiv = document.getElementById('source-filters');
    sourceTypes.forEach(st => {{
        const btn = document.createElement('button');
        btn.textContent = st;
        btn.style.borderRight = '4px solid ' + getSourceColor(st);
        btn.onclick = () => toggleSourceType(st);
        srcDiv.appendChild(btn);
    }});

    // Station chips
    const grid = document.getElementById('station-chips');
    DATA.stations.forEach(s => {{
        const chip = document.createElement('div');
        chip.className = 'station-chip selected';
        chip.dataset.station = s.name;
        chip.dataset.source = s.source_type;
        chip.innerHTML = '<span class="dot" style="background:' + getSourceColor(s.source_type) + '"></span>' + s.name;
        chip.onclick = () => toggleStation(s.name);
        grid.appendChild(chip);
    }});
    updateFilterCount();
}}

function toggleStation(name) {{
    if (selectedStations.has(name)) selectedStations.delete(name);
    else selectedStations.add(name);
    updateUI();
}}

function toggleSourceType(st) {{
    const stationsOfType = DATA.stations.filter(s => s.source_type === st).map(s => s.name);
    const allSelected = stationsOfType.every(n => selectedStations.has(n));
    stationsOfType.forEach(n => {{
        if (allSelected) selectedStations.delete(n);
        else selectedStations.add(n);
    }});
    updateUI();
}}

function selectAll() {{
    DATA.stations.forEach(s => selectedStations.add(s.name));
    updateUI();
}}

function selectNone() {{
    selectedStations.clear();
    updateUI();
}}

function updateFilterCount() {{
    document.getElementById('filter-count').textContent =
        selectedStations.size + ' מתוך ' + DATA.stations.length + ' תחנות נבחרו';
}}

function updateChipStyles() {{
    document.querySelectorAll('.station-chip').forEach(chip => {{
        chip.classList.toggle('selected', selectedStations.has(chip.dataset.station));
    }});
}}

// ── Map ──
function initMap() {{
    const lats = DATA.stations.map(s => s.lat);
    const lons = DATA.stations.map(s => s.lon);
    const cLat = lats.reduce((a,b) => a+b, 0) / lats.length;
    const cLon = lons.reduce((a,b) => a+b, 0) / lons.length;

    map = L.map('map').setView([cLat, cLon], 12);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        attribution: '&copy; OpenStreetMap contributors'
    }}).addTo(map);

    // Legend
    const legend = L.control({{position: 'bottomright'}});
    legend.onAdd = function() {{
        const div = L.DomUtil.create('div');
        div.style.cssText = 'background:rgba(255,255,255,0.92);padding:10px 14px;border-radius:8px;font-family:sans-serif;box-shadow:0 2px 8px rgba(0,0,0,0.2);direction:rtl';
        const types = [...new Set(DATA.stations.map(s => s.source_type))];
        let html = '<b style="font-size:13px">סוג מקור</b>';
        types.forEach(t => {{
            html += '<div style="display:flex;align-items:center;gap:6px;margin:3px 0">' +
                '<span style="width:12px;height:12px;border-radius:50%;background:' + getSourceColor(t) +
                ';display:inline-block;border:1px solid #fff"></span>' +
                '<span style="font-size:12px">' + t + '</span></div>';
        }});
        div.innerHTML = html;
        return div;
    }};
    legend.addTo(map);

    updateMap();
}}

function updateMap() {{
    markers.forEach(m => map.removeLayer(m));
    markers = [];

    DATA.stations.filter(s => selectedStations.has(s.name)).forEach(s => {{
        const m = L.circleMarker([s.lat, s.lon], {{
            radius: 8, fillColor: getSourceColor(s.source_type), color: '#fff',
            weight: 2, opacity: 1, fillOpacity: 0.85
        }}).addTo(map).bindPopup(
            '<b>' + s.name + '</b><br>סוג: ' + s.source_type + '<br>תרכובות: ' + s.n_compounds
        );
        markers.push(m);
    }});

    if (markers.length > 0) {{
        const group = L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.15));
    }}
}}

// ── Attenuation chart ──
function updateAttenuationChart() {{
    const filtered = DATA.attenuation.filter(a => selectedStations.has(a.name));
    Plotly.react('attenuation-chart', [{{
        x: filtered.map(a => a.name),
        y: filtered.map(a => a.total),
        type: 'bar',
        marker: {{ color: filtered.map(a => getSourceColor(a.source_type)) }},
        hovertemplate: '<b>%{{x}}</b><br>&Sigma;' + GROUP_NAME + ': %{{y:.2f}} ' + GROUP_UNIT + '<extra></extra>'
    }}], {{
        yaxis: {{ type: 'log', title: {{ text: 'ריכוז כולל (' + GROUP_UNIT + ')', font: {{ size: 13 }} }}, gridcolor: '#e0e0e0' }},
        xaxis: {{ tickangle: -35, tickfont: {{ size: 11 }} }},
        margin: {{ t: 20, b: 120, l: 60, r: 20 }},
        plot_bgcolor: '#fafafa', paper_bgcolor: 'white',
        hoverlabel: {{ font: {{ size: 13 }} }}
    }}, {{ responsive: true }});
}}

// ── Fingerprint chart ──
function updateFingerprintChart() {{
    const fp = DATA.fingerprint;
    const selIdx = [];
    fp.stations.forEach((s, i) => {{ if (selectedStations.has(s)) selIdx.push(i); }});

    const traces = fp.compounds.map((compound, ci) => ({{
        x: selIdx.map(i => fp.stations[i]),
        y: selIdx.map(i => fp.values[i][ci]),
        name: compound,
        type: 'bar',
        marker: {{ color: getCompoundColor(compound) }},
        hovertemplate: '<b>' + compound + '</b>: %{{y:.1f}}%<extra></extra>'
    }}));

    Plotly.react('fingerprint-chart', traces, {{
        barmode: 'stack',
        yaxis: {{ title: {{ text: 'הרכב יחסי (%)', font: {{ size: 13 }} }}, range: [0, 100], gridcolor: '#e0e0e0' }},
        xaxis: {{ tickangle: -35, tickfont: {{ size: 11 }} }},
        margin: {{ t: 20, b: 120, l: 50, r: 20 }},
        plot_bgcolor: '#fafafa', paper_bgcolor: 'white',
        legend: {{ orientation: 'v', x: 1.02, y: 1, font: {{ size: 11 }} }},
        hoverlabel: {{ font: {{ size: 13 }} }}
    }}, {{ responsive: true }});
}}

// ── Heatmap ──
function updateHeatmap() {{
    const sim = DATA.similarity;
    const selIdx = [];
    sim.stations.forEach((s, i) => {{ if (selectedStations.has(s)) selIdx.push(i); }});

    if (selIdx.length === 0) {{
        document.getElementById('heatmap-container').innerHTML = '<p style="color:#999;text-align:center;padding:20px">בחר תחנות כדי להציג את מטריצת הדמיון</p>';
        return;
    }}

    let html = '<table class="heatmap"><thead><tr><th class="hm-corner"></th>';
    selIdx.forEach(j => {{ html += '<th class="hm-header">' + sim.stations[j] + '</th>'; }});
    html += '</tr></thead><tbody>';

    selIdx.forEach(i => {{
        html += '<tr><td class="hm-station">' + sim.stations[i] + '</td>';
        selIdx.forEach(j => {{
            const val = sim.values[i][j];
            let bg, tc;
            if (i === j) {{ bg = '#0066cc'; tc = '#fff'; }}
            else if (val >= 90) {{ bg = 'rgba(0,102,204,' + (val/100*0.9).toFixed(2) + ')'; tc = '#fff'; }}
            else if (val >= 70) {{ bg = 'rgba(0,102,204,' + (val/100*0.7).toFixed(2) + ')'; tc = '#fff'; }}
            else if (val >= 50) {{ bg = 'rgba(0,102,204,' + (val/100*0.5).toFixed(2) + ')'; tc = '#333'; }}
            else {{ bg = 'rgba(0,102,204,' + (val/100*0.3).toFixed(2) + ')'; tc = '#333'; }}
            html += '<td class="hm-cell" style="background:' + bg + ';color:' + tc + '">' + val.toFixed(0) + '%</td>';
        }});
        html += '</tr>';
    }});

    html += '</tbody></table>';
    document.getElementById('heatmap-container').innerHTML = html;
}}

// ── Findings ──
function renderFindings() {{
    const ul = document.getElementById('findings-list');
    ul.innerHTML = DATA.findings.map(f => '<li>' + f + '</li>').join('');
}}

// ── Master update ──
function updateUI() {{
    updateChipStyles();
    updateFilterCount();
    updateMap();
    updateAttenuationChart();
    updateFingerprintChart();
    updateHeatmap();
}}

// ── Init ──
document.addEventListener('DOMContentLoaded', function() {{
    buildFilterPanel();
    initMap();
    updateAttenuationChart();
    updateFingerprintChart();
    updateHeatmap();
    renderFindings();
}});
</script>

</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"✅ הדוח נוצר בהצלחה: {output_path} ({size_kb:.0f} KB)")
    print(f"   פתח את הקובץ בדפדפן כדי לצפות בו.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate PFAS forensic HTML report")
    parser.add_argument("input_file", nargs="?", default=None, help="Path to Excel/CSV data file")
    parser.add_argument("-o", "--output", default=None, help="Output HTML file path")
    args = parser.parse_args()

    out = args.output or os.path.join(os.path.dirname(__file__), "report.html")
    generate_html_report(input_path=args.input_file, output_path=out)
