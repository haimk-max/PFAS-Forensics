# Next Steps — GeoForensics PFAS

## הרצה מהירה
```bash
cd geo-forensics
pip install -r requirements.txt
streamlit run app_v2.py
```

## שלבים הבאים

1. **פריסה ב-Streamlit Cloud** — העלאת הריפו + הגדרת `requirements.txt` + `data/` path
2. **החלטה: app.py vs app_v2.py** — בחירת הגרסה הקנונית (ראה HANDOVER.md)
3. **בדיקה ויזואלית** — טעינת כל קבצי הדוגמה ואימות שכל הסעיפים מרונדרים נכון
4. **ייצוא מהדשבורד** — כפתור להורדת דוח HTML v2 ישירות מ-Streamlit
5. **סדרות זמן** — גרף trend לתחנות נבחרות (time series) כשיש ריבוי דגימות
6. **סינון לפי תאריך** — date range picker בסרגל הצד

## מדריך קבצים

| לשם מה? | קובץ |
|----------|-------|
| הבנת המערכת | `SUMMARY.md`, `CLAUDE.md` |
| מפרט הדשבורד | `geo-forensics/REQUIREMENTS.md` |
| בדיקות | `cd geo-forensics && pytest` |
