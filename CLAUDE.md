# CLAUDE.md — Industrial Areas Groundwater Monitoring System

## Project Purpose

Automated platform for analyzing groundwater contamination in Israeli industrial areas
and generating periodic regulatory reports for the Water Authority and Ministry of
Environmental Protection. Raanana industrial zone is the pilot case study.

### GeoForensics PFAS Module

פלטפורמה לניתוח גיאו-פורנזי של מזהמי PFAS במים, קרקע ושפכים.
הפרויקט מייצר דוחות HTML אינטראקטיביים מקבצי Excel, הכוללים ניתוחים סטטיסטיים, מפות, וגרפים.

---
1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them - don't pick silently.
If a simpler approach exists, say so. Push back when warranted.
If something is unclear, stop. Name what's confusing. Ask.
2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

No features beyond what was asked.
No abstractions for single-use code.
No "flexibility" or "configurability" that wasn't requested.
No error handling for impossible scenarios.
If you write 200 lines and it could be 50, rewrite it.
Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

3. Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:

Don't "improve" adjacent code, comments, or formatting.
Don't refactor things that aren't broken.
Match existing style, even if you'd do it differently.
If you notice unrelated dead code, mention it - don't delete it.
When your changes create orphans:

Remove imports/variables/functions that YOUR changes made unused.
Don't remove pre-existing dead code unless asked.
The test: Every changed line should trace directly to the user's request.

4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

"Add validation" → "Write tests for invalid inputs, then make them pass"
"Fix the bug" → "Write a test that reproduces it, then make it pass"
"Refactor X" → "Ensure tests pass before and after"
For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

## Architecture Principles

### Plugin-First Design

The system is built on an **Open-Closed** principle: the core orchestration layer is
closed to modification, while every analysis capability is a plugin that can be added,
replaced, or disabled without touching core code.

```
core/            ← stable contracts + orchestration (rarely changes)
plugins/         ← all capabilities as drop-in packages (grows freely)
knowledge/       ← cumulative context store (approved reports feed next year)
areas/           ← GeoJSON polygons per industrial area
config.py        ← pipeline activation per area (data, not code)
```

**Rule:** adding a new analysis module (e.g., PFAS forensics, LSTM trend detector)
= create a new folder under `plugins/`, implement the relevant Protocol from
`core/interfaces.py`, decorate with `@register_plugin`. Zero changes to core.

### Six Extension Points (core/interfaces.py)

| Protocol | Where | Purpose |
|---|---|---|
| `DataSource` | `plugins/data_sources/` | Fetch raw measurements |
| `ContaminantFamilyAnalyzer` | `plugins/forensics/` | Per-family group analysis |
| `ForensicsModule` | `plugins/forensics/` | Chemical fingerprinting per well |
| `TrendDetector` | `plugins/trend_detection/` | Detect trend types in time series |
| `SourceAttributor` | `plugins/source_attribution/` | Rank pollution candidates |
| `ReportSection` | `plugins/report_sections/` | Render one HTML section |

### Typed Data Contracts (core/contracts.py)

All inter-module data flows through typed dataclasses — never raw `dict`.
Key types: `BoreholeReading`, `FamilyReport`, `FingerprintResult`,
`TrendResult`, `Attribution`, `ReportContext`.

---

## GeoForensics PFAS — מבנה הפרויקט
```
my-first-project/
├── CLAUDE.md                 # קובץ זה
├── PLAN.md                   # תכנון מקורי
├── geo-forensics/
│   ├── generate_report.py    # סקריפט ראשי - יצירת דוחות HTML סטטיים
│   ├── app.py                # אפליקציית Streamlit (דשבורד אינטראקטיבי)
│   ├── config.py             # הגדרות: מפה, קואורדינטות, UI
│   ├── requirements.txt      # תלויות Python
│   ├── src/
│   │   ├── analytics.py      # Cosine similarity, ממצאים
│   │   ├── data_model.py     # עיבוד נתונים, fingerprint, ריכוזים
│   │   ├── data_loader.py    # טעינת קבצי Excel
│   │   ├── geo_utils.py      # המרת קואורדינטות ITM ↔ WGS84
│   │   ├── contaminant_groups.py  # הגדרות קבוצות מזהמים
│   │   └── generate_sample_data.py
│   ├── data/sample/          # קבצי נתונים לדוגמה
│   │   ├── דוגמה - חגית PFAS.xlsx
│   │   ├── נתוני קישון.xlsx
│   │   ├── העברת ידע למשרד הבריאות 28.9.25 - מלא.xlsx  # קובץ גדול (1.8MB)
│   │   └── sample_pfas.xlsx
│   ├── report_hagit.html     # דוח שנוצר עבור חגית
│   ├── report_kishon.html    # דוח שנוצר עבור קישון
│   ├── tests/                # בדיקות pytest
│   ├── maps/                 # קבצי מפות
│   ├── assets/               # נכסים סטטיים
│   └── ui/                   # רכיבי ממשק
```

## פקודות הרצה

### יצירת דוח HTML (מצב נוכחי)
```bash
cd geo-forensics && python generate_report.py "data/sample/דוגמה - חגית PFAS.xlsx" -o report_hagit.html
cd geo-forensics && python generate_report.py "data/sample/נתוני קישון.xlsx" -o report_kishon.html
```
**חשוב:** תמיד להריץ מתוך תיקיית `geo-forensics/` — הסקריפט משתמש בנתיבים יחסיים.

### התקנת תלויות
```bash
pip install -r geo-forensics/requirements.txt
```

### בדיקות
```bash
cd geo-forensics && pytest
```

## ניתוחים סטטיסטיים בדוח
| ניתוח | תיאור | ספרייה |
|-------|--------|--------|
| PCA | הפחתת ממדים, זיהוי אשכולות | scikit-learn |
| MDS | Multidimensional Scaling על מרחק קוסינוס | scikit-learn |
| Cosine Similarity | מטריצת דמיון בין תחנות | scipy |
| Hierarchical Clustering | קיבוץ היררכי של תחנות | scipy |
| ΣPFAS Concentration | ריכוז כולל בציר לוגריתמי | pandas/numpy |

## טכנולוגיות
- **Python**: pandas, scikit-learn, scipy, numpy, openpyxl, pyproj
- **HTML Reports**: Plotly.js (גרפים), Bootstrap RTL (עיצוב), Leaflet.js (מפות)
- **Dashboard**: Streamlit, streamlit-folium
- **קואורדינטות**: pyproj — המרה ITM (EPSG:2039) ↔ WGS84 (EPSG:4326)

## כללי עבודה
- קבצי Excel בעברית — שמות עמודות ותחנות בעברית
- ה-HTML שנוצר הוא self-contained — כל הנתונים מוטמעים כ-JSON
- הדוח תומך ב-RTL (עברית)
- קבצים גדולים מאוד (>1MB) — לוודא שהניתוח לא קורס על זיכרון
- **מודל מומלץ**: Sonnet לכתיבה/עריכה של קוד; Opus לתכנון ארכיטקטורה

---

## Key Domain Concepts

- **Pollution Index 0-8**: logarithmic scale (ratio to drinking water standard).
  Index = `f(concentration / standard)`. Group index = `max(member indices)`.
- **7 Contaminant Families**: chlorinated solvents, fuels, metals, inorganic/salinity,
  PFAS, emerging, sewage markers.
- **7 Trend Types**: rising, falling, stable, volatile, pulse/event,
  re-escalation (changepoint after decline), new appearance.
- **Chemical Fingerprint**: leading contaminant + secondaries + degradation products
  + intra-group ratios. Used to distinguish separate plumes and link wells.
- **Dual-path Borehole Selection**: union of (historical report wells) ∪
  (polygon-based wells via Shapely point-in-polygon).
- **Cautious Attribution Phrasing**: legally critical in Israel. Vocabulary:
  "מועמד ליבה" / "מועמד משני" / "רקע מקומי" — never "the source".
- **Cumulative Knowledge**: each approved annual report becomes a formal context
  layer for the next year (stored under `knowledge/contexts/{area}/{year}.json`).
- **Flow Direction Caution**: flow direction alone never identifies a source —
  must combine with chemical fingerprint + spatial position + emission evidence.

---

## Adding a New Plugin (Quick Guide)

```
plugins/forensics/pfas/
├── __init__.py          # exposes PFASForensics class
├── plugin.py            # implements ForensicsModule Protocol, @register_plugin
├── contaminants.yaml    # PFAS compounds handled (PFOA, PFOS, GenX…)
├── tests/
│   └── test_plugin.py   # isolated unit tests
└── README.md            # contract: input schema, output schema, dependencies
```

```python
# plugin.py skeleton
from core.interfaces import ForensicsModule
from core.registry import register_plugin
from core.contracts import FingerprintResult

@register_plugin("forensics", name="pfas")
class PFASForensics:
    family = "pfas"
    version = "1.0"

    def fingerprint(self, well_data) -> FingerprintResult:
        ...
```

Activate for a specific area in `config.py`:
```python
PIPELINE_CONFIG["emek_hefer"]["forensics"].append("pfas")
```

---

## Running the System

```bash
cd Industrial-Areas-Report
pip install -r requirements.txt
python demo/raanana_demo.py          # full pipeline, Raanana pilot
pytest tests/ -v                     # unit + plugin isolation tests
```

Expected outputs in `reports/raanana/{year}/`:
- `report_raanana_{year}.html` — interactive RTL report with Leaflet map
- `report_raanana_{year}.pdf`  — official signed version
- `report_raanana_{year}.json` — machine-readable
- `map_raanana_{year}.html`    — standalone Leaflet map
- `context_raanana_{year}.json`— feeds next year's cumulative context

---

## Data Sources

| Source | Type | Status |
|---|---|---|
| Israel Water Authority (data.gov.il) | CKAN API | Working connector |
| PRTR / מפל"ס registry | Web / GIS | Placeholder → real scraper needed |
| Mei Raanana wastewater monitoring | Web reports | Placeholder → real scraper needed |
| Water Authority Excel consolidation | Excel | Working importer |
| Historical reports 2008 + 2021 | JSON loaders | Planned |

---

## Coordinate System

All spatial operations use **Israel New Grid ITM (EPSG:2039)**  internally.
Conversion to WGS84 (EPSG:4326) for Leaflet maps via `pyproj` in
`plugins/data_sources/coordinate_engine/`.

---

## Testing Guidelines

- Each plugin must have isolated unit tests that do **not** import core pipeline.
- Plugin contract tests in `tests/test_plugin_isolation.py` verify:
  - New plugin registers correctly via `discover_plugins()`
  - Pipeline runs with plugin disabled without error
  - Data contracts (FingerprintResult etc.) validate correctly
- Domain logic tests in `tests/test_analysis.py`.

---

## חזון עתידי — דשבורד מקומי אינטראקטיבי

### מטרה
דשבורד שרץ מקומית (localhost) ומציג את **קובץ נתוני איכות המים המלא של הרשות** באופן אינטראקטיבי.

### דרישות עיקריות

#### 1. טעינת נתונים
- טעינת קובץ Excel מלא של נתוני איכות מים (רשות המים / משרד הבריאות)
- תמיכה בקבצים גדולים (מעל 1MB) עם טעינה מהירה
- ניקוי אוטומטי של נתונים חסרים/שגויים
- זיהוי אוטומטי של עמודות רלוונטיות (תחנה, תאריך, תוצאות, קואורדינטות)

#### 2. בחירת אזור ונקודות דיגום — סרגלי בחירה (Dropdowns / Filters)
- **בחירת אזור גיאוגרפי**: dropdown לבחירת אזור (צפון, מרכז, דרום, או לפי אגנים)
- **בחירת נקודות דיגום**: multi-select עם חיפוש לבחירת תחנות ספציפיות
- **סינון לפי תאריך**: טווח תאריכים (date range picker)
- **סינון לפי מזהם**: בחירת תרכובות PFAS ספציפיות
- כל שינוי בסינון מעדכן את כל התצוגות (מפה + גרפים + טבלאות)

#### 3. בחירה על גבי מפה (Map-based Selection)
- מפה אינטראקטיבית (Leaflet / Folium) עם כל נקודות הדיגום
- **לחיצה על נקודה** — בחירה/ביטול בחירה של תחנה בודדת
- **ציור מלבן/פוליגון** על המפה לבחירת קבוצת תחנות (Leaflet.draw)
- **סנכרון דו-כיווני**: בחירה על המפה מעדכנת את הסרגלים, ולהיפך
- צביעה לפי ריכוז / אשכול / סטטוס
- popup עם מידע מהיר על כל תחנה

#### 4. תצוגות ודוחות
- כל הניתוחים הקיימים (PCA, MDS, Cosine Similarity, Clustering)
- טבלת נתונים אינטראקטיבית עם מיון וסינון
- גרפי זמן (time series) לתחנות נבחרות
- ייצוא דוח HTML סטטי מתוך הדשבורד
- ייצוא נתונים ל-CSV

#### 5. ארכיטקטורה טכנית
- **Backend**: Python (Flask או FastAPI) — שרת מקומי
- **Frontend**: HTML/JS עם Plotly.js + Leaflet.js, או Streamlit כאלטרנטיבה מהירה
- **נתונים**: pandas DataFrame בזיכרון; אופציונלי SQLite לקבצים גדולים מאוד
- **הרצה**: `python app.py` → נפתח בדפדפן ב-`http://localhost:8501`

#### 6. UX
- ממשק בעברית (RTL)
- עיצוב רספונסיבי
- טעינה מהירה — lazy loading לנתונים כבדים
- שמירת מצב סינון ב-URL (query params) לשיתוף
