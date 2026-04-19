# Next Steps - How to Use the Industrial Areas System

## Immediate Actions (Today)

### 1. Understand What You Have
**Time: 5 minutes**

Read these files in order:
1. `SUMMARY.md` ← Overview of what was built
2. `Industrial-Areas-Report/QUICKSTART.md` ← How to use it
3. `Industrial-Areas-Report/README.md` ← Project background

### 2. See It Working
**Time: 1 minute**

```bash
cd Industrial-Areas-Report
pip install -r requirements.txt
python demo/raanana_demo.py
```

You'll see:
- Water quality analysis for Raanana
- Contamination severity assessment
- Facility risk ranking
- Generated HTML + JSON reports in `reports/` directory

### 3. Review the Code
**Time: 30 minutes**

The system is organized into logical modules:

```
data_sources/
  ├── water_authority.py      ← How to fetch from data.gov.il
  ├── prtr.py                 ← How to query PRTR registry
  ├── mei_raanana.py          ← How to integrate wastewater monitoring
  └── excel_importer.py       ← How to use Excel consolidation files

analysis/
  ├── water_quality_analyzer.py      ← Contamination assessment logic
  └── pollution_source_analyzer.py   ← Facility risk ranking logic

reporting/
  └── report_generator.py     ← HTML/JSON report generation
```

Start with `demo/raanana_demo.py` to see how modules work together.

---

## Short Term (This Week)

### Option A: Use With Your Own Data

**Step 1: Create Excel Template**
```python
from data_sources.excel_importer import ExcelDataSource
from pathlib import Path

ExcelDataSource.create_template_excel(Path("my_data.xlsx"))
```

**Step 2: Fill With Your Water Quality Data**
```
water_quality.xlsx:
  Sheet "Water_Quality":
    date | borehole_id | industrial_area | parameter | value | unit
    2023-01-15 | RAIN-01 | raanana | TCE | 250 | μg/L
    ...
    
  Sheet "Boreholes":
    borehole_id | industrial_area | latitude | longitude | depth_m
    RAIN-01 | raanana | 32.1950 | 34.8639 | 45
    ...
    
  Sheet "Standards":
    parameter | value | unit
    TCE | 5 | μg/L
    ...
```

**Step 3: Generate Report**
```python
from data_sources.excel_importer import ExcelDataSource
from analysis.water_quality_analyzer import WaterQualityAnalyzer
from analysis.pollution_source_analyzer import PollutionSourceAnalyzer
from data_sources.prtr import PRTRDataSource
from reporting.report_generator import ReportGenerator
from config import DRINKING_WATER_STANDARDS

# Load your data
excel = ExcelDataSource(Path("my_data.xlsx"))
water_data = excel.load_water_quality_data()
standards = excel.load_standards()

# Analyze
qa = WaterQualityAnalyzer(standards)
quality_summary = qa.generate_quality_summary(water_data)
contaminated = qa.get_contaminated_boreholes(water_data)

# Identify sources
prtr = PRTRDataSource()
facilities = prtr.get_facilities_by_area("your_area")
psa = PollutionSourceAnalyzer()
sources = psa.identify_priority_facilities(facilities, ["TCE"])

# Generate report
gen = ReportGenerator()
report = gen.generate_area_report(
    area_name="Your Area",
    water_quality_summary=quality_summary,
    contaminated_boreholes=contaminated,
    pollution_sources=sources
)
print(f"Report saved: {report}")
```

### Option B: Integrate With Another Area

**Edit config.py:**
```python
INDUSTRIAL_AREAS = {
    "raanana": {...},
    "your_area": {
        "hebrew": "שם בעברית",
        "region": "Central",
        "known_contaminants": ["TCE", "PCE"],
        "status": "Under investigation"
    }
}
```

**Update PRTR data:**
```python
# In data_sources/prtr.py, add your area's facilities:
facilities = {
    "your_area": [
        {
            "facility_id": "NEW-001",
            "name": "Facility Name",
            "industry_type": "Metal Coating",
            "reported_emissions": {"TCE": 100}
        }
    ]
}
```

### Option C: Connect Real Data.gov.il API

If you have network access to data.gov.il:

```python
from data_sources.water_authority import WaterAuthorityDataSource

wa = WaterAuthorityDataSource()
data = wa.get_borehole_data(
    industrial_area="raanana",
    start_date="2020-01-01",
    end_date="2026-12-31",
    limit=5000
)
# Now use with analysis modules
```

---

## Medium Term (Next Month)

### Automate Report Generation

Create a scheduling script:

```python
# run_monthly_reports.py
from datetime import datetime
from pathlib import Path
import schedule
import time

def generate_all_area_reports():
    """Generate reports for all monitored areas"""
    from config import INDUSTRIAL_AREAS
    from data_sources.excel_importer import ExcelDataSource
    # ... load data, analyze, generate reports
    
    for area in INDUSTRIAL_AREAS.keys():
        print(f"Generating report for {area}...")
        # ... your report generation code
        
    print(f"Reports generated: {datetime.now()}")

# Schedule to run monthly on the 1st
schedule.every().month.at("09:00").do(generate_all_area_reports)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Add Visualization

Enhance reports with charts:

```python
import matplotlib.pyplot as plt
import pandas as pd

# Trend plot
def plot_contamination_trend(data):
    plt.figure(figsize=(10, 6))
    for bh in data['borehole_id'].unique():
        bh_data = data[data['borehole_id'] == bh]
        plt.plot(bh_data['date'], bh_data['value'], label=bh)
    plt.xlabel('Date')
    plt.ylabel('Concentration (μg/L)')
    plt.legend()
    plt.savefig('trend.png')
```

### Send Email Reports

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_report_email(report_path, recipients):
    """Email generated report"""
    msg = MIMEMultipart()
    msg['Subject'] = "Monthly Water Quality Report"
    msg['From'] = "monitoring@example.com"
    msg['To'] = ", ".join(recipients)
    
    with open(report_path) as f:
        msg.attach(MIMEText(f.read(), 'html'))
    
    # Send via SMTP
```

---

## Long Term (Strategic)

### 1. Build a Database Backend

```python
# Replace Excel with PostgreSQL
import psycopg2

class PostgreSQLDataSource:
    def __init__(self, connection_string):
        self.conn = psycopg2.connect(connection_string)
    
    def load_water_quality_data(self):
        query = "SELECT * FROM water_quality WHERE date > NOW() - INTERVAL 1 YEAR"
        return pd.read_sql(query, self.conn)
```

### 2. Create Web Dashboard

```python
# Flask web app
from flask import Flask, render_template
import json

app = Flask(__name__)

@app.route('/report/<area>')
def show_report(area):
    with open(f'reports/Report_{area}.json') as f:
        data = json.load(f)
    return render_template('report.html', report=data)

@app.route('/api/contamination/<area>')
def api_contamination(area):
    return jsonify(get_area_contamination(area))

if __name__ == '__main__':
    app.run(debug=True)
```

### 3. Add Predictive Analytics

```python
from sklearn.linear_model import LinearRegression
import numpy as np

def predict_future_contamination(historical_data, months_ahead=12):
    """Predict contamination trends"""
    X = np.arange(len(historical_data)).reshape(-1, 1)
    y = historical_data['value'].values
    
    model = LinearRegression()
    model.fit(X, y)
    
    future_X = np.arange(len(historical_data), len(historical_data) + months_ahead).reshape(-1, 1)
    predictions = model.predict(future_X)
    
    return predictions
```

### 4. Integrate GIS Mapping

```python
import folium
import geopandas as gpd

def create_contamination_map(boreholes, contamination_data):
    """Create interactive GIS map"""
    m = folium.Map(location=[32.2, 34.8], zoom_start=10)
    
    for bh in boreholes:
        status = "contaminated" if bh['id'] in contamination_data else "ok"
        color = "red" if status == "contaminated" else "green"
        
        folium.CircleMarker(
            location=[bh['latitude'], bh['longitude']],
            radius=10,
            color=color,
            popup=f"{bh['id']} - {status}"
        ).add_to(m)
    
    m.save('contamination_map.html')
```

### 5. Scale to All Industrial Areas

```python
# Process all 18+ monitored areas
from concurrent.futures import ThreadPoolExecutor

areas = list(INDUSTRIAL_AREAS.keys())

def process_area(area):
    """Generate report for single area"""
    # ... full pipeline
    return report_path

with ThreadPoolExecutor(max_workers=4) as executor:
    reports = executor.map(process_area, areas)
    
print(f"Generated {len(list(reports))} reports")
```

---

## File-by-File Guide

### To Understand the System:
- `SUMMARY.md` - What was built
- `QUICKSTART.md` - How to use
- `IMPLEMENTATION.md` - Technical details

### To Use Right Now:
- `config.py` - Customize settings
- `data_sources/excel_importer.py` - Use your Excel data
- `demo/raanana_demo.py` - See full pipeline

### To Extend:
- `data_sources/*.py` - Add data connectors
- `analysis/*.py` - Add analysis modules
- `reporting/*.py` - Customize reports

### To Test:
- `tests/test_analysis.py` - Example unit tests
- Add your own test cases as you extend

---

## Support Resources

### Within the System:
- Every .py file has docstrings explaining functions
- `config.py` is fully commented
- `IMPLEMENTATION.md` details the architecture

### External Resources:
- **data.gov.il API:** https://data.gov.il
- **PRTR Registry:** https://www.gov.il/he/pages/prtr
- **Mei Raanana:** https://mei-raanana.co.il
- **GovMap GIS:** https://www.govmap.gov.il

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Module not found" | `pip install -r requirements.txt` |
| Can't access gov.il APIs | Use Excel import instead (offline works) |
| Report not generating | Check `reports/` dir exists, review `config.py` |
| Data format wrong | Use `ExcelDataSource.create_template_excel()` |
| Analysis seems wrong | Check water quality standards in `config.py` |

---

## Key Takeaways

✅ **You have a complete framework** - Don't reinvent the wheel  
✅ **It's designed to be extended** - Add data sources, analyses, outputs easily  
✅ **Works offline** - Excel import doesn't need internet  
✅ **Raanana is documented** - See how everything fits together  
✅ **Ready for production** - Just connect your real data  

---

**Start here:** `cd Industrial-Areas-Report && python demo/raanana_demo.py`

Any questions? Review the relevant documentation or read the source code — it's all well-commented! 🚀
