"""
Raanana Industrial Area - Demonstration Report Generator

This script demonstrates the full pipeline:
1. Load water quality data
2. Analyze contamination
3. Identify pollution sources from PRTR
4. Generate report
"""

import sys
from pathlib import Path
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_sources.water_authority import WaterAuthorityDataSource
from data_sources.prtr import PRTRDataSource
from data_sources.mei_raanana import MeiRaananaDataSource
from analysis.water_quality_analyzer import WaterQualityAnalyzer
from analysis.pollution_source_analyzer import PollutionSourceAnalyzer
from reporting.report_generator import ReportGenerator
from config import DRINKING_WATER_STANDARDS, INDUSTRIAL_AREAS


def create_sample_water_quality_data() -> pd.DataFrame:
    """Create sample water quality data for Raanana for demonstration"""
    return pd.DataFrame([
        # TCE contamination in well RAIN-01
        {
            "date": "2023-01-15",
            "borehole_id": "RAIN-01",
            "industrial_area": "raanana",
            "parameter": "TCE",
            "value": 250.0,
            "unit": "μg/L"
        },
        {
            "date": "2023-02-20",
            "borehole_id": "RAIN-01",
            "industrial_area": "raanana",
            "parameter": "TCE",
            "value": 280.0,
            "unit": "μg/L"
        },
        {
            "date": "2023-03-15",
            "borehole_id": "RAIN-01",
            "industrial_area": "raanana",
            "parameter": "TCE",
            "value": 310.0,
            "unit": "μg/L"
        },
        # Chlorides in wells
        {
            "date": "2023-01-15",
            "borehole_id": "RAIN-01",
            "industrial_area": "raanana",
            "parameter": "Chlorides",
            "value": 450.0,
            "unit": "mg/L"
        },
        {
            "date": "2023-03-15",
            "borehole_id": "RAIN-01",
            "industrial_area": "raanana",
            "parameter": "Chlorides",
            "value": 480.0,
            "unit": "mg/L"
        },
        # Well RAIN-02
        {
            "date": "2023-01-15",
            "borehole_id": "RAIN-02",
            "industrial_area": "raanana",
            "parameter": "TCE",
            "value": 50.0,
            "unit": "μg/L"
        },
        {
            "date": "2023-03-15",
            "borehole_id": "RAIN-02",
            "industrial_area": "raanana",
            "parameter": "TCE",
            "value": 75.0,
            "unit": "μg/L"
        },
    ])


def run_raanana_demo():
    """Run demonstration report generation for Raanana"""
    print("=" * 80)
    print("Industrial Areas Water Quality Monitoring Report Generator")
    print("Demo: Raanana Industrial Area (אזור תעשייה רעננה)")
    print("=" * 80)

    # 1. Load data sources
    print("\n[1/5] Loading data sources...")
    water_qa = WaterAuthorityDataSource()
    prtr = PRTRDataSource()
    mei = MeiRaananaDataSource()

    # Create sample data for demo (in production, would use real APIs)
    water_data = create_sample_water_quality_data()
    print(f"    ✓ Water quality data: {len(water_data)} samples loaded")

    prtr_facilities = prtr.get_facilities_by_area("raanana")
    print(f"    ✓ PRTR facilities: {len(prtr_facilities)} facilities found")

    factories = mei.get_factories_monitored()
    print(f"    ✓ Mei Raanana: {len(factories)} factories in monitoring program")

    # 2. Analyze water quality
    print("\n[2/5] Analyzing water quality...")
    analyzer = WaterQualityAnalyzer(DRINKING_WATER_STANDARDS)

    area_data = water_data[water_data["industrial_area"] == "raanana"]
    quality_summary = analyzer.generate_quality_summary(area_data)
    print(f"    ✓ Status: {quality_summary.get('status', 'Unknown')}")
    print(f"    ✓ Critical parameters: {', '.join(quality_summary.get('critical_parameters', []))}")

    contaminated_boreholes = analyzer.get_contaminated_boreholes(area_data)
    print(f"    ✓ Contaminated wells: {len(contaminated_boreholes)}")

    # 3. Identify pollution sources
    print("\n[3/5] Identifying pollution sources...")
    source_analyzer = PollutionSourceAnalyzer()

    detected_contaminants = quality_summary.get("critical_parameters", [])
    priority_facilities = source_analyzer.identify_priority_facilities(
        prtr_facilities, detected_contaminants, top_n=3
    )
    print(f"    ✓ Priority facilities for investigation: {len(priority_facilities)}")

    for i, facility in enumerate(priority_facilities, 1):
        print(f"      {i}. {facility['facility_name']} - Risk: {facility['overall_risk']}")

    # 4. Get wastewater monitoring data
    print("\n[4/5] Retrieving wastewater monitoring data...")
    wastewater_summary = mei.get_monitoring_program_summary()
    print(f"    ✓ Compliance rate: {wastewater_summary.get('average_compliance_rate')}%")
    print(f"    ✓ Violations YTD: {wastewater_summary.get('total_violations_ytd')}")

    # 5. Generate report
    print("\n[5/5] Generating report...")
    report_gen = ReportGenerator()
    report_path = report_gen.generate_area_report(
        area_name="Raanana",
        water_quality_summary=quality_summary,
        contaminated_boreholes=contaminated_boreholes,
        pollution_sources=priority_facilities,
        wastewater_monitoring=wastewater_summary,
        output_format="both"
    )
    print(f"    ✓ Report generated: {report_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY - Raanana Industrial Area Water Quality Assessment")
    print("=" * 80)
    print(f"\n📊 Water Quality Status: {quality_summary.get('status')}")
    print(f"\n🔍 Detected Contamination:")
    for param in detected_contaminants:
        print(f"   - {param}")

    print(f"\n⚠️  Top Pollution Sources to Investigate:")
    for facility in priority_facilities[:3]:
        print(f"   - {facility['facility_name']} ({facility['industry_type']})")
        print(f"     Risk Level: {facility['overall_risk']}")
        if facility.get('matched_contaminants'):
            print(f"     Linked to: {', '.join(facility['matched_contaminants'])}")

    print(f"\n🏭 Industrial Wastewater Monitoring:")
    print(f"   - {wastewater_summary.get('total_factories')} factories monitored")
    print(f"   - {wastewater_summary.get('average_compliance_rate')}% compliance rate")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    run_raanana_demo()
