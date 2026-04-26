"""Tier-based source attribution plugin.

Ranks candidate pollution sources using a 5-tier industry classification
combined with emission-family matching.  Produces legally cautious Hebrew
phrases per the Water Authority vocabulary conventions.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from core.contracts import Attribution, FamilyReport
from core.registry import register_plugin

# ---------------------------------------------------------------------------
# Industry type -> tier mapping (1 = highest risk, 5 = lowest)
# ---------------------------------------------------------------------------
INDUSTRY_TIERS: Dict[str, int] = {
    # Tier 1: Heavy industry
    "chemical_industry": 1, "waste_treatment": 1, "formulation": 1,
    # Tier 2: Semi-industrial with chemicals
    "metal_coating": 2, "electronics": 2, "printing": 2, "surface_treatment": 2,
    # Tier 3: Fuel / energy
    "gas_station": 3, "power_station": 3, "fuel_depot": 3,
    # Tier 4: Small point sources
    "auto_repair": 4, "body_shop": 4, "vehicle_service": 4,
    # Tier 5: Light commercial
    "retail": 5, "warehouse": 5, "office": 5,
}

TIER_WEIGHTS: Dict[int, float] = {
    1: 1.0,
    2: 0.8,
    3: 0.6,
    4: 0.3,
    5: 0.1,
}


def _select_phrase(score: float) -> str:
    """Return a cautious Hebrew attribution phrase based on *score*."""
    if score > 0.7:
        return "מועמד ליבה"
    if score > 0.4:
        return "מועמד משני"
    if score > 0.2:
        return "רקע מקומי"
    return "לא תומך בפלומה המרכזית"


@register_plugin("source_attributor", name="tier_based")
class TierBasedAttributor:
    """Score candidate facilities using a 5-tier industry classification."""

    version: str = "1.0"

    def attribute(
        self,
        family_report: FamilyReport,
        candidates: List[Dict],
        flow_direction_deg: Optional[float] = None,
    ) -> List[Attribution]:
        """Return attributions sorted by descending score.

        Parameters
        ----------
        family_report:
            The contaminant family report for the current area/well group.
        candidates:
            Each dict must contain ``facility_id``, ``name``,
            ``industry_type``, and ``reported_emissions`` (Dict[str, float]).
        flow_direction_deg:
            Optional groundwater flow direction (degrees).  Logged in
            evidence but never used as sole attribution signal.
        """
        family_members = set(family_report.member_indices.keys())
        results: List[Attribution] = []

        for facility in candidates:
            tier = INDUSTRY_TIERS.get(facility["industry_type"], 5)
            tier_weight = TIER_WEIGHTS[tier]

            emissions = facility.get("reported_emissions", {})
            emission_match = (
                1.0 if family_members & set(emissions.keys()) else 0.5
            )

            score = min(tier_weight * emission_match, 1.0)

            matched = sorted(family_members & set(emissions.keys()))

            evidence: Dict = {
                "tier": tier,
                "tier_weight": tier_weight,
                "emission_match": emission_match,
            }
            if flow_direction_deg is not None:
                evidence["flow_direction_deg"] = flow_direction_deg

            results.append(
                Attribution(
                    facility_id=facility["facility_id"],
                    facility_name=facility["name"],
                    score=round(score, 4),
                    tier=tier,
                    cautious_phrase=_select_phrase(score),
                    matched_families=matched,
                    evidence=evidence,
                )
            )

        results.sort(key=lambda a: a.score, reverse=True)
        return results
