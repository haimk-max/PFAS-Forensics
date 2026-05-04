"""Configuration for Industrial Areas Report Generator — Plugin Architecture."""

import os
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent

# ---------------------------------------------------------------------------
# Data source connection info (consumed by DataSource plugins)
# ---------------------------------------------------------------------------
DATA_SOURCES = {
    "data_gov_il": {
        "base_url": "https://data.gov.il/api/3/action",
        "dataset_id": "borehole_quality_history",
        "description": "Israel Water Authority borehole water quality history",
    },
    "prtr": {
        "base_url": "https://www.gov.il/he/pages/prtr",
        "govmap_layer": 213244,
        "description": "Pollutant Release and Transfer Register (מפל\"ס)",
    },
    "water_authority": {
        "description": "Israel Water Authority (רשות המים)",
        "note": "Requires direct database or Excel connection",
    },
    "mei_raanana": {
        "base_url": "https://mei-raanana.co.il",
        "report_path": "/info/דוחות-ניטור-שפכי-תעשייה/",
        "description": "Mei Raanana industrial wastewater monitoring reports",
    },
}

# ---------------------------------------------------------------------------
# Drinking-water standards (תקנים) — used by PollutionIndex (core)
# ---------------------------------------------------------------------------
DRINKING_WATER_STANDARDS = {
    # Chlorinated solvents (μg/L)
    "TCE": 5.0,
    "PCE": 5.0,
    "cis-1,2-DCE": 70.0,
    "trans-1,2-DCE": 100.0,
    "1,1-DCE": 7.0,
    "Vinyl_Chloride": 2.0,
    "1,1,1-TCA": 200.0,
    "Chloroform": 100.0,
    "Carbon_Tetrachloride": 5.0,
    # Fuels (μg/L)
    "Benzene": 1.0,
    "Toluene": 1000.0,
    "Ethylbenzene": 700.0,
    "Xylene": 10000.0,
    "MTBE": 40.0,
    # Metals (μg/L)
    "Chromium": 50.0,
    "Lead": 10.0,
    "Cadmium": 5.0,
    "Nickel": 20.0,
    "Arsenic": 10.0,
    "Boron": 500.0,
    # Inorganic (mg/L)
    "Chlorides": 250.0,
    "Nitrates": 50.0,
    "Sulfate": 250.0,
    "Fluoride": 1.5,
    # PFAS (μg/L)
    "PFOA": 0.07,
    "PFOS": 0.07,
    "PFAS_Total": 0.5,
}

# ---------------------------------------------------------------------------
# Industrial areas
# ---------------------------------------------------------------------------
INDUSTRIAL_AREAS = {
    "raanana": {
        "hebrew": "רעננה",
        "region": "Central",
        "area_dunams": 500,
        "established_monitoring": 2007,
        "known_contaminants": ["TCE", "Chlorinated_Solvents"],
        "status": "Contamination detected - source under investigation",
        "polygon_file": "areas/raanana.geojson",
        "flow_direction_deg": 270,  # roughly west
        "baseline_report": "knowledge/baselines/raanana_2021.json",
        "map_center": (32.195, 34.869),
    },
}

# ---------------------------------------------------------------------------
# Source tiers (consumed by SourceAttributor plugins)
# ---------------------------------------------------------------------------
SOURCE_TIERS = {
    1: {
        "hebrew": "תעשייה של ממש ופסולת",
        "examples": ["chemical_industry", "waste_treatment", "formulation"],
        "weight": 1.0,
    },
    2: {
        "hebrew": "חצי-תעשייתית עם שימוש כימי מהותי",
        "examples": ["metal_coating", "electronics", "printing", "surface_treatment"],
        "weight": 0.8,
    },
    3: {
        "hebrew": "דלק, אנרגיה, תשתיות",
        "examples": ["gas_station", "power_station", "fuel_depot"],
        "weight": 0.6,
    },
    4: {
        "hebrew": "מקורות נקודתיים קטנים",
        "examples": ["auto_repair", "body_shop", "vehicle_service"],
        "weight": 0.3,
    },
    5: {
        "hebrew": "מסחר קל",
        "examples": ["retail", "warehouse", "office"],
        "weight": 0.1,
    },
}

# ---------------------------------------------------------------------------
# Cautious attribution phrases (legally critical in Israel)
# ---------------------------------------------------------------------------
ATTRIBUTION_PHRASES = {
    "core_candidate": "מועמד ליבה",
    "secondary_candidate": "מועמד משני",
    "local_background": "רקע מקומי",
    "not_supporting": "לא תומך בפלומה המרכזית",
    "separate_pathway": "מתאים למסלול נפרד",
}

# ---------------------------------------------------------------------------
# Pipeline plugin activation per area
# ---------------------------------------------------------------------------
PIPELINE_CONFIG = {
    "raanana": {
        "data_sources": ["water_authority", "excel"],
        "forensics": ["chlorinated", "fuels", "metals"],
        "trend_detectors": ["mann_kendall", "changepoint"],
        "source_attributors": ["tier_based"],
        "report_sections": ["*"],
    },
}

# ---------------------------------------------------------------------------
# Legacy compatibility — old severity scale (kept for backward compat)
# ---------------------------------------------------------------------------
CONTAMINATION_SEVERITY = {
    "none": {"hebrew": "לא מזוהם", "color": "green"},
    "mild": {"hebrew": "זיהום קל", "color": "yellow"},
    "moderate": {"hebrew": "זיהום בינוני", "color": "orange"},
    "severe": {"hebrew": "זיהום חמור", "color": "red"},
    "very_severe": {"hebrew": "זיהום חמור מאד", "color": "darkred"},
}

WATER_QUALITY_PARAMETERS = {
    "VOCs": {
        "name": "Volatile Organic Compounds",
        "hebrew": "תרכובות אורגניות נדיפות",
        "examples": ["TCE", "PCE", "Benzene", "Toluene"],
    },
    "Chlorides": {"name": "Chlorides", "hebrew": "כלורידים", "unit": "mg/L"},
    "Nitrates": {"name": "Nitrates", "hebrew": "ניטרטים", "unit": "mg/L"},
    "Heavy_Metals": {
        "name": "Heavy Metals",
        "hebrew": "מתכות כבדות",
        "examples": ["Lead", "Cadmium", "Chromium"],
    },
    "Fuels": {
        "name": "Fuel Hydrocarbons",
        "hebrew": "פחמימנים דלקיים",
        "examples": ["Benzene", "Diesel", "Gasoline"],
    },
}

# ---------------------------------------------------------------------------
# Report output settings
# ---------------------------------------------------------------------------
REPORTS = {
    "output_dir": PROJECT_ROOT / "reports",
    "output_formats": ["pdf", "html"],
    "include_maps": True,
    "include_trends": True,
    "include_sources": True,
}

# Knowledge store path
CONTEXT_STORE_PATH = PROJECT_ROOT / "knowledge" / "contexts"

# Create output directories
for _path in [REPORTS["output_dir"], CONTEXT_STORE_PATH]:
    _path.mkdir(parents=True, exist_ok=True)
