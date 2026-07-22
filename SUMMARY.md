# GeoForensics PFAS — סיכום יכולות המערכת

## מטרת הפרויקט

פלטפורמה לניתוח גיאו-פורנזי של מזהמי PFAS במים תהומיים ועיליים, עבור השירות ההידרולוגי, רשות המים.
הכלי עוזר לזהות מקורות זיהום, להשוות פרופילים כימיים בין תחנות, ולהפיק דוחות להחלטות רגולטוריות.

---

## מה המערכת יודעת לעשות

### 1. טעינת נתונים מ-Excel
- קריאת קבצי `xlsx` עם עמודות: תחנה, מקור, קואורדינטות ITM, תרכובת, ריכוז
- זיהוי אוטומטי של קבוצת מזהמים (PFAS, BTEX, ממסים כלוריים, מתכות, חנקות)
- המרת קואורדינטות ITM → WGS84 (pyproj)
- תמיכה בעברית בשמות עמודות ותחנות

### 2. ניתוחים סטטיסטיים
| ניתוח | תפקיד |
|-------|--------|
| **Chemical Fingerprint** | פרופיל אחוזי תרכובות לכל תחנה — הבסיס להשוואה |
| **Cosine Similarity** | מטריצת דמיון בין תחנות (0–100%), מזהה plumes משותפים |
| **PCA** | הפחתת ממדים — מציג "מרחק" בין תחנות בשתי צירים |
| **MDS** | Multidimensional Scaling על מרחק קוסינוס — וידוא PCA |
| **Hierarchical Clustering** | קיבוץ היררכי של תחנות לפי הרכב כימי |
| **ΣPFAS Concentration** | ריכוז כולל לכל תחנה, ציר לוגריתמי |

### 3. דשבורד Streamlit אינטראקטיבי (app.py / app_v2.py)
- העלאת קובץ Excel ישירות מהדפדפן
- מפה אינטראקטיבית (Folium) עם סימוני תחנות וצבעי מקור
- לשוניות: מפה | ריכוזים | פרופיל כימי | מטריצת דמיון | PCA/MDS | ממצאים
- סיכום ממצאים אוטומטי בעברית (תחנה מקסימלית, תרכובת דומיננטית, חריגים, אשכולות)
- **app_v2.py** — גרסה עם עיצוב Clinical (פלטת צבעים נקייה, כרטיסי KPI, טיפוגרפיה משודרגת)

### 4. דוחות HTML עצמאיים (generate_report.py / generate_report_v2.py)
- קובץ HTML יחיד self-contained — אין שרת, נפתח בדפדפן
- כל הנתונים מוטמעים כ-JSON; גרפים מרונדרים client-side (Plotly.js, Leaflet.js)
- מפה אינטראקטיבית עם פופ-אפים לכל תחנה
- 5 לשוניות: מפה | ריכוזים | פרופיל | דמיון | PCA
- **generate_report_v2.py** — גרסה עם עיצוב Clinical + Compare Drawer (השוואת זוג תחנות)

---

## קבצים מרכזיים

```
geo-forensics/
├── app.py                  ← דשבורד Streamlit (גרסה מקורית)
├── app_v2.py               ← דשבורד Streamlit (עיצוב Clinical)
├── generate_report.py      ← מחולל HTML סטטי (v1)
├── generate_report_v2.py   ← מחולל HTML סטטי (v2, Clinical + Compare Drawer)
├── config.py               ← צבעים, PFAS_COMPOUND_ORDER, הגדרות מפה
├── src/
│   ├── analytics.py        ← cosine_similarity_matrix, generate_findings_summary
│   ├── data_model.py       ← build_fingerprint_matrix, calc_total_concentration
│   ├── data_loader.py      ← טעינת Excel, זיהוי עמודות
│   ├── geo_utils.py        ← המרת ITM ↔ WGS84
│   └── contaminant_groups.py ← 5 קבוצות מזהמים מוגדרות + detect_group()
├── data/sample/            ← קבצי נתונים לדוגמה (חגית, קישון)
├── report_hagit_v2.html    ← דוח דוגמה (22 תחנות, 18 תרכובות)
├── report_kishon_v2.html   ← דוח דוגמה (32 תחנות, 19 תרכובות)
└── tests/                  ← 31 בדיקות pytest (כולן עוברות)
```

---

## הרצה מהירה

### דשבורד
```bash
cd geo-forensics
pip install -r requirements.txt
streamlit run app_v2.py
```

### דוח HTML סטטי
```bash
cd geo-forensics
python generate_report_v2.py "data/sample/דוגמה - חגית PFAS.xlsx" -o report.html
```

---

## ניסוח ייחוס — עיקרון קריטי

הדוחות משתמשים בשפת "מועמד ליבה" / "מועמד משני" / "רקע מקומי" — **לעולם לא "המקור"**.
דמיון גבוה בין תחנות אינו מוכיח זהות מקור; הוא מחייב בדיקה משלימה (כיוון זרימה, ראיות פליטה, chronology).

---

## מצב (2026-07-22)

| רכיב | מצב |
|------|-----|
| דשבורד Streamlit (app.py) | ✅ פועל |
| דשבורד Clinical (app_v2.py) | ✅ פועל |
| דוחות HTML v1 | ✅ פועל |
| דוחות HTML v2 + Compare Drawer | ✅ פועל |
| בדיקות pytest | ✅ 31/31 עוברות |
| פריסה ב-Streamlit Cloud | ⏳ טרם בוצע |
| החלטה: app.py vs app_v2.py | ⏳ פתוח |
