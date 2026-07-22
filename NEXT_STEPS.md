# Next Steps — GeoForensics PFAS

## הרצה מהירה
```bash
cd geo-forensics
pip install -r requirements.txt
streamlit run app.py
```

## שלבים הבאים

1. **פריסה ב-Streamlit Cloud** — העלאת הריפו + הגדרת `requirements.txt` + `data/` path
2. **בדיקה ויזואלית** — הרצת `app.py` על כל קבצי הדוגמה ואימות שכל הלשוניות מרונדרות נכון
3. **ייצוא מהדשבורד** — כפתור להורדת דוח HTML v2 ישירות מ-Streamlit
4. **סדרות זמן** — גרף trend לתחנות נבחרות (time series) כשיש ריבוי דגימות
5. **סינון לפי תאריך** — date range picker בסרגל הצד
6. **איחוד מחוללי הדוחות** — לשקול הפיכת `generate_report_v2.py` לקנוני (כפי שנעשה לדשבורד)

> **הוכרע (2026-07-22):** `app.py` הקנוני = עיצוב Clinical (לשעבר app_v2). הגרסה המקורית שמורה כ-`app_legacy.py`.

## מדריך קבצים

| לשם מה? | קובץ |
|----------|-------|
| הבנת המערכת | `SUMMARY.md`, `CLAUDE.md` |
| מפרט הדשבורד | `geo-forensics/REQUIREMENTS.md` |
| בדיקות | `cd geo-forensics && pytest` |
