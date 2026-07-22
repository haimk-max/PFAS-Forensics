# GeoForensics PFAS Dashboard

פלטפורמה לניתוח גיאו-פורנזי של מזהמי PFAS במים תהומיים ועיליים — עבור השירות ההידרולוגי, רשות המים.

## מבנה הפרויקט

```
PFAS-Forensics/
├── geo-forensics/           ← הליבה: דשבורד ודוחות PFAS
│   ├── app.py               ← דשבורד Streamlit — קנוני (עיצוב Clinical)
│   ├── app_legacy.py        ← דשבורד Streamlit — גרסה מקורית (גלילה רציפה)
│   ├── generate_report.py   ← מחולל דוחות HTML סטטיים (v1)
│   ├── generate_report_v2.py← מחולל דוחות HTML סטטיים (v2)
│   ├── config.py            ← הגדרות: צבעים, מפה, UI
│   ├── src/                 ← מודולי אנליטיקה ועיבוד נתונים
│   ├── tests/               ← בדיקות pytest
│   ├── data/sample/         ← קבצי נתונים לדוגמה
│   └── REQUIREMENTS.md      ← מפרט דרישות הדשבורד
│
├── CLAUDE.md                ← הנחיות עבודה ותיעוד טכני
├── SUMMARY.md               ← סיכום יכולות המערכת
├── HANDOVER.md              ← זיכרון בין-סשן
└── PROCESS.md               ← מעקב דרישות
```

## התחלה מהירה

### דשבורד אינטראקטיבי
```bash
cd geo-forensics
pip install -r requirements.txt
streamlit run app.py
```

### דוח HTML סטטי (self-contained)
```bash
cd geo-forensics
python generate_report_v2.py "data/sample/דוגמה - חגית PFAS.xlsx" -o report.html
```

### בדיקות
```bash
cd geo-forensics && pytest
```

## פריסה ל-Streamlit Community Cloud

הריפו מוכן לפריסה. ב-[share.streamlit.io](https://share.streamlit.io) → **New app**:

| שדה | ערך |
|-----|-----|
| Repository | `haimk-max/PFAS-Forensics` |
| Branch | `main` |
| Main file path | `geo-forensics/app.py` |

לחיצה על **Deploy** נותנת URL ציבורי קבוע. אין הגדרות נוספות:
- `requirements.txt` בשורש (מפנה ל-`geo-forensics/requirements.txt`) — Streamlit Cloud מזהה אותו אוטומטית.
- `.streamlit/config.toml` בשורש — ערכת הנושא (Clinical). נדרש בשורש כי Streamlit Cloud מריץ מתיקיית השורש.
- קבצי הדוגמה ב-`geo-forensics/data/sample/` כלולים בריפו; טעינתם עצמאית מתיקיית העבודה.

## טכנולוגיות

| רכיב | טכנולוגיה |
|-------|-----------|
| דשבורד | Streamlit, streamlit-folium, Plotly |
| מפות | Folium / Leaflet.js |
| אנליטיקה | scikit-learn (PCA, MDS), scipy (clustering), numpy, pandas |
| דוחות HTML | Plotly.js, Bootstrap RTL, Leaflet.js |
| קואורדינטות | pyproj — ITM (EPSG:2039) ↔ WGS84 (EPSG:4326) |
