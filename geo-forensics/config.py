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

# --- Data Defaults ---
MAX_UPLOAD_SIZE_MB = 50
SUPPORTED_EXTENSIONS = [".xlsx", ".xls", ".csv"]
DEFAULT_ENCODING = "utf-8"
FALLBACK_ENCODING = "cp1255"  # Hebrew Windows encoding

# --- UI ---
SIDEBAR_WIDTH = 350
PAGE_ICON = "🔬"

# --- Color Palettes ---
PFAS_S_COMPOUNDS = ["PFOS", "PFBS", "PFHxS", "6:2FT", "PFPeS", "PFHpS"]
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
