"""
config.py - הגדרות כלליות של האפליקציה
======================================
כל הקבועים והברירות מחדל של המערכת מרוכזים כאן.
אם צריך לשנות משהו (למשל מיקום ברירת מחדל של המפה) - זה המקום.
"""

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

# --- Data Defaults ---
MAX_UPLOAD_SIZE_MB = 50
SUPPORTED_EXTENSIONS = [".xlsx", ".xls", ".csv"]
DEFAULT_ENCODING = "utf-8"
FALLBACK_ENCODING = "cp1255"  # Hebrew Windows encoding

# --- UI ---
SIDEBAR_WIDTH = 350
PAGE_ICON = "🔬"
