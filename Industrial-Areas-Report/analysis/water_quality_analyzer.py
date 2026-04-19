"""
Water Quality Analyzer
Analyzes groundwater quality trends, contamination severity, and regulatory compliance
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime


class WaterQualityAnalyzer:
    """Analyze water quality data for industrial areas"""

    def __init__(self, standards: Dict[str, float]):
        """
        Initialize analyzer with drinking water standards

        Args:
            standards: Dictionary mapping parameter names to limit values
        """
        self.standards = standards

    def assess_contamination_severity(
        self,
        parameter: str,
        measured_value: float
    ) -> Dict:
        """
        Assess severity of contamination for a parameter

        Args:
            parameter: Parameter name
            measured_value: Measured concentration

        Returns:
            Dictionary with severity level and details
        """
        if parameter not in self.standards:
            return {
                "parameter": parameter,
                "severity": "unknown",
                "message": "No standard defined"
            }

        standard = self.standards[parameter]
        ratio = measured_value / standard

        if ratio <= 0.5:
            severity = "none"
            hebrew = "לא מזוהם"
        elif ratio <= 1.0:
            severity = "mild"
            hebrew = "זיהום קל"
        elif ratio <= 3.0:
            severity = "moderate"
            hebrew = "זיהום בינוני"
        elif ratio <= 6.0:
            severity = "severe"
            hebrew = "זיהום חמור"
        else:
            severity = "very_severe"
            hebrew = "זיהום חמור מאד"

        return {
            "parameter": parameter,
            "measured_value": measured_value,
            "standard_value": standard,
            "ratio_to_standard": ratio,
            "severity": severity,
            "hebrew_severity": hebrew,
            "percent_of_standard": ratio * 100
        }

    def analyze_parameter_trend(
        self,
        data: pd.DataFrame
    ) -> Dict:
        """
        Analyze trend of a parameter over time

        Args:
            data: DataFrame with columns 'date' and 'value'

        Returns:
            Trend analysis results
        """
        if data.empty or len(data) < 2:
            return {"trend": "insufficient_data", "message": "Not enough data points"}

        data = data.sort_values("date")
        values = data["value"].values
        dates = pd.to_datetime(data["date"]).values

        # Calculate trend
        n = len(values)
        x = np.arange(n)
        coeffs = np.polyfit(x, values, 1)
        slope = coeffs[0]

        # Trend direction
        if abs(slope) < (np.std(values) * 0.05):
            trend = "stable"
        elif slope > 0:
            trend = "increasing"
        else:
            trend = "decreasing"

        return {
            "trend": trend,
            "slope": slope,
            "mean_value": np.mean(values),
            "std_dev": np.std(values),
            "min_value": np.min(values),
            "max_value": np.max(values),
            "latest_value": values[-1],
            "first_value": values[0],
            "date_range": {
                "start": pd.to_datetime(dates[0]).strftime("%Y-%m-%d"),
                "end": pd.to_datetime(dates[-1]).strftime("%Y-%m-%d")
            },
            "num_samples": n,
            "change_percent": ((values[-1] - values[0]) / values[0] * 100) if values[0] != 0 else None
        }

    def get_contaminated_boreholes(
        self,
        data: pd.DataFrame,
        threshold_percent: float = 100.0
    ) -> List[Dict]:
        """
        Get list of boreholes with contamination above threshold

        Args:
            data: DataFrame with borehole quality data
            threshold_percent: Report if > X% of standard

        Returns:
            List of contaminated boreholes
        """
        if data.empty:
            return []

        contaminated = []

        for borehole_id in data["borehole_id"].unique():
            bh_data = data[data["borehole_id"] == borehole_id]

            max_severity = None
            for param in bh_data["parameter"].unique():
                param_data = bh_data[bh_data["parameter"] == param]
                latest_value = param_data["value"].iloc[-1]

                severity = self.assess_contamination_severity(param, latest_value)

                if severity["ratio_to_standard"] >= (threshold_percent / 100):
                    if max_severity is None or severity["ratio_to_standard"] > max_severity["ratio_to_standard"]:
                        max_severity = severity

            if max_severity:
                max_severity["borehole_id"] = borehole_id
                contaminated.append(max_severity)

        return sorted(contaminated, key=lambda x: x["ratio_to_standard"], reverse=True)

    def generate_quality_summary(self, area_data: pd.DataFrame) -> Dict:
        """
        Generate overall water quality summary for industrial area

        Args:
            area_data: DataFrame with all water quality data for area

        Returns:
            Summary statistics
        """
        if area_data.empty:
            return {"status": "no_data"}

        # Severity assessment
        critical_params = []
        for param in area_data["parameter"].unique():
            param_data = area_data[area_data["parameter"] == param]
            latest = param_data.iloc[-1]["value"]
            severity = self.assess_contamination_severity(param, latest)

            if severity["severity"] in ["severe", "very_severe"]:
                critical_params.append(param)

        return {
            "area": area_data.iloc[0].get("industrial_area", "Unknown"),
            "total_boreholes": area_data["borehole_id"].nunique(),
            "parameters_monitored": area_data["parameter"].nunique(),
            "total_samples": len(area_data),
            "date_range": {
                "start": pd.to_datetime(area_data["date"]).min().strftime("%Y-%m-%d"),
                "end": pd.to_datetime(area_data["date"]).max().strftime("%Y-%m-%d")
            },
            "critical_parameters": critical_params,
            "boreholes_with_contamination": len(self.get_contaminated_boreholes(area_data)),
            "status": "CONCERN" if critical_params else "OK"
        }

    def estimate_contamination_extent(
        self,
        contaminated_boreholes: List[Dict],
        borehole_coordinates: Dict
    ) -> Dict:
        """
        Estimate the geographic extent of contamination

        Args:
            contaminated_boreholes: List of contaminated boreholes
            borehole_coordinates: Dict mapping borehole IDs to coordinates

        Returns:
            Extent analysis
        """
        if not contaminated_boreholes:
            return {"extent": "None detected"}

        # Get coordinates of contaminated boreholes
        coords = []
        for bh in contaminated_boreholes:
            if bh["borehole_id"] in borehole_coordinates:
                coords.append(borehole_coordinates[bh["borehole_id"]])

        if not coords:
            return {"extent": "Unknown - coordinate data missing"}

        lats = [c["latitude"] for c in coords]
        lons = [c["longitude"] for c in coords]

        return {
            "extent": "Multiple boreholes affected",
            "num_contaminated": len(contaminated_boreholes),
            "geographic_range": {
                "latitude": {"min": min(lats), "max": max(lats)},
                "longitude": {"min": min(lons), "max": max(lons)}
            },
            "distance_between_extremes_km": self._haversine_distance(
                min(lats), min(lons), max(lats), max(lons)
            )
        }

    @staticmethod
    def _haversine_distance(lat1, lon1, lat2, lon2) -> float:
        """Calculate distance between two points in kilometers"""
        from math import radians, cos, sin, asin, sqrt

        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        km = 6371 * c
        return km
