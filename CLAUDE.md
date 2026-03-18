# CLAUDE.md — GeoForensics PFAS Project

## תיאור הפרויקט
פלטפורמה לניתוח גיאו-פורנזי של מזהמי PFAS במים, קרקע ושפכים.
הפרויקט מייצר דוחות HTML אינטראקטיביים מקבצי Excel, הכוללים ניתוחים סטטיסטיים, מפות, וגרפים.

## מבנה הפרויקט
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
