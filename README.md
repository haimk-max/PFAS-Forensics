# GeoForensics PFAS Dashboard

פלטפורמה לניתוח גיאו-פורנזי של מזהמי PFAS במים תהומיים ועיליים — עבור השירות ההידרולוגי, רשות המים.

## מבנה הפרויקט

```
my-first-project/
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

## טכנולוגיות

| רכיב | טכנולוגיה |
|-------|-----------|
| דשבורד | Streamlit, streamlit-folium, Plotly |
| מפות | Folium / Leaflet.js |
| אנליטיקה | scikit-learn (PCA, MDS), scipy (clustering), numpy, pandas |
| דוחות HTML | Plotly.js, Bootstrap RTL, Leaflet.js |
| קואורדינטות | pyproj — ITM (EPSG:2039) ↔ WGS84 (EPSG:4326) |
