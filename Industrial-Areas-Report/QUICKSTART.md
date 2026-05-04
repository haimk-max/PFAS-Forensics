# Quick Start Guide

## 1. Setup

```bash
cd Industrial-Areas-Report
pip install -r requirements.txt
```

## 2. Run Demo (Raanana Case Study)

```bash
python demo/raanana_demo.py
```

Output:
- Console summary with findings
- HTML report: `reports/Report_Raanana_*.html`
- JSON report: `reports/Report_Raanana_*.json`

## 3. System Overview

### Pipeline in 5 Steps

```
[Data Sources] → [Analysis] → [Report Generation]
```

**Data Sources:**
- Water Authority (water quality samples)
- PRTR Registry (industrial emissions)
- Mei Raanana (wastewater monitoring)

**Analysis:**
- Contamination severity assessment
- Trend detection (increasing/decreasing)
- Facility risk ranking

**Reports:**
- HTML: Interactive, human-readable
- JSON: Machine-parseable, for further processing

### Key Classes

```python
# Data
WaterAuthorityDataSource()   # API to water samples
PRTRDataSource()             # Industrial emissions registry
MeiRaananaDataSource()       # Wastewater monitoring
ExcelDataSource(file)        # Load from Excel

# Analysis
WaterQualityAnalyzer()       # Contamination assessment
PollutionSourceAnalyzer()    # Facility risk ranking

# Output
ReportGenerator()            # Generate reports
```

## 4. Use Your Own Data

### Option A: Excel File

1. Create spreadsheet using template:
```python
from data_sources.excel_importer import ExcelDataSource
ExcelDataSource.create_template_excel(Path("my_data.xlsx"))
```

2. Fill with your water quality data:
- Sheet "Water_Quality": date, borehole_id, parameter, value, unit
- Sheet "Boreholes": borehole_id, latitude, longitude, depth_m
- Sheet "Standards": parameter, value, unit

3. Load and analyze:
```python
from data_sources.excel_importer import ExcelDataSource
source = ExcelDataSource(Path("my_data.xlsx"))
water_data = source.load_water_quality_data()
```

### Option B: Direct API

For real Water Authority data:
```python
from data_sources.water_authority import WaterAuthorityDataSource
source = WaterAuthorityDataSource()
data = source.get_borehole_data("raanana")
```

## 5. Generate a Report

```python
from pathlib import Path
from data_sources.excel_importer import ExcelDataSource
from data_sources.prtr import PRTRDataSource
from data_sources.mei_raanana import MeiRaananaDataSource
from analysis.water_quality_analyzer import WaterQualityAnalyzer
from analysis.pollution_source_analyzer import PollutionSourceAnalyzer
from reporting.report_generator import ReportGenerator
from config import DRINKING_WATER_STANDARDS

# Load data
excel = ExcelDataSource(Path("my_data.xlsx"))
water_data = excel.load_water_quality_data()
prtr = PRTRDataSource()
facilities = prtr.get_facilities_by_area("raanana")

# Analyze
qa = WaterQualityAnalyzer(DRINKING_WATER_STANDARDS)
quality_summary = qa.generate_quality_summary(water_data)
contaminated = qa.get_contaminated_boreholes(water_data)

psa = PollutionSourceAnalyzer()
sources = psa.identify_priority_facilities(facilities, ["TCE"])

# Generate report
gen = ReportGenerator()
report = gen.generate_area_report(
    area_name="My Area",
    water_quality_summary=quality_summary,
    contaminated_boreholes=contaminated,
    pollution_sources=sources,
    output_format="both"  # Creates .html and .json
)

print(f"Report saved to: {report}")
```

## 6. Understand the Results

### Contamination Severity Scale

```
Ratio to Drinking Water Standard | Assessment
< 50%                           | None (לא מזוהם)
50-100%                         | Mild (זיהום קל)
100-300%                        | Moderate (זיהום בינוני)
300-600%                        | Severe (זיהום חמור)
> 600%                          | Very Severe (זיהום חמור מאד)
```

Example: If TCE standard is 5 μg/L and measured is 25 μg/L:
- Ratio = 25/5 = 5.0 (500%)
- Severity = **Severe**

### Risk Assessment

Facilities scored on:
1. **Emissions Quantity** (40%) - How much they report
2. **Distance to Well** (30%) - Proximity to contamination
3. **Industry Type** (30%) - Match to contamination type

Risk Levels:
- 🟢 **Low** (0-0.4)
- 🟡 **Medium** (0.4-0.6)
- 🟠 **High** (0.6-0.75)
- 🔴 **Very High** (>0.75)

## 7. Raanana Results (Demo)

The demo shows:

**Water Quality Finding:**
- TCE detected: 250-310 μg/L (50-62x drinking water standard)
- Severity: **SEVERE**
- Trend: **INCREASING**

**Top Pollution Sources:**
1. Metal Coating Facility A
   - Industry: Metal Surface Treatment
   - Risk: Very High
   - Emissions: TCE 150 kg/year

2. Chemical Facility B
   - Industry: Chemical Manufacturing  
   - Risk: High
   - Emissions: Benzene 50 kg/year

**Wastewater Monitoring:**
- 2 factories in program
- 87.5% compliance rate
- 3 violations in last year

## 8. Troubleshooting

| Problem | Solution |
|---------|----------|
| "Module not found" | Run `pip install -r requirements.txt` |
| "File not found" | Check path, use absolute paths |
| No report generated | Check `reports/` directory exists |
| API errors | Use Excel import instead of live API |
| Encoding errors | Save Excel as UTF-8 |

## 9. Next Steps

1. **Adapt for your area:**
   - Edit `config.py` with your industrial area name
   - Add to `INDUSTRIAL_AREAS` dictionary

2. **Add more data sources:**
   - Create new module in `data_sources/`
   - Implement data connector
   - Update demo

3. **Customize reports:**
   - Edit HTML template in `reporting/report_generator.py`
   - Add charts, maps, additional sections

4. **Schedule automation:**
   - Run demo via cron (Linux/Mac) or Task Scheduler (Windows)
   - Generate reports monthly/annually
   - Email results automatically

## 10. Key Files

```
Industrial-Areas-Report/
├── README.md                      # Project overview
├── IMPLEMENTATION.md              # Technical details
├── QUICKSTART.md                  # This file
├── config.py                      # Settings & standards
├── requirements.txt               # Python dependencies
│
├── data_sources/                  # Data connectors
│   ├── water_authority.py         # Water Authority API
│   ├── prtr.py                    # PRTR emissions registry
│   ├── mei_raanana.py             # Mei Raanana wastewater
│   └── excel_importer.py          # Excel file loader
│
├── analysis/                      # Data analysis
│   ├── water_quality_analyzer.py  # Contamination assessment
│   └── pollution_source_analyzer.py # Facility risk ranking
│
├── reporting/                     # Report generation
│   └── report_generator.py        # HTML/JSON report creation
│
├── demo/                          # Example usage
│   └── raanana_demo.py            # Complete pipeline demo
│
└── tests/                         # Unit tests
    └── test_analysis.py           # Analysis tests
```

---

**Ready to use!** Start with `python demo/raanana_demo.py` →
