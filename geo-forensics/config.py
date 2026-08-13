"""config.py - הגדרות כלליות של האפליקציה."""

import os

# --- App Info ---
APP_NAME = "GeoForensics"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = "כלי לחקירת מקורות זיהום במים, קרקע ושפכים"

# --- Map Defaults ---
# מרכז ישראל (בערך - אזור רמלה)
DEFAULT_MAP_CENTER = [31.93, 34.87]  # lat, lon
DEFAULT_MAP_ZOOM = 8

# Tile layers - שכבות רקע למפה (נטענות מהאינטרנט, רק תמונות)
MAP_TILES = {
    "מפה רגילה": {
        "tiles": "OpenStreetMap",
        "attr": "OpenStreetMap",
    },
    "לוויין": {
        "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attr": "Esri World Imagery",
    },
}

# --- Coordinate System ---
# Israel Transverse Mercator (ITM) - EPSG:2039
ITM_EPSG = 2039
WGS84_EPSG = 4326

# ITM validity range (to catch bad data)
ITM_X_RANGE = (100_000, 300_000)   # Easting
ITM_Y_RANGE = (350_000, 800_000)   # Northing

# --- Data Directory ---
DATA_DIR = os.environ.get("GEOFORENSICS_DATA_DIR", "data/sample")

# --- Evidence thresholds (calibratable) ---
# Stations with total concentration below this are near-LOD noise: their
# normalized fingerprint is dominated by measurement noise and LOD zeros, so
# they must not count as chemical-consistency evidence in attribution.
MIN_SIGNAL_UG_L = 0.01

# Relative plume half-width growth per unit travel distance (sigma = k*L) for
# the graded groundwater-plausibility tiers. Declared calibration parameter
# (claim A6, approved 2026-07-27): mid-range of field transverse
# dispersivities; will be calibrated against measured heads (S3).
GW_PLUME_K = 0.2

# --- Chemical-cluster reliability (approved 2026-08-12, PROCESS #22) ---
# A station may carry a CLUSTER COLOR (map + matrix strips) only if its
# fingerprint is reliable enough to classify: at low totals, single
# near-LOD compounds swing the relative composition by tens of percent, and
# hard clustering then paints noise with confident colors. Stations below
# this Sigma stay "signal too weak to classify" (gray). Declared,
# calibratable (kishon claim KI-A4).
CLUSTER_MIN_SIGNAL_UG_L = 0.05
# A colored cluster needs at least this many reliable members — smaller
# groups are indistinguishable from chance pairings at these noise levels.
CLUSTER_MIN_MEMBERS = 3

# --- Well classification (approved 2026-08-12) ---
# Water Authority naming convention: monitoring wells are point sensors;
# production wells integrate an ill-defined pumping capture zone. Names win;
# an explicit source_type is the fallback for unprefixed names.
WELL_MONITORING_PREFIXES = ("נד", "נת", "מח")
WELL_PRODUCTION_PREFIXES = ("פ", "מק")
# Coarse declared capture radius for the "pumping-blurred" tier range —
# placeholder until heads/discharge data (user deferred pumping rates).
PRODUCTION_CAPTURE_RADIUS_M = 500.0

# --- Junction-load test thresholds (approved 2026-08-11) ---
# Segment anomalies along a flow stem that indicate load joining between
# consecutive stations. Declared, calibratable.
JUNCTION_RISE_FACTOR = 2.0      # local Sigma rise: next/prev ratio above this
JUNCTION_SIM_REBOUND_PP = 15.0  # similarity-to-head rebound (percent points)
JUNCTION_MARKER_JUMP_PP = 5.0   # stable-marker (PFOA/PFOS) share jump (pp)
JUNCTION_PREC_REBOUND_PP = 5.0  # precursor-share return after depletion (pp)
JUNCTION_PREC_DEPLETED_PP = 2.0 # "depleted" precursor level (pp)

# --- Data Defaults ---
MAX_UPLOAD_SIZE_MB = 50
SUPPORTED_EXTENSIONS = [".xlsx", ".xls", ".csv"]
DEFAULT_ENCODING = "utf-8"
FALLBACK_ENCODING = "cp1255"  # Hebrew Windows encoding

# --- UI ---
SIDEBAR_WIDTH = 350
PAGE_ICON = "🔬"

# --- Color Palettes ---
PFAS_S_COMPOUNDS = [
    "PFOS", "PFBS", "PFHxS", "6:2FT", "PFPeS", "PFHpS",
    "PFDS", "PFTDS", "82FTS", "FOSA",
]
PFAS_A_COMPOUNDS = [
    "PFOA", "PFHxA", "PFHpA", "PFNA", "PFDA", "PFDoA",
    "PFBA", "PFPeA", "PFESA", "ADONA", "PFTDA", "PFUnA",
    "PFUnDA", "GenX",
]
PFAS_COMPOUND_ORDER = PFAS_S_COMPOUNDS + PFAS_A_COMPOUNDS

COMPOUND_COLORS = {
    # S group — Blue palette (dark → light)
    "PFOS": "#0D47A1", "PFBS": "#1565C0", "PFHxS": "#1976D2",
    "6:2FT": "#42A5F5", "PFPeS": "#90CAF9", "PFHpS": "#BBDEFB",
    "PFDS": "#1E88E5", "PFTDS": "#5C9CE6",
    "82FTS": "#64B5F6", "FOSA": "#2E5FA3",
    # A group — Orange/warm palette (dark → light)
    "PFOA": "#BF360C", "PFHxA": "#D84315", "PFHpA": "#E64A19",
    "PFNA": "#F4511E", "PFDA": "#FF7043", "PFDoA": "#FF8A65",
    "PFBA": "#FFAB76", "PFPeA": "#FFA726", "PFESA": "#FFB74D",
    "ADONA": "#FFCC80", "PFTDA": "#FFE0B2", "PFUnA": "#FFF3E0",
    "PFUnDA": "#FFE8CC", "GenX": "#FFD6A5",
}

SOURCE_COLORS = {
    "קידוח ניטור": "#3498db", "קידוח הפקה": "#2ecc71",
    "קידוח": "#2980b9", 'מט"ש': "#e74c3c", "מעיין": "#9b59b6",
    "מים עיליים": "#f39c12", "נקודה מזוהה בנחל": "#e67e22",
    "תחנה הידרומטרית": "#1abc9c", "מאגר": "#8e44ad",
}

DEFAULT_COLOR = "#95a5a6"
