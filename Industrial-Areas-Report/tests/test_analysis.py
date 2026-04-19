"""Tests for analysis modules"""

import pytest
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.water_quality_analyzer import WaterQualityAnalyzer
from analysis.pollution_source_analyzer import PollutionSourceAnalyzer


class TestWaterQualityAnalyzer:
    """Test water quality analyzer"""

    def setup_method(self):
        """Set up test fixtures"""
        self.standards = {
            "TCE": 5.0,
            "Chlorides": 250,
            "Nitrates": 50
        }
        self.analyzer = WaterQualityAnalyzer(self.standards)

    def test_assess_contamination_severity_none(self):
        """Test assessment of non-contaminated sample"""
        result = self.analyzer.assess_contamination_severity("TCE", 2.0)
        assert result["severity"] == "none"

    def test_assess_contamination_severity_severe(self):
        """Test assessment of severely contaminated sample"""
        result = self.analyzer.assess_contamination_severity("TCE", 25.0)
        assert result["severity"] == "severe"

    def test_assess_contamination_severity_very_severe(self):
        """Test assessment of very severely contaminated sample"""
        result = self.analyzer.assess_contamination_severity("TCE", 50.0)
        assert result["severity"] == "very_severe"

    def test_analyze_parameter_trend_increasing(self):
        """Test trend analysis for increasing values"""
        data = pd.DataFrame({
            "date": ["2023-01-01", "2023-02-01", "2023-03-01"],
            "value": [10, 15, 20]
        })
        result = self.analyzer.analyze_parameter_trend(data)
        assert result["trend"] == "increasing"

    def test_analyze_parameter_trend_decreasing(self):
        """Test trend analysis for decreasing values"""
        data = pd.DataFrame({
            "date": ["2023-01-01", "2023-02-01", "2023-03-01"],
            "value": [20, 15, 10]
        })
        result = self.analyzer.analyze_parameter_trend(data)
        assert result["trend"] == "decreasing"

    def test_get_contaminated_boreholes(self):
        """Test identification of contaminated boreholes"""
        data = pd.DataFrame({
            "borehole_id": ["W1", "W1", "W2"],
            "parameter": ["TCE", "Chlorides", "TCE"],
            "value": [50.0, 200, 2.0]
        })
        result = self.analyzer.get_contaminated_boreholes(data, threshold_percent=100)
        assert len(result) > 0
        assert any(b["borehole_id"] == "W1" for b in result)


class TestPollutionSourceAnalyzer:
    """Test pollution source analyzer"""

    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = PollutionSourceAnalyzer()

    def test_match_contamination_to_sources(self):
        """Test matching contaminants to facility types"""
        facilities = [
            {
                "facility_id": "F1",
                "name": "Metal Coating Facility",
                "industry_type": "Metal Surface Treatment",
                "reported_emissions": {"TCE": 100}
            }
        ]

        matches = self.analyzer.match_contamination_to_sources(
            ["TCE"], facilities
        )

        assert len(matches) > 0
        assert matches[0]["confidence"] > 0.5

    def test_assess_facility_risk(self):
        """Test facility risk assessment"""
        facility = {
            "facility_id": "F1",
            "name": "Metal Coating Facility",
            "industry_type": "Metal Surface Treatment",
            "reported_emissions": {"TCE": 150}
        }

        risk = self.analyzer.assess_facility_risk(
            facility, ["TCE"], distance_to_well_m=200
        )

        assert risk["overall_risk"] in ["Low", "Medium", "High", "Very High"]
        assert 0 <= risk["risk_score"] <= 1

    def test_identify_priority_facilities(self):
        """Test prioritization of facilities"""
        facilities = [
            {
                "facility_id": "F1",
                "name": "Metal Coating Facility A",
                "industry_type": "Metal Surface Treatment",
                "reported_emissions": {"TCE": 150}
            },
            {
                "facility_id": "F2",
                "name": "Chemical Facility B",
                "industry_type": "Chemical Manufacturing",
                "reported_emissions": {"Benzene": 50}
            }
        ]

        priorities = self.analyzer.identify_priority_facilities(
            facilities, ["TCE"], top_n=2
        )

        assert len(priorities) <= 2
        assert all("priority_score" in p for p in priorities)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
