"""generate_report.py - יצירת דוח HTML סטטי מ-Excel."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, leaves_list

from config import (
    APP_NAME, APP_VERSION, COMPOUND_COLORS, DEFAULT_COLOR, PAGE_ICON,
    PFAS_COMPOUND_ORDER, SOURCE_COLORS,
)
from src.analytics import cosine_similarity_matrix, generate_findings_summary
from src.data_model import (
    build_fingerprint_matrix,
    calc_total_concentration,
    get_station_summary,
    process_file,
)


# =============================================================================
# MDS via SMACOF algorithm (replaces sklearn.manifold.MDS)
# =============================================================================
def _mds_smacof(dist_matrix, n_components=2, n_init=4, max_iter=300, eps=1e-6, random_state=42):
    """
    Metric MDS using SMACOF (Scaling by MAjorizing a COmplicated Function).
    Works on a precomputed distance matrix.

    Returns:
        (coords, stress) — coordinates array and final stress value
    """
    n = len(dist_matrix)
    rng = np.random.RandomState(random_state)
    best_coords = None
    best_stress = np.inf

    for init_run in range(n_init):
        # Random initialization
        X = rng.randn(n, n_components)

        for iteration in range(max_iter):
            # Compute current distances
            diff = X[:, np.newaxis, :] - X[np.newaxis, :, :]
            current_dist = np.sqrt((diff ** 2).sum(axis=2))
            current_dist = np.maximum(current_dist, 1e-12)

            # Stress (raw)
            stress = np.sqrt(((dist_matrix - current_dist) ** 2).sum() / max(1, (dist_matrix ** 2).sum()))

            # Guttman transform
            B = np.zeros_like(dist_matrix)
            mask = current_dist > 1e-12
            B[mask] = -dist_matrix[mask] / current_dist[mask]
            np.fill_diagonal(B, 0)
            np.fill_diagonal(B, -B.sum(axis=1))

            X_new = B @ X / n

            # Check convergence
            change = np.sqrt(((X_new - X) ** 2).sum())
            X = X_new
            if change < eps:
                break

        if stress < best_stress:
            best_stress = stress
            best_coords = X.copy()

    return best_coords, best_stress


# =============================================================================
# Prepare data for embedding as JSON
# =============================================================================
def _prepare_report_data(df, group):
    """Prepare all data structures for the report."""
    totals = calc_total_concentration(df, group)
    totals = totals.sort_values("total_concentration", ascending=False)
    fingerprint = build_fingerprint_matrix(df, group)
    sim_matrix = cosine_similarity_matrix(df, group)
    # findings will be generated after PCA data is ready

    # --- Determine max-event per station (date + total) ---
    max_event_per_station = (
        totals.loc[totals.groupby("station_name")["total_concentration"].idxmax()]
        .set_index("station_name")
    )

    # Station info (enriched with max total + selected date)
    stations_info = df.groupby("station_name").agg(
        lat=("lat", "first"),
        lon=("lon", "first"),
        source_type=("source_type", "first"),
        n_compounds=("compound", "nunique"),
    ).reset_index()

    stations_list = []
    for _, r in stations_info.iterrows():
        name = r["station_name"]
        max_total = 0.0
        selected_date = ""
        if name in max_event_per_station.index:
            row = max_event_per_station.loc[name]
            max_total = float(row["total_concentration"])
            selected_date = str(row["sample_date"])[:10]
        stations_list.append({
            "name": name,
            "lat": round(r["lat"], 6),
            "lon": round(r["lon"], 6),
            "source_type": r["source_type"],
            "n_compounds": int(r["n_compounds"]),
            "max_total": round(max_total, 4),
            "selected_date": selected_date,
        })

    # Attenuation: ONE bar per station (max event only), sorted descending
    # Filter out stations with zero concentration (< LOD)
    attenuation_list = []
    for _, r in max_event_per_station.reset_index().sort_values(
        "total_concentration", ascending=False
    ).iterrows():
        if r["total_concentration"] > 0:
            attenuation_list.append({
                "name": r["station_name"],
                "total": round(r["total_concentration"], 4),
                "source_type": r["source_type"],
                "date": str(r["sample_date"])[:10],
            })

    # --- Reorder compounds: S/A order for PFAS, top-station proportion for others ---
    if group.name == "PFAS":
        ordered = [c for c in PFAS_COMPOUND_ORDER if c in fingerprint.columns]
        remaining = [c for c in fingerprint.columns if c not in ordered]
        sorted_compounds = ordered + remaining
    else:
        top_station = max_event_per_station["total_concentration"].idxmax()
        if top_station in fingerprint.index:
            top_profile = fingerprint.loc[top_station]
            sorted_compounds = top_profile.sort_values(ascending=False).index.tolist()
        else:
            sorted_compounds = fingerprint.columns.tolist()

    # Reorder fingerprint columns
    fingerprint = fingerprint[sorted_compounds]

    # Filter fingerprint: remove stations with zero total concentration
    non_zero_stations = [
        stn for stn in fingerprint.index
        if stn in max_event_per_station.index
        and max_event_per_station.loc[stn, "total_concentration"] > 0
    ]
    fingerprint_filtered = fingerprint.loc[non_zero_stations]

    # Fingerprint matrix (with per-station absolute totals for labels)
    fp_totals = []
    for stn in fingerprint_filtered.index.tolist():
        fp_totals.append(round(float(max_event_per_station.loc[stn, "total_concentration"]), 3))

    fp_data = {
        "stations": fingerprint_filtered.index.tolist(),
        "compounds": fingerprint_filtered.columns.tolist(),
        "values": [[round(v, 2) for v in row] for row in fingerprint_filtered.values.tolist()],
        "totals": fp_totals,
    }

    # --- PFOS/PFHxS ratio per station (only non-zero stations) ---
    pfos_col = "PFOS" if "PFOS" in fingerprint_filtered.columns else None
    pfhxs_col = "PFHxS" if "PFHxS" in fingerprint_filtered.columns else None
    ratios = {}
    if pfos_col and pfhxs_col:
        for stn in fingerprint_filtered.index:
            pfos_val = fingerprint_filtered.loc[stn, pfos_col]
            pfhxs_val = fingerprint_filtered.loc[stn, pfhxs_col]
            if pfhxs_val > 0:
                ratios[stn] = round(pfos_val / pfhxs_val, 2)
            else:
                ratios[stn] = None

    # Similarity matrix — filter out zero-concentration stations, then cluster-sort
    sim_matrix_filtered = sim_matrix.loc[non_zero_stations, non_zero_stations]
    sim_vals = sim_matrix_filtered.values
    # Distance = 1 - similarity (normalized to 0-1)
    dist = 1 - sim_vals / 100.0
    np.fill_diagonal(dist, 0)
    # Condensed distance matrix for linkage
    n = len(dist)
    condensed = []
    for i in range(n):
        for j in range(i + 1, n):
            condensed.append(dist[i][j])
    condensed = np.array(condensed)
    if len(condensed) > 0 and np.all(np.isfinite(condensed)):
        Z = linkage(condensed, method='average')
        order = leaves_list(Z).tolist()
    else:
        order = list(range(n))

    clustered_stations = [sim_matrix_filtered.index[i] for i in order]
    sim_data = {
        "stations": clustered_stations,
        "values": [[round(sim_matrix_filtered.loc[a, b], 1) for b in clustered_stations] for a in clustered_stations],
    }

    # --- PCA: 2D projection using numpy SVD (no sklearn needed) ---
    fp_vals = fingerprint_filtered.values
    pca_data = {"stations": [], "pc1": [], "pc2": [], "var_explained": [0, 0]}

    if len(fp_vals) >= 2:
        # Center the data
        mean_vec = fp_vals.mean(axis=0)
        centered = fp_vals - mean_vec
        # SVD
        U, S, Vt = np.linalg.svd(centered, full_matrices=False)
        # Project onto first 2 components
        n_components = min(2, len(S))
        coords = centered @ Vt[:n_components].T
        # Explained variance ratio
        var_all = (S ** 2) / (len(fp_vals) - 1)
        total_var = var_all.sum()
        var_explained = [(var_all[i] / total_var * 100) if total_var > 0 else 0 for i in range(n_components)]
        pca_data["var_explained"] = [round(v, 1) for v in var_explained]

        for i, stn in enumerate(fingerprint_filtered.index):
            pca_data["stations"].append(stn)
            pca_data["pc1"].append(round(float(coords[i, 0]), 3))
            pca_data["pc2"].append(round(float(coords[i, 1]) if n_components > 1 else 0, 3))

    # --- MDS: 2D projection based on cosine distance (SMACOF, no sklearn) ---
    mds_data = {"stations": [], "x": [], "y": [], "stress": 0}
    if len(non_zero_stations) >= 2:
        cos_dist = 1 - sim_matrix_filtered.values / 100.0
        np.fill_diagonal(cos_dist, 0)
        cos_dist = (cos_dist + cos_dist.T) / 2  # ensure symmetry
        mds_coords, stress = _mds_smacof(cos_dist, n_components=2, n_init=4, random_state=42)
        mds_data["stress"] = round(float(stress), 4)
        for i, stn in enumerate(sim_matrix_filtered.index):
            mds_data["stations"].append(stn)
            mds_data["x"].append(round(float(mds_coords[i, 0]), 4))
            mds_data["y"].append(round(float(mds_coords[i, 1]), 4))

    # Generate findings summary with PCA data
    findings = generate_findings_summary(df, group, sim_matrix, pca_data=pca_data)

    return {
        "stations": stations_list,
        "attenuation": attenuation_list,
        "fingerprint": fp_data,
        "similarity": sim_data,
        "findings": findings,
        "pfos_pfhxs_ratios": ratios,
        "pca": pca_data,
        "mds": mds_data,
        "group_unit": group.unit,
    }


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
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
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

  /* ── Max-concentration banner ── */
  .max-banner {{
    background: linear-gradient(90deg, #fff3cd 0%, #ffeeba 100%);
    border: 1px solid #ffc107; border-radius: 10px;
    padding: 14px 22px; margin-bottom: 25px;
    display: flex; align-items: center; gap: 12px;
    font-size: 0.95em; color: #856404;
  }}
  .max-banner .icon {{ font-size: 1.5em; }}

  /* ── Methodology box (compact) ── */
  .method-box-compact {{
    background: #f7f9fc; border: 1px solid #e2e8f0; border-radius: 10px;
    padding: 14px 20px; margin-bottom: 18px;
    display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
  }}
  .method-box-compact .method-text {{ font-size: 0.88em; color: #555; flex: 1; min-width: 200px; }}
  .method-box-compact .method-text b {{ color: #333; }}
  .method-box-compact .formula-inline {{
    background: white; border: 1px solid #ddd; border-radius: 8px;
    padding: 8px 16px; font-size: 0.95em; direction: ltr; white-space: nowrap;
  }}
  .frac {{ display: inline-flex; flex-direction: column; align-items: center; vertical-align: middle; }}
  .frac .num {{ border-bottom: 2px solid #333; padding-bottom: 3px; font-size: 0.9em; }}
  .frac .den {{ padding-top: 3px; font-size: 0.9em; }}

  /* ── Ratio table ── */
  .ratio-table {{ border-collapse: collapse; width: 100%; font-size: 0.88em; }}
  .ratio-table th {{ background: #f7f9fc; padding: 8px 10px; border: 1px solid #e0e0e0; font-weight: 600; text-align: right; }}
  .ratio-table td {{ padding: 8px 10px; border: 1px solid #e0e0e0; text-align: center; }}
  .ratio-table tr:hover {{ background: #f0f5ff; }}

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
  .map-label {{ background: none; border: none; }}
  .map-label span {{
    font-size: 11px; color: #333; white-space: nowrap;
    text-shadow: 1px 1px 2px #fff, -1px -1px 2px #fff, 1px -1px 2px #fff, -1px 1px 2px #fff;
    direction: rtl; line-height: 1.3;
  }}
  .map-label b {{ color: #0066cc; }}
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

    <!-- ════════════════════════ MAX-CONCENTRATION BANNER ════════════════════════ -->
    <div class="max-banner">
        <span class="icon">&#9888;</span>
        <div><b>כלל הנתונים, הגרפים והניתוחים בדוח זה מתייחסים לאירוע הדיגום בו נמדד הריכוז הסכומי המירבי (&Sigma;{group.name}) בכל תחנה.</b>
        גישה זו מייצגת את תרחיש החשיפה המקסימלי ואת החותמת הכימית הבולטת ביותר.</div>
    </div>

    <!-- ════════════════════════ MAP ════════════════════════ -->
    <div class="section">
        <h2>1. פריסת נקודות הדיגום במרחב הגיאוגרפי</h2>
        <p class="section-desc">גודל הסמן פרופורציונלי ל-&Sigma;{group.name} המירבי בתחנה. לחיצה על סמן מציגה פרטים כולל התאריך הנבחר.</p>
        <div id="map" style="height:480px;border-radius:8px;"></div>
    </div>

    <!-- ════════════════════════ CHARTS ════════════════════════ -->
    <div class="two-col-equal">
        <div class="section">
            <h2>2. ריכוז כולל — &Sigma;{group.name} Attenuation</h2>
            <p class="section-desc">ציר לוגריתמי. עמודה אחת לכל תחנה (אירוע מירבי). בחינת דעיכת מסת המזהם לאורך מסלולי הסעה.</p>
            <div style="width:100%;height:420px;"><canvas id="attenuation-canvas"></canvas></div>
        </div>
        <div class="section">
            <h2>3. הרכב כימי יחסי — Chromatographic Shift</h2>
            <p class="section-desc">מנורמל ל-100%. מעל כל עמודה מוצג הריכוז הסכומי ({group.unit}). התרכובות ממוינות לפי שיעורן בתחנה המרוכזת ביותר.</p>
            <div style="width:100%;height:420px;"><canvas id="fingerprint-canvas"></canvas></div>
        </div>
    </div>

    <!-- ════════════════════════ PCA SCATTER ════════════════════════ -->
    <div class="section">
        <h2>4. PCA — פיזור לפי שונות מירבית</h2>
        <div class="method-box-compact" style="flex-direction:column;align-items:stretch;">
            <div class="method-text" style="margin-bottom:8px;">
                <b>Principal Component Analysis (PCA)</b> — מקרין את וקטור ההרכב הכימי (%) של כל תחנה למישור דו-ממדי, כך שהצירים מייצגים את כיווני השונות הגדולים ביותר בנתונים.
            </div>
            <div style="display:flex;gap:24px;flex-wrap:wrap;">
                <div class="method-text" style="flex:1;min-width:180px;">
                    <span style="color:#27ae60;font-weight:600;">&#10003; יתרונות:</span> חושף מגמות וקבוצות על-בסיס ההרכב הכימי המלא; מזהה תרכובות שמניעות את ההפרדה בין קבוצות; מותאם לזיהוי פרקציונציה (Chromatographic Shift).
                </div>
                <div class="method-text" style="flex:1;min-width:180px;">
                    <span style="color:#c0392b;font-weight:600;">&#10007; חסרונות:</span> ממקסם שונות ולא דמיון — תחנות עם חותמת כימית דומה אך יחסי-תרכובות מעט שונים עלולות להיראות רחוקות; רגיש לנוכחות תרכובת דומיננטית אחת שמושכת ציר שלם.
                </div>
            </div>
        </div>
        <p class="section-desc">נקודות קרובות = חותמת כימית דומה <b>לפי כיווני שונות</b>. גודל הנקודה פרופורציונלי לריכוז הכולל. תחנות ללא ריכוזים (&lt; LOD) אינן מוצגות.</p>
        <div style="width:100%;height:500px;"><canvas id="pca-canvas"></canvas></div>
    </div>

    <!-- ════════════════════════ MDS SCATTER ════════════════════════ -->
    <div class="section">
        <h2>5. MDS — פיזור לפי דמיון כימי (Cosine Distance)</h2>
        <div class="method-box-compact" style="flex-direction:column;align-items:stretch;">
            <div class="method-text" style="margin-bottom:8px;">
                <b>Multidimensional Scaling (MDS)</b> — ממפה את מטריצת Cosine Distance למישור דו-ממדי כך שהמרחק בין נקודות על הגרף משקף ככל הניתן את ה<b>דמיון הכימי</b> בפועל. תחנות שדומות ב-Cosine Similarity (מעל 90%) יופיעו <b>צמודות</b>.
            </div>
            <div style="display:flex;gap:24px;flex-wrap:wrap;">
                <div class="method-text" style="flex:1;min-width:180px;">
                    <span style="color:#27ae60;font-weight:600;">&#10003; יתרונות:</span> נאמן למטריקת הדמיון הפורנזית — מרחק על הגרף = מרחק כימי אמיתי; מנטרל הבדלי ריכוז מוחלט; אידיאלי לזיהוי מקור משותף (Source Apportionment).
                </div>
                <div class="method-text" style="flex:1;min-width:180px;">
                    <span style="color:#c0392b;font-weight:600;">&#10007; חסרונות:</span> אינו חושף אילו תרכובות מניעות את ההפרדה; עלול לאבד מידע על כיווני פרקציונציה; איכות ההקרנה תלויה בערך ה-Stress (ככל שנמוך יותר, כך מדויק יותר).
                </div>
            </div>
        </div>
        <p class="section-desc">נקודות קרובות = <b>דמיון כימי גבוה</b> (Cosine Similarity). גודל הנקודה פרופורציונלי לריכוז הכולל. תחנות ללא ריכוזים (&lt; LOD) אינן מוצגות.</p>
        <div style="width:100%;height:500px;"><canvas id="mds-canvas"></canvas></div>
    </div>

    <!-- ════════════════════════ HEATMAP ════════════════════════ -->
    <div class="section">
        <h2>6. מטריצת Cosine Similarity — השוואת חותמות כימיות</h2>
        <p class="section-desc">התחנות ממוינות לפי Hierarchical Clustering. צבע ירוק = דמיון גבוה, אדום = דמיון נמוך.</p>
        <div class="method-box-compact">
            <div class="method-text"><b>Cosine Similarity</b> — השוואת פרופילים כימיים כווקטורים, תוך נטרול השפעת גודל הריכוזים.
            ערך הקרוב ל-100% מצביע על חותמת כימית זהה ומאפשר לאמת קיומו של נתיב זרימה (Pathway).</div>
            <div class="formula-inline">cos(&theta;) = <span class="frac">
                <span class="num">&Sigma;(A<sub>i</sub>&times;B<sub>i</sub>)</span>
                <span class="den">&radic;&Sigma;A<sub>i</sub>&sup2; &times; &radic;&Sigma;B<sub>i</sub>&sup2;</span>
            </span></div>
        </div>
        <div class="table-wrap" id="heatmap-container"></div>
    </div>

    <!-- ════════════════════════ PFOS/PFHxS RATIO ════════════════════════ -->
    <div class="section">
        <h2>7. מדד פורנזי: יחס PFOS/PFHxS</h2>
        <p class="section-desc">יחס מקובל בספרות הפורנזית (Charbonnet et al. 2021; Zenobio et al. 2026) להערכת קרבה למקור זיהום ומידת ה-Transport. ב-AFFF מקורי (3M ECF) היחס ~8; ירידה ביחס משקפת ספיחה סלקטיבית של PFOS לאורך מסלול הזרימה. יחסים פורנזיים נוספים (כגון &Sigma;PFCAs/&Sigma;PFSAs, יחס Branched/Linear, ונוכחות 6:2 FTS) מומלצים כקווי ראיה משלימים.</p>
        <div class="table-wrap" id="ratio-container"></div>
    </div>

    <!-- ════════════════════════ FINDINGS ════════════════════════ -->
    <div class="section">
        <div class="findings">
            <h3>סיכום ממצאים:</h3>
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
let attenuationChart = null, fingerprintChart = null;

// ── Helpers ──
function getSourceColor(s) {{ return SOURCE_COLORS[s] || DEFAULT_COLOR; }}
function getCompoundColor(c) {{ return COMPOUND_COLORS[c] || DEFAULT_COLOR; }}

// Heatmap color: red (0%) -> yellow (50%) -> green (100%)
function heatmapColor(val) {{
    if (val <= 50) {{
        const t = val / 50;
        const r = 220; const g = Math.round(60 + t * 160); const b = Math.round(60 * (1 - t));
        return 'rgb(' + r + ',' + g + ',' + b + ')';
    }} else {{
        const t = (val - 50) / 50;
        const r = Math.round(220 - t * 185); const g = Math.round(220 - t * 35); const b = Math.round(t * 80);
        return 'rgb(' + r + ',' + g + ',' + b + ')';
    }}
}}

// Graduated marker radius (log scale)
function markerRadius(total) {{
    if (total <= 0) return 5;
    const r = 5 + Math.log10(total + 1) * 6;
    return Math.min(Math.max(r, 5), 28);
}}

// ── Filter panel ──
function buildFilterPanel() {{
    const sourceTypes = [...new Set(DATA.stations.map(s => s.source_type))];
    const srcDiv = document.getElementById('source-filters');
    sourceTypes.forEach(st => {{
        const btn = document.createElement('button');
        btn.textContent = st;
        btn.style.borderRight = '4px solid ' + getSourceColor(st);
        btn.onclick = () => toggleSourceType(st);
        srcDiv.appendChild(btn);
    }});
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
    stationsOfType.forEach(n => {{ if (allSelected) selectedStations.delete(n); else selectedStations.add(n); }});
    updateUI();
}}
function selectAll() {{ DATA.stations.forEach(s => selectedStations.add(s.name)); updateUI(); }}
function selectNone() {{ selectedStations.clear(); updateUI(); }}
function updateFilterCount() {{
    document.getElementById('filter-count').textContent =
        selectedStations.size + ' מתוך ' + DATA.stations.length + ' תחנות נבחרו';
}}
function updateChipStyles() {{
    document.querySelectorAll('.station-chip').forEach(chip => {{
        chip.classList.toggle('selected', selectedStations.has(chip.dataset.station));
    }});
}}

// ── Map (graduated markers) ──
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
        html += '<div style="margin-top:8px;border-top:1px solid #ddd;padding-top:6px"><b style="font-size:11px">גודל = &Sigma;' + GROUP_NAME + '</b></div>';
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
        const r = markerRadius(s.max_total);
        const m = L.circleMarker([s.lat, s.lon], {{
            radius: r, fillColor: getSourceColor(s.source_type), color: '#fff',
            weight: 2, opacity: 1, fillOpacity: 0.85
        }}).addTo(map).bindPopup(
            '<b>' + s.name + '</b><br>סוג: ' + s.source_type +
            '<br>&Sigma;' + GROUP_NAME + ': ' + (s.max_total > 0 ? s.max_total.toFixed(2) : '< LOD') + ' ' + GROUP_UNIT +
            '<br>תאריך נבחר: ' + (s.selected_date || '-') +
            '<br>תרכובות: ' + s.n_compounds
        );
        markers.push(m);

        // Permanent label: station name + total concentration
        const concLabel = s.max_total > 0 ? (s.max_total >= 1 ? s.max_total.toFixed(1) : s.max_total.toFixed(3)) : '< LOD';
        const label = L.marker([s.lat, s.lon], {{
            icon: L.divIcon({{
                className: 'map-label',
                html: '<span>' + s.name + '<br><b>' + concLabel + '</b></span>',
                iconSize: [120, 30],
                iconAnchor: [-r - 2, 15]
            }})
        }}).addTo(map);
        markers.push(label);
    }});
    if (markers.length > 0) {{
        const group = L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.15));
    }}
}}

// ── Attenuation chart (Chart.js) ──
function updateAttenuationChart() {{
    const filtered = DATA.attenuation.filter(a => selectedStations.has(a.name));
    const ctx = document.getElementById('attenuation-canvas').getContext('2d');
    if (attenuationChart) attenuationChart.destroy();
    attenuationChart = new Chart(ctx, {{
        type: 'bar',
        data: {{
            labels: filtered.map(a => a.name),
            datasets: [{{ data: filtered.map(a => a.total), backgroundColor: filtered.map(a => getSourceColor(a.source_type)), borderWidth: 0 }}]
        }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            plugins: {{
                legend: {{ display: false }},
                tooltip: {{ callbacks: {{ label: function(ctx) {{ return '\\u03A3' + GROUP_NAME + ': ' + ctx.parsed.y.toFixed(2) + ' ' + GROUP_UNIT; }} }} }}
            }},
            scales: {{
                y: {{ type: 'logarithmic', title: {{ display: true, text: '\\u03A3' + GROUP_NAME + ' (' + GROUP_UNIT + ')', font: {{ size: 13 }} }}, grid: {{ color: '#e0e0e0' }} }},
                x: {{ ticks: {{ maxRotation: 55, minRotation: 35, font: {{ size: 12, weight: 'bold' }} }} }}
            }}
        }}
    }});
}}

// ── Fingerprint chart with total labels on top ──
function updateFingerprintChart() {{
    const fp = DATA.fingerprint;
    const selIdx = [];
    fp.stations.forEach((s, i) => {{ if (selectedStations.has(s)) selIdx.push(i); }});
    const ctx = document.getElementById('fingerprint-canvas').getContext('2d');
    if (fingerprintChart) fingerprintChart.destroy();

    const datasets = fp.compounds.map((compound, ci) => ({{
        label: compound,
        data: selIdx.map(i => fp.values[i][ci]),
        backgroundColor: getCompoundColor(compound),
        borderWidth: 0
    }}));

    // Total concentration labels plugin
    const totalLabelsPlugin = {{
        id: 'totalLabels',
        afterDraw(chart) {{
            const ctx2 = chart.ctx;
            const meta = chart.getDatasetMeta(chart.data.datasets.length - 1);
            ctx2.save();
            ctx2.font = 'bold 10px sans-serif';
            ctx2.textAlign = 'center';
            ctx2.fillStyle = '#333';
            selIdx.forEach((si, barIdx) => {{
                const total = fp.totals[si];
                if (total > 0 && meta.data[barIdx]) {{
                    const bar = meta.data[barIdx];
                    const label = total >= 1 ? total.toFixed(1) : total.toFixed(3);
                    ctx2.fillText(label, bar.x, bar.y - 6);
                }} else if (meta.data[barIdx]) {{
                    const bar = meta.data[barIdx];
                    ctx2.fillStyle = '#999';
                    ctx2.fillText('< LOD', bar.x, chart.chartArea.top + chart.chartArea.height / 2);
                    ctx2.fillStyle = '#333';
                }}
            }});
            ctx2.restore();
        }}
    }};

    fingerprintChart = new Chart(ctx, {{
        type: 'bar',
        data: {{ labels: selIdx.map(i => fp.stations[i]), datasets: datasets }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            layout: {{ padding: {{ top: 20 }} }},
            plugins: {{
                legend: {{ position: 'right', labels: {{ font: {{ size: 10 }}, boxWidth: 12 }} }},
                tooltip: {{ callbacks: {{ label: function(ctx) {{ return ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(1) + '%'; }} }} }}
            }},
            scales: {{
                x: {{ stacked: true, ticks: {{ maxRotation: 55, minRotation: 35, font: {{ size: 12, weight: 'bold' }} }} }},
                y: {{ stacked: true, max: 100, title: {{ display: true, text: 'הרכב יחסי (%)', font: {{ size: 13 }} }}, grid: {{ color: '#e0e0e0' }} }}
            }}
        }},
        plugins: [totalLabelsPlugin]
    }});
}}

// ── PCA scatter plot ──
let pcaChart = null;
function updatePcaChart() {{
    const pca = DATA.pca;
    if (!pca || pca.stations.length < 2) {{
        document.getElementById('pca-canvas').parentElement.innerHTML = '<p style="color:#999;text-align:center;padding:40px">אין מספיק תחנות עם ריכוזים לניתוח PCA</p>';
        return;
    }}
    const ctx = document.getElementById('pca-canvas').getContext('2d');
    if (pcaChart) pcaChart.destroy();

    // Build datasets grouped by source_type
    const stationInfo = {{}};
    DATA.stations.forEach(s => {{ stationInfo[s.name] = s; }});
    const sourceGroups = {{}};
    pca.stations.forEach((stn, i) => {{
        if (!selectedStations.has(stn)) return;
        const info = stationInfo[stn];
        const st = info ? info.source_type : 'אחר';
        if (!sourceGroups[st]) sourceGroups[st] = [];
        sourceGroups[st].push({{ x: pca.pc1[i], y: pca.pc2[i], name: stn, total: info ? info.max_total : 0 }});
    }});

    const datasets = Object.entries(sourceGroups).map(([st, pts]) => ({{
        label: st,
        data: pts.map(p => ({{ x: p.x, y: p.y }})),
        backgroundColor: getSourceColor(st),
        borderColor: '#fff',
        borderWidth: 1.5,
        pointRadius: pts.map(p => Math.max(5, Math.min(20, 5 + Math.log10(p.total + 1) * 5))),
        pointHoverRadius: pts.map(p => Math.max(7, Math.min(22, 7 + Math.log10(p.total + 1) * 5))),
        _stationNames: pts.map(p => p.name),
        _totals: pts.map(p => p.total)
    }}));

    pcaChart = new Chart(ctx, {{
        type: 'scatter',
        data: {{ datasets: datasets }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            plugins: {{
                legend: {{ position: 'top', labels: {{ font: {{ size: 12 }}, boxWidth: 14 }} }},
                tooltip: {{
                    callbacks: {{
                        label: function(ctx) {{
                            const ds = ctx.dataset;
                            const name = ds._stationNames[ctx.dataIndex];
                            const total = ds._totals[ctx.dataIndex];
                            return name + ' (' + (total >= 1 ? total.toFixed(1) : total.toFixed(3)) + ' ' + GROUP_UNIT + ')';
                        }}
                    }}
                }}
            }},
            scales: {{
                x: {{ title: {{ display: true, text: 'PC1 (' + pca.var_explained[0] + '% שונות)', font: {{ size: 13 }} }}, grid: {{ color: '#eee' }} }},
                y: {{ title: {{ display: true, text: 'PC2 (' + pca.var_explained[1] + '% שונות)', font: {{ size: 13 }} }}, grid: {{ color: '#eee' }} }}
            }}
        }},
        plugins: [{{
            // Draw station name labels on each point
            id: 'pcaLabels',
            afterDraw(chart) {{
                const ctx2 = chart.ctx;
                ctx2.save();
                ctx2.font = '11px sans-serif';
                ctx2.fillStyle = '#333';
                ctx2.textAlign = 'right';
                chart.data.datasets.forEach((ds, di) => {{
                    const meta = chart.getDatasetMeta(di);
                    meta.data.forEach((pt, pi) => {{
                        const name = ds._stationNames[pi];
                        // Short name (last part after " - ")
                        const shortName = name.length > 20 ? name.split(' - ').pop() || name.slice(0, 18) + '...' : name;
                        ctx2.fillText(shortName, pt.x - 8, pt.y - 8);
                    }});
                }});
                ctx2.restore();
            }}
        }}]
    }});
}}

// ── MDS scatter plot ──
let mdsChart = null;
function updateMdsChart() {{
    const mds = DATA.mds;
    if (!mds || mds.stations.length < 2) {{
        document.getElementById('mds-canvas').parentElement.innerHTML = '<p style="color:#999;text-align:center;padding:40px">אין מספיק תחנות עם ריכוזים לניתוח MDS</p>';
        return;
    }}
    const ctx = document.getElementById('mds-canvas').getContext('2d');
    if (mdsChart) mdsChart.destroy();

    const stationInfo = {{}};
    DATA.stations.forEach(s => {{ stationInfo[s.name] = s; }});
    const sourceGroups = {{}};
    mds.stations.forEach((stn, i) => {{
        if (!selectedStations.has(stn)) return;
        const info = stationInfo[stn];
        const st = info ? info.source_type : 'אחר';
        if (!sourceGroups[st]) sourceGroups[st] = [];
        sourceGroups[st].push({{ x: mds.x[i], y: mds.y[i], name: stn, total: info ? info.max_total : 0 }});
    }});

    const datasets = Object.entries(sourceGroups).map(([st, pts]) => ({{
        label: st,
        data: pts.map(p => ({{ x: p.x, y: p.y }})),
        backgroundColor: getSourceColor(st),
        borderColor: '#fff',
        borderWidth: 1.5,
        pointRadius: pts.map(p => Math.max(5, Math.min(20, 5 + Math.log10(p.total + 1) * 5))),
        pointHoverRadius: pts.map(p => Math.max(7, Math.min(22, 7 + Math.log10(p.total + 1) * 5))),
        _stationNames: pts.map(p => p.name),
        _totals: pts.map(p => p.total)
    }}));

    mdsChart = new Chart(ctx, {{
        type: 'scatter',
        data: {{ datasets: datasets }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            plugins: {{
                legend: {{ position: 'top', labels: {{ font: {{ size: 12 }}, boxWidth: 14 }} }},
                tooltip: {{
                    callbacks: {{
                        label: function(ctx) {{
                            const ds = ctx.dataset;
                            const name = ds._stationNames[ctx.dataIndex];
                            const total = ds._totals[ctx.dataIndex];
                            return name + ' (' + (total >= 1 ? total.toFixed(1) : total.toFixed(3)) + ' ' + GROUP_UNIT + ')';
                        }}
                    }}
                }}
            }},
            scales: {{
                x: {{ title: {{ display: true, text: 'MDS ציר 1', font: {{ size: 13 }} }}, grid: {{ color: '#eee' }} }},
                y: {{ title: {{ display: true, text: 'MDS ציר 2', font: {{ size: 13 }} }}, grid: {{ color: '#eee' }} }}
            }}
        }},
        plugins: [{{
            id: 'mdsLabels',
            afterDraw(chart) {{
                const ctx2 = chart.ctx;
                ctx2.save();
                ctx2.font = '11px sans-serif';
                ctx2.fillStyle = '#333';
                ctx2.textAlign = 'right';
                chart.data.datasets.forEach((ds, di) => {{
                    const meta = chart.getDatasetMeta(di);
                    meta.data.forEach((pt, pi) => {{
                        const name = ds._stationNames[pi];
                        const shortName = name.length > 20 ? name.split(' - ').pop() || name.slice(0, 18) + '...' : name;
                        ctx2.fillText(shortName, pt.x - 8, pt.y - 8);
                    }});
                }});
                ctx2.restore();
            }}
        }}]
    }});
}}

// ── PFOS/PFHxS ratio table ──
function renderRatioTable() {{
    const ratios = DATA.pfos_pfhxs_ratios;
    if (!ratios || Object.keys(ratios).length === 0) {{
        document.getElementById('ratio-container').innerHTML = '<p style="color:#999;text-align:center">אין נתונים זמינים</p>';
        return;
    }}
    const entries = Object.entries(ratios).filter(([s, v]) => v !== null && selectedStations.has(s)).sort((a, b) => b[1] - a[1]);
    if (entries.length === 0) {{
        document.getElementById('ratio-container').innerHTML = '<p style="color:#999;text-align:center">בחר תחנות עם ריכוזי PFOS ו-PFHxS</p>';
        return;
    }}
    let html = '<table class="ratio-table"><thead><tr><th>תחנה</th><th>PFOS/PFHxS</th><th>פרשנות</th></tr></thead><tbody>';
    entries.forEach(([stn, ratio]) => {{
        let interp = '';
        if (ratio >= 5) interp = '<span style="color:#c0392b;font-weight:600">קרוב למקור</span>';
        else if (ratio >= 2) interp = '<span style="color:#e67e22;font-weight:600">אזור מעבר</span>';
        else interp = '<span style="color:#27ae60;font-weight:600">מרוחק / Transport</span>';
        html += '<tr><td style="text-align:right;font-weight:600">' + stn + '</td><td><b>' + ratio.toFixed(2) + '</b></td><td>' + interp + '</td></tr>';
    }});
    html += '</tbody></table>';
    document.getElementById('ratio-container').innerHTML = html;
}}

// ── Heatmap (red-yellow-green, clustered) ──
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
            if (i === j) {{ bg = '#555'; tc = '#fff'; }}
            else {{ bg = heatmapColor(val); tc = (val >= 40 && val <= 75) ? '#333' : '#fff'; }}
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
    updatePcaChart();
    updateMdsChart();
    renderRatioTable();
    updateHeatmap();
}}

// ── Init ──
document.addEventListener('DOMContentLoaded', function() {{
    buildFilterPanel();
    initMap();
    updateAttenuationChart();
    updateFingerprintChart();
    updatePcaChart();
    updateMdsChart();
    renderRatioTable();
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
