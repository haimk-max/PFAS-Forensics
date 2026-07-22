# HANDOVER.md — זיכרון בין-סשן

קובץ זה מתוחזק על-ידי הסקיל `/handover`. מתעדכן **רק** כשסשן מייצר משהו שהסשן הבא צריך לדעת — אילוץ, footgun, החלטה מגבילה. לא פעולות שגרתיות.

---

## סשן 2026-07-22 — איחוד פרויקט + Claude Design

### החלטות מחייבות

1. **`Industrial-Areas-Report/` נמחק מהריפו** (החלטת משתמש, סשן זה).
   עותק מיושן היה; מקור האמת בריפו `haimk-max/industrial-areas-report`. README/NEXT_STEPS/CLAUDE/SUMMARY נוקו מכל הפניה אליו.

2. **יעד פריסה: Streamlit Cloud** — הפלטפורמה הרשמית לאפליקציית PFAS. טרם בוצע; הצעד הבא הפרקטי.

3. **החלטה פתוחה: app.py vs app_v2.py** — שתי גרסאות דשבורד פועלות:
   - `app.py` — גרסה מקורית, יציבה, נבדקה
   - `app_v2.py` — גרסה עם עיצוב Clinical (Claude Design), לשוניות st.tabs(), KPI strip, insight cards
   המשתמש טרם בחר גרסה קנונית. לפתוח ב-PROCESS.md לפני שינויים נוספים בדשבורד.

### מה נבנה בסשן זה

- **app_v2.py** (1491 שורות): דשבורד Streamlit עם עיצוב Clinical מ-Claude Design.
- **generate_report_v2.py** (844 שורות): מחולל HTML v2 עם Compare Drawer (השוואת זוג תחנות).
- **report_hagit_v2.html / report_kishon_v2.html**: דוחות דוגמה שנוצרו ומוטמעים בריפו.

### לקחים טכניים

- `st.html()` — DOMPurify מסיר `<link>` tags → פונטים חייבים דרך `@import` בתוך `<style>` ב-`st.markdown`.
- Plotly heatmap RTL: `reversescale=True` + `autosize=False` + `height` מפורש.
- MDS FutureWarning: להוסיף `init='random'` ל-`MDS()` בגרסה הבאה.

---

## סשן 2026-07-20 — אונבורדינג לכללים המעודכנים

- הפרויקט חובר לתשתית הממשל חוצת-הפרויקטים: CLAUDE.md נכתב מחדש (זהות אחת — GeoForensics PFAS; עקרונות מ-`CLAUDE.base@9801386`; ממשל קלט חיצוני; אובייקטיביות; תזכורת toolkit), הותקנו סקיל `/handover` + hook תחילת-סשן, נוצרו HANDOVER.md + PROCESS.md.
- **`Industrial-Areas-Report/` = עותק מיושן** (הכרעת המשתמש) — לא לפתח בו; מקור האמת בריפו `industrial-areas-report`. סעיפי הארכיטקטורה שלו (plugin-first, protocols) הוסרו מ-CLAUDE.md — זמינים בהיסטוריית git אם יידרשו.
- דוחות ה-HTML הקיימים (חגית/קישון) קדמו לתקני RTL/print של ה-toolkit — יישור ייעשה רק כשעובדים עליהם בפועל (לא רטרואקטיבית).

**הצעד הבא הסביר**: לפי `NEXT_STEPS.md` — בדיקה ויזואלית של הדשבורד, ייצוא HTML מהדשבורד, סדרות-זמן, סינון תאריכים. לא אושר עדיין כדרישה — לפתוח ב-PROCESS.md לפני עבודה.
