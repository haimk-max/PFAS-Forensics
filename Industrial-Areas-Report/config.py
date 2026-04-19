"""Configuration for Industrial Areas Report Generator"""

import os
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent

# Data sources
DATA_SOURCES = {
    "data_gov_il": {
        "base_url": "https://data.gov.il/api/3/action",
        "dataset_id": "borehole_quality_history",
        "description": "Israel Water Authority borehole water quality history"
    },
    "prtr": {
        "base_url": "https://www.gov.il/he/pages/prtr",
        "govmap_layer": 213244,
        "description": "Pollutant Release and Transfer Register (מפל\"ס)"
    },
    "water_authority": {
        "description": "Israel Water Authority (רשות המים)",
        "note": "Requires direct database or Excel connection"
    },
    "mei_raanana": {
        "base_url": "https://mei-raanana.co.il",
        "report_path": "/info/דוחות-ניטור-שפכי-תעשייה/",
        "description": "Mei Raanana industrial wastewater monitoring reports"
    }
}

# Monitoring parameters (פרמטרים מנוטרים)
WATER_QUALITY_PARAMETERS = {
    "VOCs": {
        "name": "Volatile Organic Compounds",
        "hebrew": "תרכובות אורגניות נדיפות",
        "examples": ["TCE", "PCE", "Benzene", "Toluene"]
    },
    "Chlorides": {
        "name": "Chlorides",
        "hebrew": "כלורידים",
        "unit": "mg/L"
    },
    "Nitrates": {
        "name": "Nitrates",
        "hebrew": "ניטרטים",
        "unit": "mg/L"
    },
    "Heavy_Metals": {
        "name": "Heavy Metals",
        "hebrew": "מתכות כבדות",
        "examples": ["Lead", "Cadmium", "Chromium"]
    },
    "Fuels": {
        "name": "Fuel Hydrocarbons",
        "hebrew": "פחמימנים דלקיים",
        "examples": ["Benzene", "Diesel", "Gasoline"]
    }
}

# Industrial areas in monitoring network
INDUSTRIAL_AREAS = {
    "raanana": {
        "hebrew": "רעננה",
        "region": "Central",
        "area_dunams": 500,
        "established_monitoring": 2007,
        "known_contaminants": ["TCE", "Chlorinated_Solvents"],
        "status": "Contamination detected - source under investigation"
    },
    # Additional areas will be added as data becomes available
}

# Contamination severity thresholds
CONTAMINATION_SEVERITY = {
    "none": {"hebrew": "לא מזוהם", "color": "green"},
    "mild": {"hebrew": "זיהום קל", "color": "yellow"},
    "moderate": {"hebrew": "זיהום בינוני", "color": "orange"},
    "severe": {"hebrew": "זיהום חמור", "color": "red"},
    "very_severe": {"hebrew": "זיהום חמור מאד", "color": "darkred"}
}

# Standards (תקנים)
DRINKING_WATER_STANDARDS = {
    "TCE": 5.0,  # μg/L (60% of 8.3 μg/L limit triggers severe alert)
    "PCE": 5.0,  # μg/L
    "Benzene": 1.0,  # μg/L
    "Chlorides": 250,  # mg/L
    "Nitrates": 50,  # mg/L
}

# Report settings
REPORTS = {
    "output_dir": PROJECT_ROOT / "reports",
    "output_formats": ["pdf", "html"],
    "include_maps": True,
    "include_trends": True,
    "include_sources": True
}

# Create output directories
for path in [REPORTS["output_dir"]]:
    path.mkdir(parents=True, exist_ok=True)
