# Next Steps

## GeoForensics Dashboard (geo-forensics/)

### מוכן לשימוש
```bash
cd geo-forensics
pip install -r requirements.txt
streamlit run app.py
```

### שלבים הבאים
1. **בדיקה ויזואלית** — טעינת כל קבצי הדוגמה ואימות שכל הסעיפים מרונדרים נכון
2. **ייצוא** — הוספת כפתור ייצוא דוח HTML סטטי מתוך הדשבורד
3. **סדרות זמן** — הוספת גרף trend לתחנות נבחרות (time series)
4. **סינון לפי תאריך** — date range picker בסרגל הצד

---

## Industrial Areas Report (Industrial-Areas-Report/)

### הרצה מהירה
```bash
cd Industrial-Areas-Report
pip install -r requirements.txt
python demo/raanana_demo.py
```

### שלבים הבאים
1. **חיבור API אמיתי** — data.gov.il (CKAN API) לנתוני רשות המים
2. **scraper ל-PRTR** — החלפת placeholder ב-scraper אמיתי למפל"ס
3. **אזורים נוספים** — הרחבה מרעננה לאזורי תעשייה אחרים
4. **דוחות PDF** — הוספת ייצוא PDF חתום לדוחות רגולטוריים

---

## מדריך קבצים

| לשם מה? | קובץ |
|----------|-------|
| הבנת המערכת | `SUMMARY.md`, `CLAUDE.md` |
| שימוש בדשבורד | `geo-forensics/REQUIREMENTS.md` |
| שימוש בדוחות | `Industrial-Areas-Report/QUICKSTART.md` |
| הרחבת plugins | `Industrial-Areas-Report/IMPLEMENTATION.md` |
| בדיקות | `cd geo-forensics && pytest` |
