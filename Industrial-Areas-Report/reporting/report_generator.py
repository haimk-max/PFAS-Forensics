"""
Report Generator
Creates comprehensive reports on industrial area water quality and pollution sources
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json


class ReportGenerator:
    """Generate reports for industrial areas"""

    def __init__(self, output_dir: Path = None):
        """
        Initialize report generator

        Args:
            output_dir: Directory for output reports
        """
        self.output_dir = output_dir or Path("reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_area_report(
        self,
        area_name: str,
        water_quality_summary: Dict,
        contaminated_boreholes: List[Dict],
        pollution_sources: List[Dict],
        wastewater_monitoring: Optional[Dict] = None,
        output_format: str = "html"
    ) -> str:
        """
        Generate comprehensive report for industrial area

        Args:
            area_name: Industrial area name
            water_quality_summary: Summary of water quality analysis
            contaminated_boreholes: List of contaminated boreholes
            pollution_sources: List of identified pollution sources
            wastewater_monitoring: Optional wastewater monitoring data
            output_format: Output format (html, json, or both)

        Returns:
            Path to generated report
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Report_{area_name}_{timestamp}"

        if output_format in ["html", "both"]:
            html_path = self._generate_html_report(
                area_name, water_quality_summary, contaminated_boreholes,
                pollution_sources, wastewater_monitoring, filename
            )
        else:
            html_path = None

        if output_format in ["json", "both"]:
            json_path = self._generate_json_report(
                area_name, water_quality_summary, contaminated_boreholes,
                pollution_sources, wastewater_monitoring, filename
            )
        else:
            json_path = None

        return html_path or json_path

    def _generate_html_report(
        self,
        area_name: str,
        water_quality_summary: Dict,
        contaminated_boreholes: List[Dict],
        pollution_sources: List[Dict],
        wastewater_monitoring: Optional[Dict],
        filename: str
    ) -> str:
        """Generate HTML report"""
        html_file = self.output_dir / f"{filename}.html"

        html_content = f"""
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>דו"ח איכות מי תהום - {area_name}</title>
    <style>
        body {{
            font-family: 'Arial', sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1, h2, h3 {{
            color: #1a5490;
            border-bottom: 2px solid #1a5490;
            padding-bottom: 10px;
        }}
        .section {{
            margin: 30px 0;
        }}
        .status {{
            padding: 15px;
            border-radius: 4px;
            margin: 10px 0;
        }}
        .status.concern {{
            background-color: #fee;
            border-left: 4px solid #c33;
        }}
        .status.ok {{
            background-color: #efe;
            border-left: 4px solid #3c3;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: right;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #e8f1f8;
            font-weight: bold;
        }}
        .risk-high {{
            color: #c00;
            font-weight: bold;
        }}
        .risk-medium {{
            color: #f80;
            font-weight: bold;
        }}
        .risk-low {{
            color: #080;
            font-weight: bold;
        }}
        .footer {{
            margin-top: 40px;
            font-size: 12px;
            color: #666;
            border-top: 1px solid #ccc;
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>דו"ח איכות מי תהום - אזור תעשייה {area_name}</h1>

        <div class="section">
            <h2>סיכום ביצועים</h2>
            <div class="status {water_quality_summary.get('status', 'unknown').lower()}">
                <strong>סטטוס כללי:</strong> {water_quality_summary.get('status', 'לא ידוע')}
            </div>

            <h3>סטטיסטיקות בסיסיות</h3>
            <table>
                <tr>
                    <th>פרט</th>
                    <th>ערך</th>
                </tr>
                <tr>
                    <td>מספר קידוחי ניטור</td>
                    <td>{water_quality_summary.get('total_boreholes', 'N/A')}</td>
                </tr>
                <tr>
                    <td>פרמטרים מנוטרים</td>
                    <td>{water_quality_summary.get('parameters_monitored', 'N/A')}</td>
                </tr>
                <tr>
                    <td>סך דוגמים</td>
                    <td>{water_quality_summary.get('total_samples', 'N/A')}</td>
                </tr>
                <tr>
                    <td>קידוחים מזוהמים</td>
                    <td>{water_quality_summary.get('boreholes_with_contamination', 0)}</td>
                </tr>
            </table>
        </div>

        {self._generate_contamination_section(contaminated_boreholes)}
        {self._generate_sources_section(pollution_sources)}
        {self._generate_wastewater_section(wastewater_monitoring)}

        <div class="footer">
            <p>דו"ח זה נוצר אוטומטית על ידי מערכת ניתוח איכות מי תהום</p>
            <p>תאריך: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>
"""

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return str(html_file)

    def _generate_json_report(
        self,
        area_name: str,
        water_quality_summary: Dict,
        contaminated_boreholes: List[Dict],
        pollution_sources: List[Dict],
        wastewater_monitoring: Optional[Dict],
        filename: str
    ) -> str:
        """Generate JSON report"""
        json_file = self.output_dir / f"{filename}.json"

        report_data = {
            "metadata": {
                "area": area_name,
                "generated_date": datetime.now().isoformat(),
                "version": "1.0"
            },
            "water_quality_summary": water_quality_summary,
            "contaminated_boreholes": contaminated_boreholes,
            "pollution_sources": pollution_sources,
            "wastewater_monitoring": wastewater_monitoring or {}
        }

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        return str(json_file)

    @staticmethod
    def _generate_contamination_section(contaminated_boreholes: List[Dict]) -> str:
        """Generate contamination section"""
        if not contaminated_boreholes:
            return """
            <div class="section">
                <h2>זיהום קרקע</h2>
                <div class="status ok">
                    <strong>מצב:</strong> לא אותרו זיהומים משמעותיים בקידוחי הניטור
                </div>
            </div>
            """

        rows = ""
        for bh in contaminated_boreholes[:10]:
            rows += f"""
            <tr>
                <td>{bh.get('borehole_id', 'N/A')}</td>
                <td>{bh.get('parameter', 'N/A')}</td>
                <td>{bh.get('measured_value', 'N/A')} / {bh.get('standard_value', 'N/A')}</td>
                <td><span class="risk-{bh.get('severity', 'low')}">{bh.get('hebrew_severity', 'לא ידוע')}</span></td>
            </tr>
            """

        return f"""
        <div class="section">
            <h2>קידוחים מזוהמים</h2>
            <table>
                <tr>
                    <th>קידוח</th>
                    <th>פרמטר</th>
                    <th>ריכוז / תקן</th>
                    <th>חומרה</th>
                </tr>
                {rows}
            </table>
        </div>
        """

    @staticmethod
    def _generate_sources_section(pollution_sources: List[Dict]) -> str:
        """Generate pollution sources section"""
        if not pollution_sources:
            return "<div class='section'><h2>מקורות זיהום</h2><p>לא אותרו מקורות זיהום פוטנציאליים</p></div>"

        rows = ""
        for source in pollution_sources[:5]:
            rows += f"""
            <tr>
                <td>{source.get('facility_name', 'N/A')}</td>
                <td>{source.get('industry_type', 'N/A')}</td>
                <td><span class="risk-{source.get('overall_risk', 'low').lower()}">{source.get('overall_risk', 'Unknown')}</span></td>
            </tr>
            """

        return f"""
        <div class="section">
            <h2>מקורות זיהום פוטנציאליים</h2>
            <table>
                <tr>
                    <th>מתקן</th>
                    <th>סוג תעשייה</th>
                    <th>רמת סיכון</th>
                </tr>
                {rows}
            </table>
        </div>
        """

    @staticmethod
    def _generate_wastewater_section(wastewater_monitoring: Optional[Dict]) -> str:
        """Generate wastewater monitoring section"""
        if not wastewater_monitoring:
            return ""

        return f"""
        <div class="section">
            <h2>ניטור שפכי תעשייה</h2>
            <p>שיעור ציות: {wastewater_monitoring.get('average_compliance_rate', 'N/A')}%</p>
            <p>מפעלים מנוטרים: {wastewater_monitoring.get('total_factories', 'N/A')}</p>
        </div>
        """
