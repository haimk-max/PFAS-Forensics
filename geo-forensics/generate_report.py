"""
generate_report.py - יצירת דוח HTML סטטי
==========================================
מייצר קובץ HTML עצמאי שניתן לפתוח בדפדפן בלי שרת.

שימוש:
    python generate_report.py
    -> יוצר report.html בתיקייה הנוכחית
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from config import APP_NAME, APP_VERSION, PAGE_ICON
from src.data_model import (
    build_fingerprint_matrix,
    calc_total_concentration,
    get_station_summary,
    process_file,
)


def generate_html_report(output_path: str = "report.html"):
    """Generate a standalone HTML report from the sample data."""
    sample_path = os.path.join(os.path.dirname(__file__), "data", "sample", "sample_pfas.xlsx")

    if not os.path.exists(sample_path):
        print("שגיאה: קובץ הדוגמה לא נמצא. הרץ: python -m src.generate_sample_data")
        sys.exit(1)

    print("טוען ומעבד נתונים...")
    df, group = process_file(sample_path)

    # Prepare data
    summary = get_station_summary(df)
    fingerprint = build_fingerprint_matrix(df, group)
    totals = calc_total_concentration(df, group)
    totals = totals.sort_values("total_concentration", ascending=False)

    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{PAGE_ICON} {APP_NAME} - דוח</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0e1117;
    color: #fafafa;
    padding: 20px;
    direction: rtl;
  }}
  h1 {{ color: #ff4b4b; margin-bottom: 10px; }}
  h2 {{ color: #fafafa; margin: 30px 0 15px; border-bottom: 1px solid #333; padding-bottom: 8px; }}
  h3 {{ color: #ccc; margin: 20px 0 10px; }}
  .header {{ text-align: center; padding: 20px 0; }}
  .header p {{ color: #888; }}
  .metrics {{
    display: flex;
    gap: 15px;
    justify-content: center;
    flex-wrap: wrap;
    margin: 20px 0;
  }}
  .metric {{
    background: #1e1e2e;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 15px 25px;
    text-align: center;
    min-width: 150px;
  }}
  .metric .value {{ font-size: 2em; font-weight: bold; color: #ff4b4b; }}
  .metric .label {{ color: #888; margin-top: 5px; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0 20px;
    direction: ltr;
    text-align: left;
  }}
  th {{
    background: #1e1e2e;
    color: #ff4b4b;
    padding: 10px 12px;
    border: 1px solid #333;
    font-weight: 600;
    position: sticky;
    top: 0;
  }}
  td {{
    padding: 8px 12px;
    border: 1px solid #333;
  }}
  tr:nth-child(even) {{ background: #1a1a2a; }}
  tr:hover {{ background: #252540; }}
  .tabs {{
    display: flex;
    gap: 5px;
    margin: 20px 0 0;
    border-bottom: 2px solid #333;
  }}
  .tab {{
    padding: 10px 20px;
    cursor: pointer;
    background: #1e1e2e;
    border: 1px solid #333;
    border-bottom: none;
    border-radius: 8px 8px 0 0;
    color: #888;
  }}
  .tab.active {{ background: #252540; color: #ff4b4b; border-color: #ff4b4b; }}
  .tab-content {{ display: none; padding: 15px 0; }}
  .tab-content.active {{ display: block; }}
  .table-wrap {{ overflow-x: auto; }}
  .footer {{
    text-align: center;
    color: #555;
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid #333;
  }}
</style>
</head>
<body>

<div class="header">
  <h1>{PAGE_ICON} {APP_NAME}</h1>
  <p>v{APP_VERSION} | דוח סטטי - נתוני דוגמה PFAS</p>
</div>

<h2>סקירת נתונים - {group.name}</h2>

<div class="metrics">
  <div class="metric">
    <div class="value">{df["station_name"].nunique()}</div>
    <div class="label">תחנות</div>
  </div>
  <div class="metric">
    <div class="value">{df["compound"].nunique()}</div>
    <div class="label">תרכובות</div>
  </div>
  <div class="metric">
    <div class="value">{len(df)}</div>
    <div class="label">שורות נתונים</div>
  </div>
  <div class="metric">
    <div class="value">{df["source_type"].nunique()}</div>
    <div class="label">סוגי מקור</div>
  </div>
</div>

<div class="tabs">
  <div class="tab active" onclick="showTab('summary')">📊 סיכום תחנות</div>
  <div class="tab" onclick="showTab('raw')">📋 נתונים גולמיים</div>
  <div class="tab" onclick="showTab('fingerprint')">🔬 טביעת אצבע</div>
  <div class="tab" onclick="showTab('totals')">📈 סה"כ ריכוזים</div>
</div>

<div id="summary" class="tab-content active">
  <h3>סיכום לפי תחנות</h3>
  <div class="table-wrap">
    {summary.to_html(index=False, classes='data-table', border=0)}
  </div>
</div>

<div id="raw" class="tab-content">
  <h3>נתונים גולמיים</h3>
  <div class="table-wrap">
    {df.to_html(index=False, classes='data-table', border=0)}
  </div>
</div>

<div id="fingerprint" class="tab-content">
  <h3>מטריצת טביעת אצבע כימית (%)</h3>
  <div class="table-wrap">
    {fingerprint.style.format("{{:.1f}}%").to_html(classes='data-table')}
  </div>
</div>

<div id="totals" class="tab-content">
  <h3>סה"כ ריכוזים לפי תחנה</h3>
  <div class="table-wrap">
    {totals[["station_name", "source_type", "total_concentration", "sample_date"]].to_html(index=False, classes='data-table', border=0)}
  </div>
</div>

<div class="footer">
  <p>🔒 דוח זה נוצר מנתוני דוגמה סינתטיים | {APP_NAME} v{APP_VERSION}</p>
</div>

<script>
function showTab(name) {{
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById(name).classList.add('active');
  event.target.classList.add('active');
}}
</script>

</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"הדוח נוצר בהצלחה: {output_path}")
    print(f"פתח את הקובץ בדפדפן כדי לצפות בו.")


if __name__ == "__main__":
    output = os.path.join(os.path.dirname(__file__), "report.html")
    generate_html_report(output)
