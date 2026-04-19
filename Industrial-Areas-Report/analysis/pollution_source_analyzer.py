"""
Pollution Source Analyzer
Analyzes potential industrial pollution sources using PRTR and environmental data
"""

from typing import Dict, List, Optional


class PollutionSourceAnalyzer:
    """Analyze potential pollution sources in industrial areas"""

    def __init__(self):
        """Initialize pollution source analyzer"""
        self.contamination_chemical_mapping = {
            "TCE": ["Metal coating", "Surface treatment", "Chlorinated solvent use", "Dry cleaning (historical)"],
            "PCE": ["Dry cleaning", "Metal degreasing", "Chlorinated solvent use"],
            "Benzene": ["Fuel handling", "Chemical manufacturing", "Printing"],
            "Toluene": ["Chemical manufacturing", "Fuel handling", "Printing"],
            "Chlorides": ["Deicing salt", "Industrial processes", "Wastewater discharge"],
            "Nitrates": ["Agriculture", "Fertilizer production", "Wastewater treatment"],
            "Heavy_Metals": ["Metal plating", "Metal finishing", "Electronics manufacturing"]
        }

    def match_contamination_to_sources(
        self,
        detected_contaminants: List[str],
        prtr_facilities: List[Dict]
    ) -> List[Dict]:
        """
        Match detected groundwater contaminants to potential PRTR-reporting facilities

        Args:
            detected_contaminants: List of contaminants found in groundwater
            prtr_facilities: List of PRTR-reporting facilities in area

        Returns:
            List of matched sources with confidence scores
        """
        matches = []

        for facility in prtr_facilities:
            for contaminant in detected_contaminants:
                possible_sources = self.contamination_chemical_mapping.get(contaminant, [])

                # Check if facility industry type matches
                facility_type = facility.get("industry_type", "").lower()
                confidence = 0

                for source in possible_sources:
                    if source.lower() in facility_type:
                        confidence = max(confidence, 0.9)
                    # Check if facility reports this chemical
                    elif contaminant in facility.get("reported_emissions", {}):
                        confidence = max(confidence, 0.7)

                if confidence > 0.5:
                    matches.append({
                        "facility_id": facility["facility_id"],
                        "facility_name": facility["name"],
                        "industry_type": facility.get("industry_type"),
                        "detected_contaminant": contaminant,
                        "confidence": confidence,
                        "possible_cause": ", ".join(possible_sources[:2]) if possible_sources else "Unknown",
                        "reported_substance": contaminant in facility.get("reported_emissions", {}),
                        "emissions_kg": facility.get("reported_emissions", {}).get(contaminant)
                    })

        return sorted(matches, key=lambda x: x["confidence"], reverse=True)

    def assess_facility_risk(
        self,
        facility: Dict,
        detected_contaminants: List[str],
        distance_to_well_m: Optional[float] = None
    ) -> Dict:
        """
        Assess contamination risk from a specific facility

        Args:
            facility: PRTR facility data
            detected_contaminants: Contaminants found in nearby wells
            distance_to_well_m: Distance from facility to well in meters

        Returns:
            Risk assessment
        """
        # Base risk from emissions
        emissions_qty = sum(
            facility.get("reported_emissions", {}).get(c, 0)
            for c in detected_contaminants
        )

        if emissions_qty == 0:
            base_risk = "Low"
            base_score = 0.2
        elif emissions_qty < 100:
            base_risk = "Medium"
            base_score = 0.5
        elif emissions_qty < 500:
            base_risk = "High"
            base_score = 0.7
        else:
            base_risk = "Very High"
            base_score = 0.9

        # Distance factor (closer = higher risk)
        distance_score = 1.0
        if distance_to_well_m:
            if distance_to_well_m > 500:
                distance_score = 0.3
            elif distance_to_well_m > 300:
                distance_score = 0.6
            # else < 300m: high risk (distance_score = 1.0)

        # Industry type risk
        industry_type = facility.get("industry_type", "").lower()
        if "metal" in industry_type or "coating" in industry_type:
            industry_score = 0.9
        elif "chemical" in industry_type:
            industry_score = 0.85
        elif "fuel" in industry_type or "petroleum" in industry_type:
            industry_score = 0.8
        else:
            industry_score = 0.5

        # Combine scores
        combined_risk = (base_score + distance_score + industry_score) / 3

        if combined_risk > 0.75:
            overall_risk = "Very High"
        elif combined_risk > 0.60:
            overall_risk = "High"
        elif combined_risk > 0.40:
            overall_risk = "Medium"
        else:
            overall_risk = "Low"

        return {
            "facility_id": facility["facility_id"],
            "facility_name": facility["name"],
            "overall_risk": overall_risk,
            "risk_score": combined_risk,
            "emissions_risk": base_risk,
            "distance_risk": "High" if distance_score > 0.7 else "Medium" if distance_score > 0.3 else "Low",
            "industry_risk": "High" if industry_score > 0.75 else "Medium" if industry_score > 0.5 else "Low",
            "recommendation": self._get_risk_recommendation(overall_risk)
        }

    def identify_priority_facilities(
        self,
        facilities: List[Dict],
        detected_contaminants: List[str],
        top_n: int = 5
    ) -> List[Dict]:
        """
        Identify priority facilities for investigation

        Args:
            facilities: List of facilities in area
            detected_contaminants: Contaminants in groundwater
            top_n: Number of top priorities to return

        Returns:
            List of top priority facilities
        """
        priority_list = []

        for facility in facilities:
            risk_assessment = self.assess_facility_risk(facility, detected_contaminants)
            matches = self.match_contamination_to_sources([facility], detected_contaminants)

            priority_score = risk_assessment["risk_score"]
            if matches:
                priority_score += len(matches) * 0.1

            priority_list.append({
                **risk_assessment,
                "priority_score": min(priority_score, 1.0),
                "matched_contaminants": [m["detected_contaminant"] for m in matches]
            })

        return sorted(priority_list, key=lambda x: x["priority_score"], reverse=True)[:top_n]

    def assess_historical_liability(
        self,
        facility: Dict,
        contaminant: str
    ) -> Dict:
        """
        Assess whether contaminant could be from historical operations

        Args:
            facility: Facility data
            contaminant: Contaminant to assess

        Returns:
            Historical liability assessment
        """
        historically_used = {
            "TCE": ["1970-2005", "Metal surface treatment, dry cleaning"],
            "PCE": ["1960-2005", "Dry cleaning, metal degreasing"],
            "Benzene": ["1950-present", "Fuel handling, chemical manufacturing"]
        }

        if contaminant not in historically_used:
            return {
                "contaminant": contaminant,
                "likely_historical": "Unknown",
                "risk_level": "Unclear"
            }

        period, uses = historically_used[contaminant]
        facility_type = facility.get("industry_type", "").lower()

        likely = any(use.lower() in facility_type for use in uses.split(", "))

        return {
            "contaminant": contaminant,
            "historical_use_period": period,
            "likely_uses": uses,
            "facility_matches_use": likely,
            "likely_historical": "Yes" if likely else "Unlikely",
            "risk_level": "High" if likely else "Low"
        }

    @staticmethod
    def _get_risk_recommendation(risk_level: str) -> str:
        """Get recommendation based on risk level"""
        recommendations = {
            "Very High": "Immediate investigation required. Consider emergency response protocols.",
            "High": "Urgent investigation needed. Remediation planning should begin.",
            "Medium": "Investigation recommended within 6 months. Monitor with regular testing.",
            "Low": "Routine monitoring. No immediate action required."
        }
        return recommendations.get(risk_level, "Unknown risk level")
