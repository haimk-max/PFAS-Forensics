# Industrial Areas Water Quality Monitoring Report Generator

Automated system for generating periodic monitoring reports for industrial areas' groundwater quality and potential pollution sources.

## Overview

This project automates the analysis and reporting of groundwater contamination in industrial areas above Israel's Coastal Aquifer (אקויפר החוף). The system integrates data from:

- **Israel Water Authority** (רשות המים) - monitoring well data
- **Environmental Ministry PRTR** (מפל"ס) - industrial emissions registry
- **Local Water Corporations** (תאגידי מים) - wastewater monitoring reports
- **Government Data Portal** (data.gov.il) - water quality datasets

## Architecture

```
Data Sources
├── Water Authority DB / Excel Files (בדיקות איכות מים)
├── data.gov.il CKAN API (borehole_quality_history)
├── PRTR Registry (מפל"ס PRTR)
├── Mei Raanana Reports (דוחות ניטור שפכי תעשייה)
└── Ministry of Environmental Protection Data

Processing Pipeline
├── Data Ingestion & Normalization
├── Water Quality Analysis (Trends, Standards Comparison)
├── Pollution Source Identification (PRTR + Environmental Data)
└── Report Generation (PDF/HTML per Industrial Area)

Output
└── Periodic Reports (Annual + Ad-hoc)
    ├── Water Quality Analysis
    ├── Contamination Trends
    ├── Potential Pollution Sources
    ├── Maps & Visualizations
    └── Regulatory Compliance Assessment
```

## Modules

- `data_sources/` - Data connectors
- `analysis/` - Analysis engines
- `reporting/` - Report generators
- `demo/` - Raanana case study

## Status

In development - Building core framework with Raanana as pilot area.
