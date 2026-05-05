#!/usr/bin/env python3
"""generate_report_v2.py — מחולל דוח HTML אינטראקטיבי בעיצוב Clinical.

Usage:
    cd geo-forensics
    python generate_report_v2.py "data/sample/נתוני קישון.xlsx" -o report_v2.html
    python generate_report_v2.py "data/sample/דוגמה - חגית PFAS.xlsx" -o report_hagit_v2.html
"""

import argparse
import html as html_lib
import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from config import (
    COMPOUND_COLORS, DEFAULT_COLOR, PFAS_COMPOUND_ORDER, SOURCE_COLORS,
)
from src.analytics import cosine_similarity_matrix, generate_findings_summary
from src.contaminant_groups import get_group
from src.data_model import (
    build_fingerprint_matrix,
    calc_total_concentration,
    get_station_summary,
    process_file,
)


def _fmt_total(v: float) -> str:
    if v >= 1000:
        return f"{v:.0f}"
    if v >= 100:
        return f"{v:.1f}"
    if v >= 10:
        return f"{v:.2f}"
    return f"{v:.3f}"


def _prepare_data(file_path: str, group_name: str = "PFAS") -> dict:
    """Load Excel file, run all analytics, return JSON-serializable dict."""
    df, group = process_file(file_path, group_name=group_name)

    totals = calc_total_concentration(df, group)
    max_event = (
        totals
        .loc[totals.groupby("station_name")["total_concentration"].idxmax()]
        .sort_values("total_concentration", ascending=False)
    )

    fingerprint = build_fingerprint_matrix(df, group)
    if group_name == "PFAS":
        ordered = [c for c in PFAS_COMPOUND_ORDER if c in fingerprint.columns]
        remaining = [c for c in fingerprint.columns if c not in ordered]
        fingerprint = fingerprint[ordered + remaining]

    sim_matrix = cosine_similarity_matrix(df, group)

    _nz_mask = max_event["total_concentration"] > 0
    max_event_nonzero = max_event[_nz_mask]
    zero_stn_names = set(max_event.loc[~_nz_mask, "station_name"])
    fingerprint_nonzero = fingerprint.loc[~fingerprint.index.isin(zero_stn_names)]
    if zero_stn_names:
        _nz_keep = [s for s in sim_matrix.index if s not in zero_stn_names]
        sim_matrix_nonzero = sim_matrix.loc[_nz_keep, _nz_keep]
    else:
        sim_matrix_nonzero = sim_matrix

    # PCA
    pca_data = None
    if not fingerprint_nonzero.empty and len(fingerprint_nonzero) >= 2:
        from sklearn.decomposition import PCA
        fp_values = fingerprint_nonzero.values
        n_comp = min(2, fp_values.shape[0], fp_values.shape[1])
        pca = PCA(n_components=n_comp)
        coords_pca = pca.fit_transform(fp_values)
        var_explained = (pca.explained_variance_ratio_ * 100).tolist()
        pca_data = {
            "stations": fingerprint_nonzero.index.tolist(),
            "pc1": coords_pca[:, 0].tolist(),
            "pc2": coords_pca[:, 1].tolist() if n_comp == 2 else [0.0] * len(fingerprint_nonzero),
            "var_explained": var_explained,
        }

    # MDS
    mds_data = None
    if not sim_matrix_nonzero.empty and len(sim_matrix_nonzero) >= 2:
        from sklearn.manifold import MDS
        dist_mds = 1 - sim_matrix_nonzero.values / 100
        np.fill_diagonal(dist_mds, 0)
        dist_mds = (dist_mds + dist_mds.T) / 2
        mds = MDS(n_components=2, metric="precomputed", random_state=42, normalized_stress="auto", n_init=4)
        coords_mds = mds.fit_transform(dist_mds)
        mds_data = {
            "stations": sim_matrix_nonzero.index.tolist(),
            "x": coords_mds[:, 0].tolist(),
            "y": coords_mds[:, 1].tolist(),
        }

    # Hierarchical clustering for similarity matrix ordering
    ordered_labels = sim_matrix_nonzero.index.tolist()
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
        except Exception:
            pass

    sim_ordered = sim_matrix_nonzero.loc[ordered_labels, ordered_labels] if len(ordered_labels) >= 2 else sim_matrix_nonzero

    # Top pairs
    top_pairs = []
    for i in range(len(sim_matrix_nonzero)):
        for j in range(i + 1, len(sim_matrix_nonzero)):
            v = float(sim_matrix_nonzero.iloc[i, j])
            if v >= 70:
                top_pairs.append({
                    "a": sim_matrix_nonzero.index[i],
                    "b": sim_matrix_nonzero.columns[j],
                    "v": round(v, 1),
                })
    top_pairs.sort(key=lambda x: -x["v"])

    # Findings
    findings = generate_findings_summary(df, group, sim_matrix, pca_data=pca_data)

    # Station info for map
    stations_geo = []
    for _, row in max_event.iterrows():
        lat = row.get("lat")
        lon = row.get("lon")
        if pd.notna(lat) and pd.notna(lon):
            stations_geo.append({
                "name": row["station_name"],
                "lat": float(lat),
                "lon": float(lon),
                "total": float(row["total_concentration"]),
                "source_type": row.get("source_type", ""),
                "date": row["sample_date"].strftime("%d/%m/%Y") if pd.notna(row.get("sample_date")) else "",
            })

    # Source type per station for PCA/MDS coloring
    source_map = {}
    for stn in df["station_name"].unique():
        st_rows = df[df["station_name"] == stn]["source_type"].dropna()
        source_map[stn] = st_rows.iloc[0] if len(st_rows) > 0 else ""

    # Dates
    dates = df["sample_date"].dropna()
    date_min = dates.min() if len(dates) > 0 else None
    date_max = dates.max() if len(dates) > 0 else None
    date_valid = date_min is not None and date_max is not None and date_min.year >= 1980
    date_str = f"{date_min:%d/%m/%Y} — {date_max:%d/%m/%Y}" if date_valid else "לא זוהה"

    # Insights
    _dominant = ""
    _dominant_pct = 0.0
    if not fingerprint_nonzero.empty:
        _mean_fp = fingerprint_nonzero.mean()
        _dominant = _mean_fp.idxmax()
        _dominant_pct = float(_mean_fp.max())

    _top_pair_str = "—"
    _top_pair_val = 0.0
    _n_high_pairs = 0
    if top_pairs:
        _top_pair_str = f"{top_pairs[0]['a']} · {top_pairs[0]['b']}"
        _top_pair_val = top_pairs[0]["v"]
        _n_high_pairs = sum(1 for p in top_pairs if p["v"] >= 90)

    return {
        "group_name": group.name,
        "group_unit": group.unit,
        "file_name": os.path.basename(file_path),
        "n_stations": int(df["station_name"].nunique()),
        "n_rows": int(len(df)),
        "n_compounds": int(df["compound"].nunique()) if "compound" in df.columns else 0,
        "date_str": date_str,
        "top_station": max_event_nonzero.iloc[0]["station_name"] if not max_event_nonzero.empty else "—",
        "top_value": float(max_event_nonzero.iloc[0]["total_concentration"]) if not max_event_nonzero.empty else 0,
        "n_detected": int(len(max_event_nonzero)),
        "n_total_stations": int(len(max_event)),
        "dominant_compound": _dominant,
        "dominant_pct": _dominant_pct,
        "top_pair_str": _top_pair_str,
        "top_pair_val": _top_pair_val,
        "n_high_pairs": _n_high_pairs,
        "stations_geo": stations_geo,
        "source_map": source_map,
        "source_colors": SOURCE_COLORS,
        "compound_colors": COMPOUND_COLORS,
        "default_color": DEFAULT_COLOR,
        "fingerprint": {
            "stations": fingerprint.index.tolist(),
            "compounds": fingerprint.columns.tolist(),
            "values": fingerprint.values.tolist(),
        },
        "concentration": {
            "stations": max_event_nonzero["station_name"].tolist(),
            "values": max_event_nonzero["total_concentration"].tolist(),
            "source_types": max_event_nonzero["source_type"].tolist(),
            "labels": [_fmt_total(v) for v in max_event_nonzero["total_concentration"]],
        },
        "sim_matrix": {
            "labels": ordered_labels,
            "values": sim_ordered.values.tolist() if not sim_ordered.empty else [],
        },
        "top_pairs": top_pairs[:15],
        "pca": pca_data,
        "mds": mds_data,
        "findings": findings,
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<title>PFAS Forensics — __TITLE__</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Assistant:wght@400;500;600;700&family=Frank+Ruhl+Libre:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
:root {
  --bg:#f5f3ee;--bg-2:#ebe7df;--surface:#ffffff;--surface-2:#faf8f4;
  --ink:#1c1f24;--ink-2:#4a4f57;--ink-3:#7d8189;
  --line:#e2ddd2;--line-2:#d4cdbe;
  --accent:#2a9d8f;--accent-2:#e07b39;--warn:#d97a2c;--ok:#2d8b5e;--high:#7a3d9e;
  --sim-90:#1f7a4d;--sim-70:#4ea66b;--sim-30:#d8c84a;--sim-low:#c64a3b;
  --radius:4px;--radius-lg:6px;
  --shadow-sm:0 1px 2px rgba(28,31,36,0.05);
  --font-sans:"Assistant",system-ui,sans-serif;
  --font-display:"Frank Ruhl Libre",Georgia,serif;
  --font-mono:"JetBrains Mono",ui-monospace,monospace;
}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{height:100%;font-family:var(--font-sans);background:var(--bg);color:var(--ink);
  direction:rtl;font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased;}

.app{min-height:100vh;}

/* Header */
.app-header{display:flex;align-items:center;gap:16px;padding:14px 28px;
  background:var(--surface);border-bottom:1px solid var(--line);}
.brand{display:flex;align-items:center;gap:10px;}
.brand-mark{width:38px;height:38px;border-radius:var(--radius);background:var(--ink);
  color:white;display:flex;align-items:center;justify-content:center;font-size:18px;}
.brand-name{font-family:var(--font-display);font-size:18px;font-weight:600;}
.brand-sub{font-size:11px;color:var(--ink-3);margin-top:-2px;}
.meta-bar{display:flex;gap:20px;font-size:12px;color:var(--ink-2);margin-right:auto;}
.meta .dim{color:var(--ink-3);margin-left:5px;}

/* Tabs */
.tabs{display:flex;gap:0;background:var(--surface);border-bottom:1px solid var(--line);padding:0 28px;}
.tab{font-family:var(--font-sans);font-size:13px;padding:11px 16px;
  background:none;border:none;color:var(--ink-3);cursor:pointer;
  border-bottom:2px solid transparent;margin-bottom:-1px;}
.tab:hover{color:var(--ink-2);}
.tab.on{color:var(--ink);border-bottom-color:var(--accent);font-weight:600;}

/* Main */
.main{padding:24px 28px 60px;max-width:1400px;margin:0 auto;}
.section{display:none;}
.section.active{display:block;}

/* KPI */
.kpi-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px;}
.kpi-card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);
  padding:18px 20px;position:relative;overflow:hidden;box-shadow:var(--shadow-sm);}
.kpi-card::before{content:'';position:absolute;top:0;right:0;bottom:0;width:3px;}
.kpi-a::before{background:#2a9d8f;}.kpi-b::before{background:#e07b39;}
.kpi-c::before{background:#7a3d9e;}.kpi-d::before{background:#2d8b5e;}
.kpi-label{font-size:11px;color:var(--ink-3);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;}
.kpi-value{font-family:var(--font-display);font-size:32px;font-weight:600;line-height:1;letter-spacing:-0.02em;}
.kpi-value.mono{font-family:var(--font-mono);font-size:16px;font-weight:500;letter-spacing:0;}
.kpi-unit{font-size:11px;color:var(--ink-3);margin-top:6px;}

/* Insights */
.sec-title{font-family:var(--font-display);font-size:16px;font-weight:600;margin:0 0 10px;}
.insight-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px;}
.insight-card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);
  padding:14px 16px;border-top:3px solid var(--accent);box-shadow:var(--shadow-sm);}
.insight-card.tone-warn{border-top-color:var(--warn);}
.insight-card.tone-ok{border-top-color:var(--ok);}
.insight-card.tone-high{border-top-color:var(--high);}
.insight-kicker{font-size:10.5px;color:var(--ink-3);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;}
.insight-main{font-family:var(--font-display);font-size:17px;font-weight:600;line-height:1.2;word-break:break-word;}
.insight-detail{font-family:var(--font-mono);font-size:11.5px;color:var(--ink-2);margin-top:6px;}

/* Panel */
.panel{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);
  padding:22px 24px;margin-bottom:20px;box-shadow:var(--shadow-sm);}
.panel-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;
  margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid var(--line);}
.panel-num{font-family:var(--font-mono);font-size:11px;color:var(--ink-3);letter-spacing:0.1em;margin-bottom:3px;}
.panel-title{font-family:var(--font-display);font-size:20px;font-weight:600;letter-spacing:-0.01em;}
.panel-sub{font-size:12.5px;color:var(--ink-2);margin-top:4px;max-width:60ch;}
.chart-wrap{width:100%;min-height:300px;}

/* Caveat */
.caveat{background:color-mix(in srgb,#d97a2c 8%,white);
  border:1px solid color-mix(in srgb,#d97a2c 30%,#e2ddd2);
  padding:10px 14px;border-radius:var(--radius);display:flex;align-items:flex-start;gap:10px;
  font-size:12.5px;color:var(--ink-2);line-height:1.55;margin-top:12px;}
.caveat-icon{width:22px;height:22px;border-radius:50%;background:var(--warn);color:white;
  display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;flex-shrink:0;}

/* Sim legend */
.sim-legend{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 14px;}
.sim-pill{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:100px;
  font-size:11px;border:1px solid var(--line-2);background:var(--surface-2);font-family:var(--font-mono);}
.sim-dot{width:8px;height:8px;border-radius:50%;display:inline-block;flex-shrink:0;}

/* Pairs table */
.pairs-table{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:12px;}
.pairs-table th{font-size:10.5px;color:var(--ink-3);text-transform:uppercase;letter-spacing:0.08em;
  background:var(--bg-2);padding:8px 12px;text-align:right;border-radius:var(--radius);}
.pairs-table td{padding:8px 12px;border-bottom:1px solid var(--line);}
.pairs-table .pv{font-family:var(--font-mono);font-weight:600;}
.bar-fill{display:inline-block;height:6px;border-radius:3px;vertical-align:middle;margin-right:6px;}

/* Findings */
.finding{background:var(--surface-2);border-radius:var(--radius);border-right:3px solid var(--accent);
  padding:11px 14px;margin-bottom:8px;font-size:13px;line-height:1.55;}

/* Map */
#map{width:100%;height:480px;border-radius:var(--radius-lg);border:1px solid var(--line);}

/* Compare drawer */
.drawer{position:fixed;bottom:0;left:0;right:0;background:var(--surface);
  border-top:1px solid var(--line);box-shadow:0 -8px 24px rgba(0,0,0,0.08);
  max-height:60vh;overflow-y:auto;z-index:50;transform:translateY(100%);
  transition:transform 0.25s ease;}
.drawer.open{transform:translateY(0);}
.drawer-head{display:flex;align-items:center;gap:20px;padding:14px 28px;
  border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--surface);z-index:1;}
.drawer-title{font-family:var(--font-display);font-size:20px;font-weight:600;flex:1;}
.drawer-sim{font-family:var(--font-mono);font-size:24px;font-weight:600;color:var(--accent);}
.drawer-close{width:32px;height:32px;border-radius:50%;border:1px solid var(--line-2);
  background:var(--surface);cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center;}
.drawer-body{padding:14px 28px 24px;}
.cmp-row{display:grid;grid-template-columns:80px 1fr;gap:16px;align-items:center;
  padding:5px 0;border-bottom:1px solid var(--line);}
.cmp-name{font-family:var(--font-mono);font-size:12px;font-weight:600;}
.cmp-bars{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.cmp-side{display:flex;align-items:center;gap:6px;}
.cmp-side.a{justify-content:flex-end;}
.cmp-side.b{flex-direction:row-reverse;justify-content:flex-end;}
.cmp-bar{height:14px;border-radius:2px;min-width:1px;}
.cmp-pct{font-family:var(--font-mono);font-size:11px;color:var(--ink-2);min-width:38px;text-align:center;}

/* Footer */
.report-footer{text-align:center;padding:30px;font-size:11px;color:var(--ink-3);}

/* Responsive */
@media(max-width:900px){
  .kpi-strip{grid-template-columns:repeat(2,1fr);}
  .insight-grid{grid-template-columns:repeat(2,1fr);}
  .tabs{overflow-x:auto;}
}
</style>
</head>
<body>
<div class="app">

<!-- Header -->
<div class="app-header">
  <div class="brand">
    <div class="brand-mark">🔬</div>
    <div>
      <div class="brand-name" id="hdr-title"></div>
      <div class="brand-sub" id="hdr-file"></div>
    </div>
  </div>
  <div class="meta-bar">
    <span class="meta"><span class="dim">תחנות </span><span id="hdr-n"></span></span>
    <span class="meta"><span class="dim">תרכובות </span><span id="hdr-c"></span></span>
    <span class="meta"><span class="dim">טווח </span><span id="hdr-d"></span></span>
  </div>
</div>

<!-- Tabs -->
<div class="tabs" id="tabs"></div>

<!-- Main -->
<div class="main">

  <!-- KPI -->
  <div class="kpi-strip" id="kpi-strip"></div>

  <!-- Insights -->
  <div id="insights-area"></div>

  <!-- Sections -->
  <div id="sec-map" class="section active"></div>
  <div id="sec-conc" class="section"></div>
  <div id="sec-fp" class="section"></div>
  <div id="sec-sim" class="section"></div>
  <div id="sec-pca" class="section"></div>
  <div id="sec-findings" class="section"></div>
</div>

<!-- Compare drawer -->
<div class="drawer" id="drawer">
  <div class="drawer-head">
    <div class="drawer-title" id="drawer-title"></div>
    <div class="drawer-sim" id="drawer-sim"></div>
    <button class="drawer-close" onclick="closeDrawer()">✕</button>
  </div>
  <div class="drawer-body" id="drawer-body"></div>
</div>

<div class="report-footer" id="footer"></div>

</div>

<script>
// ===== DATA (injected by Python) =====
const D = __DATA_JSON__;

// ===== Helpers =====
const esc = s => {const d=document.createElement('div');d.textContent=s;return d.innerHTML;};
const simColor = v => v>=90?'var(--sim-90)':v>=70?'var(--sim-70)':v>=30?'var(--sim-30)':'var(--sim-low)';
const simColorHex = v => v>=90?'#1f7a4d':v>=70?'#4ea66b':v>=30?'#d8c84a':'#c64a3b';
const srcColor = s => D.source_colors[s] || D.default_color;
const cmpColor = c => D.compound_colors[c] || D.default_color;

// ===== Header =====
document.getElementById('hdr-title').textContent = 'ניתוח ' + D.group_name;
document.getElementById('hdr-file').textContent = D.file_name;
document.getElementById('hdr-n').textContent = D.n_stations;
document.getElementById('hdr-c').textContent = D.n_compounds;
document.getElementById('hdr-d').textContent = D.date_str;

// ===== KPI =====
document.getElementById('kpi-strip').innerHTML = `
  <div class="kpi-card kpi-a"><div class="kpi-label">תחנות</div><div class="kpi-value">${D.n_stations}</div><div class="kpi-unit">נקודות דיגום</div></div>
  <div class="kpi-card kpi-b"><div class="kpi-label">שורות נתונים</div><div class="kpi-value">${D.n_rows.toLocaleString()}</div><div class="kpi-unit">רשומות</div></div>
  <div class="kpi-card kpi-c"><div class="kpi-label">תרכובות</div><div class="kpi-value">${D.n_compounds}</div><div class="kpi-unit">${esc(D.group_name)}</div></div>
  <div class="kpi-card kpi-d"><div class="kpi-label">טווח תאריכים</div><div class="kpi-value mono">${esc(D.date_str)}</div></div>`;

// ===== Insights =====
if (D.n_detected > 0) {
  document.getElementById('insights-area').innerHTML = `
  <div class="sec-title">תובנות מרכזיות</div>
  <div class="insight-grid">
    <div class="insight-card tone-warn"><div class="insight-kicker">Σ${esc(D.group_name)} מקסימלי</div>
      <div class="insight-main">${esc(D.top_station)}</div>
      <div class="insight-detail">${D.top_value.toFixed(2)} ${esc(D.group_unit)}</div></div>
    <div class="insight-card tone-ok"><div class="insight-kicker">שיעור גילוי</div>
      <div class="insight-main">${D.n_detected}/${D.n_total_stations}</div>
      <div class="insight-detail">תחנות עם ${esc(D.group_name)} &gt;LOD</div></div>
    <div class="insight-card"><div class="insight-kicker">תרכובת דומיננטית</div>
      <div class="insight-main">${esc(D.dominant_compound)}</div>
      <div class="insight-detail">${D.dominant_pct.toFixed(1)}% ממוצע</div></div>
    <div class="insight-card tone-high"><div class="insight-kicker">זוג דומה ביותר</div>
      <div class="insight-main" style="font-size:13px">${esc(D.top_pair_str)}</div>
      <div class="insight-detail">${D.top_pair_val.toFixed(0)}% דמיון</div></div>
    <div class="insight-card"><div class="insight-kicker">זוגות ≥90% דמיון</div>
      <div class="insight-main">${D.n_high_pairs}</div>
      <div class="insight-detail">חשודים במקור משותף</div></div>
  </div>`;
}

// ===== Tabs =====
const TABS = [
  {id:'map',label:'🗺 מפה'},
  {id:'conc',label:'📊 ריכוז סכומי'},
  {id:'fp',label:'🧪 הרכב יחסי'},
  {id:'sim',label:'🔗 דמיון'},
  {id:'pca',label:'📐 PCA / MDS'},
  {id:'findings',label:'📋 ממצאים'},
];
let activeTab = 'map';
function switchTab(id) {
  activeTab = id;
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.dataset.id===id));
  document.querySelectorAll('.section').forEach(s=>s.classList.toggle('active',s.id==='sec-'+id));
  if(id==='map' && !window._mapInit) initMap();
  if(id==='conc' && !window._concInit) initConc();
  if(id==='fp' && !window._fpInit) initFP();
  if(id==='sim' && !window._simInit) initSim();
  if(id==='pca' && !window._pcaInit) initPCA();
  if(id==='findings' && !window._findInit) initFindings();
}
const tabsEl = document.getElementById('tabs');
TABS.forEach(t=>{
  const btn = document.createElement('button');
  btn.className = 'tab' + (t.id==='map'?' on':'');
  btn.dataset.id = t.id;
  btn.textContent = t.label;
  btn.onclick = ()=>switchTab(t.id);
  tabsEl.appendChild(btn);
});

// ===== Panel helper =====
function panelHead(num, title, sub) {
  return `<div class="panel-head"><div><div class="panel-num">${num}</div>
    <div class="panel-title">${title}</div>
    ${sub?'<div class="panel-sub">'+sub+'</div>':''}</div></div>`;
}
function caveat(txt) {
  return `<div class="caveat"><div class="caveat-icon">!</div><div>${txt}</div></div>`;
}

// ===== MAP =====
function initMap() {
  window._mapInit = true;
  const el = document.getElementById('sec-map');
  el.innerHTML = `<div class="panel">${panelHead('01','מפת נקודות הדיגום',
    'מיקום התחנות. גודל הסמן פרופורציוני לריכוז הסכומי.')}<div id="map"></div></div>`;

  const map = L.map('map').setView([D.stations_geo[0]?.lat||31.9,D.stations_geo[0]?.lon||34.9], 10);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
    attribution:'OpenStreetMap', maxZoom:18}).addTo(map);

  const bounds = [];
  D.stations_geo.forEach(s => {
    const r = Math.max(6, Math.min(20, 6 + 4*Math.log10(Math.max(s.total,0.01)+1)));
    const c = srcColor(s.source_type);
    const opacity = s.total > 0 ? 0.85 : 0.25;
    L.circleMarker([s.lat,s.lon],{radius:r,color:c,fillColor:c,fillOpacity:opacity,weight:1.5})
      .bindPopup(`<div style="direction:rtl;text-align:right;font-family:Assistant,sans-serif;">
        <b>${esc(s.name)}</b><br>סוג: ${esc(s.source_type)}<br>
        Σ${esc(D.group_name)}: ${s.total.toFixed(3)} ${esc(D.group_unit)}<br>
        תאריך: ${esc(s.date)}</div>`)
      .bindTooltip(esc(s.name),{permanent:false,direction:'top'})
      .addTo(map);
    bounds.push([s.lat,s.lon]);
  });
  if(bounds.length) map.fitBounds(bounds, {padding:[30,30]});
}

// ===== CONCENTRATION =====
function initConc() {
  window._concInit = true;
  const el = document.getElementById('sec-conc');
  const c = D.concentration;
  if(!c.stations.length){el.innerHTML='<div class="panel"><p>אין נתוני ריכוז להצגה.</p></div>';return;}

  el.innerHTML = `<div class="panel">${panelHead('02','ריכוז סכומי — '+esc(D.group_name),
    'סכום ריכוזי כל התרכובות בכל תחנה, בסקאלה לוגריתמית.')}
    <div id="chart-conc" class="chart-wrap"></div>
    ${caveat('הריכוז הסכומי משקף עומס נקודתי — אינו מעיד על מקור משותף.')}</div>`;

  Plotly.newPlot('chart-conc',[{
    type:'bar',
    x:c.stations.map(s=>s.length>18?s.slice(0,18)+'…':s),
    y:c.values,
    text:c.labels,
    textposition:'outside',
    marker:{color:c.source_types.map(s=>srcColor(s)),line:{width:0}},
    customdata:c.stations,
    hovertemplate:'<b>%{customdata}</b><br>Σ'+esc(D.group_name)+': %{y:.3f} '+esc(D.group_unit)+'<extra></extra>',
  }],{
    yaxis:{type:'log',title:esc(D.group_unit)},
    xaxis:{title:'תחנה'},
    height:460,template:'plotly_white',
    font:{family:'Assistant,sans-serif',size:13},
    paper_bgcolor:'#fff',plot_bgcolor:'#fff',
    margin:{t:20,r:20,b:80,l:60},
  },{responsive:true});
}

// ===== FINGERPRINT =====
function initFP() {
  window._fpInit = true;
  const el = document.getElementById('sec-fp');
  const fp = D.fingerprint;
  if(!fp.stations.length){el.innerHTML='<div class="panel"><p>אין מספיק נתונים.</p></div>';return;}

  el.innerHTML = `<div class="panel">${panelHead('03','הרכב יחסי — '+esc(D.group_name),
    'תרומה יחסית של כל תרכובת לסך הריכוז בכל תחנה.')}
    <div id="chart-fp" class="chart-wrap"></div>
    ${caveat('הרכב יחסי תלוי בקיום מספיק תרכובות מעל סף הזיהוי.')}</div>`;

  const shortStn = fp.stations.map(s=>s.length>18?s.slice(0,18)+'…':s);
  const traces = fp.compounds.map((cmp,ci)=>({
    type:'bar',name:cmp,
    x:shortStn,
    y:fp.values.map(row=>row[ci]),
    marker:{color:cmpColor(cmp),line:{width:0}},
    hovertemplate:'<b>'+esc(cmp)+'</b><br>%{x}: %{y:.1f}%<extra></extra>',
  }));

  Plotly.newPlot('chart-fp',traces,{
    barmode:'stack',
    yaxis:{title:'אחוז (%)',range:[0,100]},
    xaxis:{title:'תחנה'},
    height:460,template:'plotly_white',
    font:{family:'Assistant,sans-serif',size:13},
    legend:{orientation:'h',yanchor:'bottom',y:1.02},
    paper_bgcolor:'#fff',plot_bgcolor:'#fff',
    margin:{t:40,r:20,b:80,l:60},
  },{responsive:true});
}

// ===== SIMILARITY =====
function initSim() {
  window._simInit = true;
  const el = document.getElementById('sec-sim');
  const sm = D.sim_matrix;
  if(!sm.labels.length||sm.labels.length<2){el.innerHTML='<div class="panel"><p>נדרשות לפחות 2 תחנות.</p></div>';return;}

  let pairsHtml = '';
  if(D.top_pairs.length){
    pairsHtml = `<div style="font-size:13px;font-weight:600;margin:16px 0 8px;">זוגות עם דמיון ≥70%</div>
    <table class="pairs-table"><thead><tr><th>תחנה א׳</th><th>תחנה ב׳</th><th>דמיון</th><th>הערה</th></tr></thead><tbody>`;
    D.top_pairs.forEach(p=>{
      const tone = p.v>=90?'sim-90':p.v>=70?'sim-70':'sim-30';
      pairsHtml += `<tr><td>${esc(p.a)}</td><td>${esc(p.b)}</td>
        <td class="pv"><span class="bar-fill" style="width:${p.v*0.6}px;background:var(--${tone});"></span>${p.v}%</td>
        <td>${p.v>=90?'גבוה מאוד':'גבוה'}</td></tr>`;
    });
    pairsHtml += '</tbody></table>';
  }

  el.innerHTML = `<div class="panel">${panelHead('04','דמיון בין חתימות '+esc(D.group_name),
    'Cosine Similarity — מידת הדמיון בין פרופילי התרכובות.')}
    <div class="sim-legend">
      <span class="sim-pill"><span class="sim-dot" style="background:var(--sim-low)"></span>0–30% נמוך</span>
      <span class="sim-pill"><span class="sim-dot" style="background:var(--sim-30)"></span>30–70% בינוני</span>
      <span class="sim-pill"><span class="sim-dot" style="background:var(--sim-70)"></span>70–90% גבוה</span>
      <span class="sim-pill"><span class="sim-dot" style="background:var(--sim-90)"></span>90–100% גבוה מאוד</span>
    </div>
    <div id="chart-sim" class="chart-wrap"></div>
    ${pairsHtml}
    ${caveat('דמיון בהרכב אינו מוכיח מקור משותף — יש לפרש עם מידע הידרולוגי ומרחבי.')}</div>`;

  Plotly.newPlot('chart-sim',[{
    type:'heatmap',z:sm.values,x:sm.labels,y:sm.labels,
    colorscale:[[0,'#c64a3b'],[0.3,'#d8c84a'],[0.7,'#4ea66b'],[0.9,'#1f7a4d'],[1,'#0d4a2e']],
    zmin:0,zmax:100,
    text:sm.values.map(r=>r.map(v=>Math.round(v)+'%')),
    texttemplate:'%{text}',
    textfont:{size:11,family:'JetBrains Mono,monospace',color:'white'},
    hovertemplate:'<b>%{x}</b> ↔ <b>%{y}</b><br>דמיון: %{z:.1f}%<extra></extra>',
    showscale:false,
  }],{
    height:Math.max(460,sm.labels.length*40+120),
    template:'plotly_white',
    font:{family:'Assistant,sans-serif',size:12},
    paper_bgcolor:'#fff',plot_bgcolor:'#fff',
    margin:{t:20,r:20,b:80,l:120},
  },{responsive:true});

  // Click handler for compare drawer
  document.getElementById('chart-sim').on('plotly_click',function(data){
    const pt = data.points[0];
    if(pt) openDrawer(pt.x, pt.y);
  });
}

// ===== PCA / MDS =====
function initPCA() {
  window._pcaInit = true;
  const el = document.getElementById('sec-pca');
  let html = `<div class="panel">${panelHead('05','PCA / MDS — ניתוח מרחבי',
    'הפחתת ממדים: תחנות קרובות = הרכב כימי דומה.')}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
      <div><div style="font-family:var(--font-display);font-size:15px;font-weight:600;margin-bottom:8px;">PCA — רכיבים ראשיים</div><div id="chart-pca" class="chart-wrap"></div></div>
      <div><div style="font-family:var(--font-display);font-size:15px;font-weight:600;margin-bottom:8px;">MDS — מיפוי מרחק כימי</div><div id="chart-mds" class="chart-wrap"></div></div>
    </div>
    ${caveat('הקרבה בגרף משקפת דמיון בהרכב — לא בהכרח מקור משותף. מיקומי הצירים ב-MDS שרירותיים.')}</div>`;
  el.innerHTML = html;

  // PCA
  if(D.pca && D.pca.stations.length>=2){
    const traces = {};
    D.pca.stations.forEach((s,i)=>{
      const src = D.source_map[s]||'';
      if(!traces[src])traces[src]={type:'scatter',mode:'markers+text',x:[],y:[],text:[],
        textposition:'top center',textfont:{size:9,family:'Assistant'},name:src,
        marker:{size:10,color:srcColor(src),line:{width:1.5,color:'white'}},
        hovertemplate:[]};
      traces[src].x.push(D.pca.pc1[i]);
      traces[src].y.push(D.pca.pc2[i]);
      traces[src].text.push(s);
      traces[src].hovertemplate.push('<b>'+esc(s)+'</b><br>'+esc(src)+'<extra></extra>');
    });
    const ve = D.pca.var_explained;
    Plotly.newPlot('chart-pca',Object.values(traces),{
      xaxis:{title:'PC1 ('+ve[0].toFixed(1)+'%)'},
      yaxis:{title:ve.length>1?'PC2 ('+ve[1].toFixed(1)+'%)':'PC2'},
      height:380,template:'plotly_white',
      font:{family:'Assistant,sans-serif',size:12},
      legend:{orientation:'h',y:1.08},
      paper_bgcolor:'#fff',plot_bgcolor:'#fff',
      margin:{t:30,r:20,b:50,l:50},
    },{responsive:true});
  } else {
    document.getElementById('chart-pca').innerHTML='<p style="color:var(--ink-3)">נדרשות לפחות 2 תחנות.</p>';
  }

  // MDS
  if(D.mds && D.mds.stations.length>=2){
    const traces = {};
    D.mds.stations.forEach((s,i)=>{
      const src = D.source_map[s]||'';
      if(!traces[src])traces[src]={type:'scatter',mode:'markers+text',x:[],y:[],text:[],
        textposition:'top center',textfont:{size:9,family:'Assistant'},name:src,
        marker:{size:10,color:srcColor(src),line:{width:1.5,color:'white'}},
        hovertemplate:[]};
      traces[src].x.push(D.mds.x[i]);
      traces[src].y.push(D.mds.y[i]);
      traces[src].text.push(s);
      traces[src].hovertemplate.push('<b>'+esc(s)+'</b><br>'+esc(src)+'<extra></extra>');
    });
    Plotly.newPlot('chart-mds',Object.values(traces),{
      xaxis:{title:'ציר 1'},yaxis:{title:'ציר 2'},
      height:380,template:'plotly_white',
      font:{family:'Assistant,sans-serif',size:12},
      legend:{orientation:'h',y:1.08},
      paper_bgcolor:'#fff',plot_bgcolor:'#fff',
      margin:{t:30,r:20,b:50,l:50},
    },{responsive:true});
  } else {
    document.getElementById('chart-mds').innerHTML='<p style="color:var(--ink-3)">נדרשות לפחות 2 תחנות.</p>';
  }
}

// ===== FINDINGS =====
function initFindings() {
  window._findInit = true;
  const el = document.getElementById('sec-findings');
  let fhtml = D.findings.map(f=>'<div class="finding">'+f+'</div>').join('');
  if(!fhtml) fhtml = '<p style="color:var(--ink-3)">אין מספיק נתונים.</p>';
  el.innerHTML = `<div class="panel">${panelHead('06','סיכום ממצאים והערות זהירות',
    'ממצאים אוטומטיים המבוססים על הנתונים.')}
    ${fhtml}
    ${caveat('כלי זה תומך בניתוח מקצועי אך אינו מחליף שיקול דעת מומחה.')}</div>`;
}

// ===== COMPARE DRAWER =====
function openDrawer(stnA, stnB) {
  const sm = D.sim_matrix;
  const ia = sm.labels.indexOf(stnA);
  const ib = sm.labels.indexOf(stnB);
  if(ia<0||ib<0||ia===ib)return;
  const simVal = sm.values[ia][ib];

  document.getElementById('drawer-title').innerHTML = esc(stnA)+' <span style="color:var(--ink-3)">↔</span> '+esc(stnB);
  document.getElementById('drawer-sim').textContent = Math.round(simVal)+'%';

  // Get fingerprints
  const fp = D.fingerprint;
  const idxA = fp.stations.indexOf(stnA);
  const idxB = fp.stations.indexOf(stnB);
  if(idxA<0||idxB<0){document.getElementById('drawer-body').innerHTML='<p>אין נתוני הרכב.</p>';return;}

  const valsA = fp.values[idxA];
  const valsB = fp.values[idxB];
  const maxV = Math.max(...valsA,...valsB,1);

  let rows = '';
  fp.compounds.forEach((cmp,ci)=>{
    const a = valsA[ci], b = valsB[ci];
    if(a<0.5 && b<0.5)return;
    const wA = (a/maxV)*100, wB = (b/maxV)*100;
    const col = cmpColor(cmp);
    rows += `<div class="cmp-row">
      <div class="cmp-name">${esc(cmp)}</div>
      <div class="cmp-bars">
        <div class="cmp-side a"><span class="cmp-pct">${a.toFixed(1)}%</span><div class="cmp-bar" style="width:${wA}%;background:${col}"></div></div>
        <div class="cmp-side b"><span class="cmp-pct">${b.toFixed(1)}%</span><div class="cmp-bar" style="width:${wB}%;background:${col}"></div></div>
      </div>
    </div>`;
  });

  document.getElementById('drawer-body').innerHTML =
    `<div style="display:grid;grid-template-columns:80px 1fr;gap:16px;margin-bottom:8px;font-size:11px;color:var(--ink-3);">
      <div></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;text-align:center;">
        <div>${esc(stnA)}</div><div>${esc(stnB)}</div></div></div>`+rows;

  document.getElementById('drawer').classList.add('open');
}
function closeDrawer(){document.getElementById('drawer').classList.remove('open');}

// ===== Footer =====
document.getElementById('footer').innerHTML =
  'דוח נוצר ב-'+esc(D.generated_at)+' • PFAS Forensics Dashboard v2 • '+esc(D.file_name);

// ===== Init first tab =====
initMap();
</script>
</body>
</html>"""


def generate_html(data: dict) -> str:
    data_json = json.dumps(data, ensure_ascii=False, default=str)
    title = html_lib.escape(f"{data['group_name']} — {data['file_name']}")
    page = HTML_TEMPLATE.replace("__DATA_JSON__", data_json)
    page = page.replace("__TITLE__", title)
    return page


def main():
    parser = argparse.ArgumentParser(
        description="מחולל דוח HTML אינטראקטיבי — עיצוב Clinical v2"
    )
    parser.add_argument("file", help="נתיב לקובץ Excel (xlsx / xls / csv)")
    parser.add_argument("-o", "--output", default=None, help="נתיב לקובץ הפלט (HTML)")
    parser.add_argument("-g", "--group", default="PFAS", help="קבוצת מזהמים (ברירת מחדל: PFAS)")
    args = parser.parse_args()

    if args.output is None:
        base = os.path.splitext(os.path.basename(args.file))[0]
        args.output = f"report_{base}_v2.html"

    print(f"[1/3] טוען נתונים מ: {args.file}")
    data = _prepare_data(args.file, group_name=args.group)

    print(f"[2/3] מייצר דוח HTML...")
    html_content = generate_html(data)

    print(f"[3/3] שומר ל: {args.output}")
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html_content)

    size_kb = os.path.getsize(args.output) / 1024
    print(f"✓ דוח נוצר בהצלחה ({size_kb:.0f} KB)")
    print(f"  {data['n_stations']} תחנות, {data['n_compounds']} תרכובות, {len(data['findings'])} ממצאים")


if __name__ == "__main__":
    main()
