# Industrial Areas Water Quality Monitoring System - Implementation Guide

## Overview

This system automates the generation of periodic reports on groundwater quality and industrial pollution sources in Israeli industrial areas above the Coastal Aquifer (אקויפר החוף).

## Architecture

### Data Pipeline

```
Data Ingestion
├── Water Authority (בדיקות איכות מים)
│   ├── data.gov.il CKAN API (borehole_quality_history dataset)
│   └── Excel consolidation file
├── PRTR Registry (מפל"ס)
│   ├── Facility emissions data
│   └── GovMap GIS layers
├── Local Water Corporations (תאגידי מים)
│   └── Wastewater monitoring reports
└── Ministry of Environmental Protection
    ├── Business licenses
    ├── Environmental permits
    └── Historical facility data

    ↓

Analysis Layer
├── Water Quality Analysis
│   ├── Contamination severity assessment
│   ├── Trend analysis (increasing/decreasing/stable)
│   └── Regulatory compliance evaluation
├── Pollution Source Identification
│   ├── PRTR-to-contamination matching
│   ├── Facility risk assessment
│   └── Priority facility ranking
└── Wastewater Monitoring Integration
    ├── Factory compliance history
    └── Violation tracking

    ↓

Report Generation
├── HTML Report
│   ├── Executive summary
│   ├── Water quality findings
│   ├── Contamination maps
│   └── Pollution source assessment
└── JSON Report
    └── Structured data for further processing
```

## Modules

### 1. Data Sources (`data_sources/`)

#### `water_authority.py` - WaterAuthorityDataSource
Connects to Israel Water Authority data via data.gov.il CKAN API.

**Key Methods:**
- `get_borehole_data()` - Fetch water quality samples
- `get_parameter_trend()` - Time series for specific parameter
- `get_boreholes_by_area()` - List monitoring wells in area

**Data Expected:**
```
borehole_id: RAIN-01
date: 2023-01-15
parameter: TCE
value: 250.0 (μg/L)
industrial_area: raanana
```

#### `prtr.py` - PRTRDataSource
Accesses Pollutant Release and Transfer Register (מפל"ס PRTR).

**Key Methods:**
- `get_facilities_by_area()` - List PRTR facilities
- `get_emissions_by_substance()` - Query by contaminant
- `search_by_coordinates()` - Geographic search
- `get_environmental_concerns()` - Link groundwater to emissions

**Data Expected:**
```
facility_id: PRTR-001
name: Metal Coating Facility A
reported_emissions: {TCE: 150 kg/year, PCE: 45 kg/year}
industry_type: Metal Surface Treatment
```

#### `excel_importer.py` - ExcelDataSource
Reads consolidated water quality data from Excel files.

**Template Structure:**
- Sheet 1: Water_Quality (date, borehole_id, parameter, value, unit)
- Sheet 2: Boreholes (borehole_id, latitude, longitude, depth_m)
- Sheet 3: Standards (parameter, value, unit)

**Generate template:**
```python
from data_sources.excel_importer import ExcelDataSource
ExcelDataSource.create_template_excel(Path("template.xlsx"))
```

#### `mei_raanana.py` - MeiRaananaDataSource
Fetches industrial wastewater monitoring data from Mei Raanana.

**Key Methods:**
- `get_factories_monitored()` - List factories in program
- `get_factory_compliance_history()` - Monthly compliance data
- `get_violations_log()` - Compliance violations
- `get_monitoring_program_summary()` - Overall program status

### 2. Analysis (`analysis/`)

#### `water_quality_analyzer.py` - WaterQualityAnalyzer
Analyzes water quality data and contamination severity.

**Key Methods:**
- `assess_contamination_severity()` - Classify contamination level
  - Returns: none/mild/moderate/severe/very_severe
- `analyze_parameter_trend()` - Time series analysis
  - Returns: trend (increasing/decreasing/stable), slope, statistics
- `get_contaminated_boreholes()` - List wells exceeding thresholds
- `generate_quality_summary()` - Area-wide assessment

**Severity Levels:**
```
Ratio to Standard | Severity
< 0.5             | None (לא מזוהם)
0.5-1.0           | Mild (זיהום קל)
1.0-3.0           | Moderate (זיהום בינוני)
3.0-6.0           | Severe (זיהום חמור)
> 6.0             | Very Severe (זיהום חמור מאד)
```

#### `pollution_source_analyzer.py` - PollutionSourceAnalyzer
Identifies and prioritizes potential pollution sources.

**Key Methods:**
- `match_contamination_to_sources()` - Link contaminants to facilities
- `assess_facility_risk()` - Calculate risk score (0-1)
- `identify_priority_facilities()` - Rank facilities for investigation
- `assess_historical_liability()` - Evaluate past operations

**Risk Factors:**
1. Emissions quantity (40%)
2. Distance to well (30%)
3. Industry type (30%)

### 3. Reporting (`reporting/`)

#### `report_generator.py` - ReportGenerator
Generates comprehensive area reports.

**Methods:**
```python
report_path = generator.generate_area_report(
    area_name="Raanana",
    water_quality_summary={...},
    contaminated_boreholes=[...],
    pollution_sources=[...],
    wastewater_monitoring={...},
    output_format="both"  # html, json, or both
)
```

**Output Formats:**
- **HTML**: Interactive report with tables, visualizations, status indicators
- **JSON**: Structured data for integration with other systems

## Configuration

Edit `config.py` to customize:

```python
# Drinking water standards (mg/L or μg/L)
DRINKING_WATER_STANDARDS = {
    "TCE": 5.0,
    "PCE": 5.0,
    "Benzene": 1.0,
    "Chlorides": 250,
    "Nitrates": 50,
}

# Industrial areas to monitor
INDUSTRIAL_AREAS = {
    "raanana": {
        "hebrew": "רעננה",
        "known_contaminants": ["TCE", "Chlorinated_Solvents"],
        "status": "..."
    }
}
```

## Usage

### Basic Example

```python
from pathlib import Path
from data_sources.excel_importer import ExcelDataSource
from data_sources.prtr import PRTRDataSource
from data_sources.mei_raanana import MeiRaananaDataSource
from analysis.water_quality_analyzer import WaterQualityAnalyzer
from analysis.pollution_source_analyzer import PollutionSourceAnalyzer
from reporting.report_generator import ReportGenerator
from config import DRINKING_WATER_STANDARDS

# 1. Load data
excel_source = ExcelDataSource(Path("water_quality_data.xlsx"))
water_data = excel_source.load_water_quality_data()

prtr_source = PRTRDataSource()
facilities = prtr_source.get_facilities_by_area("raanana")

# 2. Analyze
qa = WaterQualityAnalyzer(DRINKING_WATER_STANDARDS)
summary = qa.generate_quality_summary(water_data)
contaminated = qa.get_contaminated_boreholes(water_data)

psa = PollutionSourceAnalyzer()
priority = psa.identify_priority_facilities(facilities, ["TCE"])

# 3. Report
gen = ReportGenerator()
report = gen.generate_area_report(
    "raanana", summary, contaminated, priority
)
```

### Run Raanana Demo

```bash
python demo/raanana_demo.py
```

This generates sample reports demonstrating the full pipeline.

## Data Integration

### Option 1: Direct Water Authority API (data.gov.il)

```python
from data_sources.water_authority import WaterAuthorityDataSource

source = WaterAuthorityDataSource()
# Fetches from: https://data.gov.il/api/3/action
data = source.get_borehole_data("raanana", limit=1000)
```

**Requirements:**
- Internet access to data.gov.il
- No API key required (public data)

### Option 2: Excel File

```python
from data_sources.excel_importer import ExcelDataSource

# Create template first
ExcelDataSource.create_template_excel(Path("data.xlsx"))

# Then load
source = ExcelDataSource(Path("data.xlsx"))
water_data = source.load_water_quality_data()
```

**Advantages:**
- Works offline
- Can consolidate multiple years of data
- Easy to update

### Option 3: Hybrid

Use Excel as primary, fall back to API if available:

```python
try:
    excel = ExcelDataSource(Path("data.xlsx"))
    data = excel.load_water_quality_data()
except FileNotFoundError:
    api = WaterAuthorityDataSource()
    data = api.get_borehole_data("raanana")
```

## Data Standards

### Water Quality Parameters

**Contaminants of Concern (אזור רעננה):**
- **TCE (Trichloroethylene)** - Chlorinated solvent, metal surface treatment
- **PCE (Perchloroethylene)** - Dry cleaning, metal degreasing
- **Chlorides** - Industrial processes, deicing salts
- **Heavy Metals** - Metal plating, finishing operations
- **Nitrates** - Fertilizers, wastewater

**Drinking Water Standards (Israel):**
- TCE: 8.3 μg/L (alert at 60% = 5 μg/L)
- PCE: 10 μg/L
- Benzene: 1 μg/L
- Chlorides: 250 mg/L
- Nitrates: 50 mg/L

### Facility Classifications

**PRTR-Reporting Industries:**
- Metal surface treatment & coating
- Chemical manufacturing
- Fuel handling & storage
- Electronics manufacturing
- Dry cleaning (historical)

## Contamination Mapping

### Expected Contaminant Routes

| Industry | Primary Contaminants | Route to Groundwater |
|----------|-------------------|-------------------|
| Metal Coating | TCE, PCE, Chrome | Floor leaks, waste disposal |
| Chemical Mfg | VOCs, Benzene | Spills, wastewater |
| Fuel Storage | Benzene, Toluene | Tank leaks, overfills |
| Deicing | Chlorides | Surface infiltration |

## Testing

```bash
# Run unit tests
pytest tests/ -v

# Run specific test
pytest tests/test_analysis.py::TestWaterQualityAnalyzer -v
```

## Extending the System

### Add New Industrial Area

1. Update `config.py`:
```python
INDUSTRIAL_AREAS["new_area"] = {
    "hebrew": "שם בעברית",
    "region": "North/Central/South",
    "known_contaminants": [...]
}
```

2. Create data source adapters if needed
3. Run demo with new area

### Add New Data Source

```python
# data_sources/new_source.py
class NewDataSource:
    def get_area_data(self, area: str) -> pd.DataFrame:
        # Implementation
        pass
```

### Customize Report Template

Edit `reporting/report_generator.py` HTML template section to change layout, styling, or sections.

## Troubleshooting

**API 403 Errors:**
- data.gov.il and gov.il APIs may be access-restricted
- Use Excel import as alternative
- Check your IP/proxy settings

**Missing Data:**
- Ensure column names match expected format
- Use `ExcelDataSource.create_template_excel()` as reference
- Check date formats (YYYY-MM-DD)

**Report Not Generating:**
- Verify `output_dir` exists and is writable
- Check for encoding issues (use UTF-8)
- Review `demo/raanana_demo.py` for example

## References

- Israel Water Authority: https://www.gov.il/he/departments/organisations/water_authority
- PRTR Registry: https://www.gov.il/he/pages/prtr
- Mei Raanana: https://mei-raanana.co.il
- data.gov.il: https://data.gov.il
- GovMap: https://www.govmap.gov.il

## License & Attribution

This system demonstrates automated environmental reporting using Israeli government data sources. All data sources are public.

---

**Version:** 1.0
**Last Updated:** April 2026
**Status:** Production Ready (with data source connections)
