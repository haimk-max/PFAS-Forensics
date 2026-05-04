"""Raanana lean v1 demo — produces an interactive HTML dashboard.

Generates multi-year synthetic-but-realistic data for 6 actual Raanana wells,
runs the lean plugin pipeline (grouping + 0-8 index + tier source attribution,
NO rigorous trends, NO chemical fingerprints), and writes a self-contained
interactive HTML report with Leaflet map + 3 Plotly charts.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DRINKING_WATER_STANDARDS  # noqa: E402
from core.contracts import ReportContext  # noqa: E402
from core.pipeline import Pipeline  # noqa: E402
from reporting.html_assembler import assemble_report  # noqa: E402


# ---------------------------------------------------------------------------
# Lean v1 pipeline configuration — skips trends + forensics
# ---------------------------------------------------------------------------
LEAN_CONFIG: Dict = {
    "data_sources": [],
    "forensics": ["__skip__"],          # sentinel: no plugin matches → all skipped
    "trend_detectors": ["__skip__"],    # same
    "source_attributors": ["tier_based"],
    "report_sections": [
        "area_overview",
        "borehole_card",
        "regulatory_checklist",
    ],
}


# ---------------------------------------------------------------------------
# Boreholes (real Raanana well names with WGS84 coordinates)
# ---------------------------------------------------------------------------
BOREHOLES: List[Dict] = [
    {"id": "nat_raanana_1",   "name_hebrew": "נת רעננה 1",          "lat": 32.1950, "lon": 34.8690},
    {"id": "nat_raanana_3",   "name_hebrew": "נת רעננה 3",          "lat": 32.1970, "lon": 34.8710},
    {"id": "nd_paz_hanofar",  "name_hebrew": "נד פז הנופר",        "lat": 32.1930, "lon": 34.8650},
    {"id": "nd_turbines",     "name_hebrew": "נד תחנת טורבינות גז", "lat": 32.1910, "lon": 34.8680},
    {"id": "p_raanana_25",    "name_hebrew": "פ רעננה 25",          "lat": 32.1980, "lon": 34.8720},
    {"id": "p_raanana_18",    "name_hebrew": "פ רעננה 18",          "lat": 32.1960, "lon": 34.8740},
]


# Per-well synthetic profile: parameter -> (start_value_2022, annual_growth_factor)
# Growth factor 1.0 = stable, >1 rising, <1 declining.
WELL_PROFILES: Dict[str, Dict[str, tuple]] = {
    # Chlorinated solvents focus, very high index
    "nat_raanana_1": {
        "TCE":         (200.0, 1.10),
        "PCE":         (45.0,  1.05),
        "cis-1,2-DCE": (12.0,  1.15),
        "Chlorides":   (380.0, 1.02),
    },
    # Chlorinated, moderate
    "nat_raanana_3": {
        "TCE":         (35.0,  1.08),
        "PCE":         (18.0,  1.03),
        "Chlorides":   (290.0, 1.01),
    },
    # Fuel-pathway well
    "nd_paz_hanofar": {
        "Benzene":  (4.5,  1.20),
        "Toluene":  (220.0, 1.10),
        "MTBE":     (110.0, 1.18),
        "Xylene":   (90.0,  1.05),
    },
    # PFAS pathway well
    "nd_turbines": {
        "PFOA":        (0.18, 1.15),
        "PFOS":        (0.32, 1.12),
        "PFAS_Total":  (0.95, 1.10),
    },
    # Production well, low TCE
    "p_raanana_25": {
        "TCE":       (1.8,   1.05),
        "Chlorides": (180.0, 1.01),
        "Nitrates":  (28.0,  1.00),
    },
    # Production well, chloride-dominated
    "p_raanana_18": {
        "Chlorides": (260.0, 1.04),
        "Nitrates":  (35.0,  1.02),
        "Sulfate":   (140.0, 1.01),
    },
}


# Quarterly sampling (Jan/Apr/Jul/Oct), 2022-2024
SAMPLE_DATES = [
    ("2022-01-15", 0, 0), ("2022-04-15", 0, 1), ("2022-07-15", 0, 2), ("2022-10-15", 0, 3),
    ("2023-01-15", 1, 0), ("2023-04-15", 1, 1), ("2023-07-15", 1, 2), ("2023-10-15", 1, 3),
    ("2024-01-15", 2, 0), ("2024-04-15", 2, 1), ("2024-07-15", 2, 2), ("2024-10-15", 2, 3),
]


def _unit_for(param: str) -> str:
    if param in {"Chlorides", "Nitrates", "Sulfate"}:
        return "mg/L"
    return "μg/L"


def build_sample_data() -> pd.DataFrame:
    """Build the multi-year, multi-well, multi-parameter sample DataFrame."""
    rows: List[Dict] = []
    for well_id, profile in WELL_PROFILES.items():
        for param, (start, growth) in profile.items():
            for date_str, year_idx, q_idx in SAMPLE_DATES:
                # Compound annual growth + small quarterly seasonal jitter
                yearly = start * (growth ** year_idx)
                seasonal = 1.0 + 0.05 * ((q_idx - 1.5))   # -0.075..+0.075
                val = round(yearly * seasonal, 4)
                rows.append({
                    "date": date_str,
                    "borehole_id": well_id,
                    "industrial_area": "raanana",
                    "parameter": param,
                    "value": val,
                    "unit": _unit_for(param),
                })
    return pd.DataFrame(rows)


def candidate_facilities() -> List[Dict]:
    """Sample candidate facilities for source attribution."""
    return [
        {
            "facility_id": "F001",
            "name": "מפעל אלקטרוניקה רעננה",
            "industry_type": "electronics",
            "reported_emissions": {"TCE": 12.0, "PCE": 4.5},
            "evidence": {"lat": 32.1955, "lon": 34.8700},
        },
        {
            "facility_id": "F002",
            "name": "מתקן ציפוי מתכת בא.ת.",
            "industry_type": "metal_coating",
            "reported_emissions": {"Chromium": 1.2, "Nickel": 0.8},
            "evidence": {"lat": 32.1940, "lon": 34.8720},
        },
        {
            "facility_id": "F003",
            "name": "תחנת דלק פז הנופר",
            "industry_type": "gas_station",
            "reported_emissions": {"Benzene": 0.3, "MTBE": 1.1, "Toluene": 0.6},
            "evidence": {"lat": 32.1925, "lon": 34.8655},
        },
        {
            "facility_id": "F004",
            "name": "תחנת טורבינות גז",
            "industry_type": "power_station",
            "reported_emissions": {"PFOS": 0.05, "PFOA": 0.03},
            "evidence": {"lat": 32.1908, "lon": 34.8682},
        },
        {
            "facility_id": "F005",
            "name": "מוסך מרכזי רעננה",
            "industry_type": "auto_repair",
            "reported_emissions": {"Toluene": 0.1},
            "evidence": {"lat": 32.1948, "lon": 34.8732},
        },
    ]


def main() -> Path:
    print("=" * 72)
    print("Raanana Industrial Area — Lean v1 Interactive Dashboard")
    print("=" * 72)

    print("\n[1/5] Building sample data (6 wells × 3 years × 4 quarters) ...")
    data = build_sample_data()
    print(f"      ✓ {len(data)} measurements across "
          f"{data['borehole_id'].nunique()} wells / "
          f"{data['parameter'].nunique()} parameters")

    print("\n[2/5] Initializing lean plugin pipeline ...")
    pipeline = Pipeline(LEAN_CONFIG, DRINKING_WATER_STANDARDS)

    print("\n[3/5] Analyzing contaminant families (grouping + 0-8 index) ...")
    family_reports = pipeline.analyze_families(data)
    for fr in family_reports:
        print(f"      · {fr.family:25s} index={fr.max_index} "
              f"dominant={fr.dominant_contaminant} "
              f"wells={len(fr.wells_affected)}")

    print("\n[4/5] Running source attribution (tier-based, 5 candidates) ...")
    candidates = candidate_facilities()
    attributions = pipeline.attribute_sources(
        family_reports, candidates, flow_direction_deg=270
    )
    for a in attributions:
        print(f"      · {a.facility_name:35s} "
              f"score={a.score:.2f} → {a.cautious_phrase} (דרג {a.tier})")

    print("\n[5/5] Rendering interactive HTML dashboard ...")
    ctx = ReportContext(
        area_name="raanana",
        area_hebrew="רעננה",
        year=2024,
        family_reports=family_reports,
        attributions=attributions,
        flow_direction_deg=270,
        boreholes=BOREHOLES,
        map_center=(32.1945, 34.8695),
        previous_context={"raw_data": data.to_dict(orient="records")},
    )
    section_html = pipeline.render_report(ctx)
    full_html = assemble_report(section_html, "raanana", "רעננה", 2024)

    out_dir = Path(__file__).parent.parent / "reports" / "raanana" / "2024"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "report_raanana_2024.html"
    out_path.write_text(full_html, encoding="utf-8")

    print(f"\n      ✓ Report saved: {out_path}")
    print(f"      ✓ Size: {out_path.stat().st_size:,} bytes")
    print("\n" + "=" * 72)
    print("פתח את הקובץ בדפדפן כדי לצפות במפה האינטראקטיבית, גרפי הזמן,")
    print("וגרף העמודות המוערם להשוואת ההרכב הכימי בין הקידוחים.")
    print("=" * 72)
    return out_path


if __name__ == "__main__":
    main()
