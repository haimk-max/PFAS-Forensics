"""Wrap report-section HTML fragments in a complete HTML5 page."""

from __future__ import annotations

from datetime import datetime


_LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
_LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
_PLOTLY_JS = "https://cdn.plot.ly/plotly-2.27.0.min.js"

_PAGE_CSS = """
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: 'Segoe UI', 'Heebo', Arial, sans-serif;
  background: #f5f7fa;
  color: #1f2933;
  line-height: 1.5;
}
header.report-header {
  background: linear-gradient(135deg, #1a3a5c 0%, #2c5282 100%);
  color: #fff;
  padding: 28px 32px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
header.report-header h1 {
  margin: 0 0 6px 0;
  font-size: 28px;
  font-weight: 600;
}
header.report-header .meta {
  font-size: 14px;
  opacity: 0.9;
}
main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 16px 48px 16px;
}
.card {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  padding: 24px 28px;
  margin: 18px 0;
}
.card h2 {
  margin-top: 0;
  color: #1a3a5c;
  border-bottom: 2px solid #e2e8f0;
  padding-bottom: 10px;
  font-size: 22px;
}
.card h3 {
  color: #2c5282;
  font-size: 17px;
  margin-top: 20px;
}
table.summary {
  width: 100%;
  border-collapse: collapse;
  margin-top: 12px;
  font-size: 14px;
}
table.summary th, table.summary td {
  padding: 10px 12px;
  text-align: right;
  border-bottom: 1px solid #e2e8f0;
}
table.summary th {
  background: #edf2f7;
  font-weight: 600;
  color: #2d3748;
}
.idx-badge {
  display: inline-block;
  min-width: 28px;
  padding: 3px 10px;
  border-radius: 12px;
  color: #fff;
  font-weight: 600;
  text-align: center;
  font-size: 13px;
}
.idx-0, .idx-1, .idx-2 { background: #28a745; }
.idx-3, .idx-4 { background: #ffc107; color: #333; }
.idx-5, .idx-6 { background: #fd7e14; }
.idx-7, .idx-8 { background: #dc3545; }
.tier-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  background: #e2e8f0;
  color: #2d3748;
  font-weight: 600;
  font-size: 12px;
}
.chart-controls {
  margin: 14px 0 8px 0;
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.chart-controls label {
  font-weight: 600;
  color: #4a5568;
}
.chart-controls select {
  padding: 6px 10px;
  border: 1px solid #cbd5e0;
  border-radius: 6px;
  background: #fff;
  font-size: 14px;
  font-family: inherit;
}
.plot-area {
  width: 100%;
  height: 420px;
  margin-top: 4px;
}
.map-area {
  width: 100%;
  height: 520px;
  border-radius: 8px;
  position: relative;
}
.map-legend {
  position: absolute;
  bottom: 16px;
  left: 16px;
  background: rgba(255,255,255,0.95);
  padding: 10px 14px;
  border-radius: 6px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.2);
  font-size: 12px;
  z-index: 1000;
}
.map-legend .swatch {
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  margin-left: 6px;
  vertical-align: middle;
}
.note {
  font-size: 12px;
  color: #718096;
  margin-top: 8px;
  font-style: italic;
}
footer.report-footer {
  text-align: center;
  color: #718096;
  font-size: 12px;
  padding: 18px;
}
"""


def assemble_report(
    section_html: str,
    area_name: str,
    area_hebrew: str,
    year: int,
) -> str:
    """Wrap rendered ReportSection HTML in a complete HTML5 page.

    The section_html is the concatenated output of all ReportSection
    plugins (as returned by ``Pipeline.render_report``). It is inserted
    inside ``<main>`` with each section already responsible for its own
    ``<section class="card">`` wrapper.
    """
    generated = datetime.now().strftime("%d.%m.%Y %H:%M")
    title = f'דו"ח ניטור מי תהום — אזור תעשייה {area_hebrew} ({year})'

    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="stylesheet" href="{_LEAFLET_CSS}">
<script src="{_LEAFLET_JS}"></script>
<script src="{_PLOTLY_JS}"></script>
<style>{_PAGE_CSS}</style>
</head>
<body>
<header class="report-header">
  <h1>{title}</h1>
  <div class="meta">דו"ח שנתי לרשות המים והגנת הסביבה · גרסה רזה (v1) · נוצר {generated}</div>
</header>
<main>
{section_html}
</main>
<footer class="report-footer">
  מערכת ניטור אוטומטית לאזורי תעשייה · {area_name} · {year}
</footer>
</body>
</html>
"""
