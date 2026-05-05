# Groundwater Contamination Monitoring & GeoForensics

מערכת לניטור זיהום מי תהום באזורי תעשייה בישראל וחקירה גיאו-פורנזית של מזהמים.

## מבנה הפרויקט

```
my-first-project/
├── geo-forensics/           ← דשבורד אינטראקטיבי לניתוח PFAS (Streamlit)
│   ├── app.py               ← אפליקציית Streamlit
│   ├── generate_report.py   ← מחולל דוחות HTML סטטיים
│   ├── config.py            ← הגדרות: צבעים, מפה, UI
│   ├── src/                 ← מודולי אנליטיקה ועיבוד נתונים
│   ├── tests/               ← בדיקות pytest
│   ├── data/sample/         ← קבצי נתונים לדוגמה
│   └── REQUIREMENTS.md      ← מפרט דרישות הדשבורד
│
├── Industrial-Areas-Report/ ← מערכת דוחות תקופתיים (ארכיטקטורת Plugins)
│   ├── core/                ← חוזים, interfaces, pipeline
│   ├── plugins/             ← forensics, trend detection, attribution
│   ├── data_sources/        ← Water Authority API, Excel, PRTR
│   ├── reporting/           ← מחולל דוחות HTML/JSON
│   ├── demo/                ← הדגמה — אזור תעשייה רעננה
│   └── README.md            ← תיעוד מלא
│
├── CLAUDE.md                ← הנחיות עבודה ותיעוד טכני
└── SUMMARY.md               ← סיכום יכולות המערכת
```

## התחלה מהירה

### GeoForensics — דשבורד PFAS
```bash
cd geo-forensics
pip install -r requirements.txt
streamlit run app.py
```

### דוח HTML סטטי
```bash
cd geo-forensics
python generate_report.py "data/sample/דוגמה - חגית PFAS.xlsx" -o report.html
```

### Industrial Areas Report — מערכת דוחות תקופתיים
```bash
cd Industrial-Areas-Report
pip install -r requirements.txt
python demo/raanana_demo.py
```

## טכנולוגיות

| רכיב | טכנולוגיה |
|-------|-----------|
| דשבורד | Streamlit, streamlit-folium, Plotly |
| מפות | Folium / Leaflet.js |
| אנליטיקה | scikit-learn, scipy, numpy, pandas |
| דוחות | Jinja2, Plotly.js, Bootstrap RTL |
| קואורדינטות | pyproj (ITM ↔ WGS84) |
