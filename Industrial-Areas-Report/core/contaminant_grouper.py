"""Assign individual contaminants to one of 7 families."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

CONTAMINANT_GROUPS: Dict[str, Dict] = {
    "chlorinated_solvents": {
        "hebrew": "ממסים מוכלרים",
        "members": {
            "TCE", "PCE", "cis-1,2-DCE", "trans-1,2-DCE", "1,1-DCE",
            "Vinyl_Chloride", "1,1,1-TCA", "1,1,2-TCA", "Chloroform",
            "Carbon_Tetrachloride", "Methylene_Chloride",
        },
        "degradation_chain": ["PCE", "TCE", "cis-1,2-DCE", "Vinyl_Chloride"],
        "source_indicators": [
            "chemical_industry", "electronics", "dry_cleaning",
            "metal_degreasing", "printed_circuits",
        ],
    },
    "fuels": {
        "hebrew": "דלקים ומרכיביהם",
        "members": {
            "Benzene", "Toluene", "Ethylbenzene", "Xylene",
            "MTBE", "TPH", "Diesel", "Gasoline",
        },
        "degradation_chain": [],
        "source_indicators": ["gas_station", "fuel_depot", "vehicle_service"],
    },
    "metals": {
        "hebrew": "מתכות ומתכות למחצה",
        "members": {
            "Chromium", "Lead", "Cadmium", "Nickel", "Copper",
            "Zinc", "Boron", "Arsenic", "Mercury", "Selenium",
        },
        "degradation_chain": [],
        "source_indicators": [
            "metal_coating", "surface_treatment", "electroplating",
        ],
    },
    "inorganic": {
        "hebrew": "יונים עיקריים / מליחות",
        "members": {
            "Chlorides", "Sulfate", "Nitrates", "Sodium",
            "EC", "TDS", "Fluoride",
        },
        "degradation_chain": [],
        "source_indicators": ["general_industry", "agriculture", "sewage"],
    },
    "pfas": {
        "hebrew": "PFAS",
        "members": {
            "PFOA", "PFOS", "GenX", "PFAS_Total",
            "6:2_FTS", "PFHxS", "PFNA", "PFDA",
        },
        "degradation_chain": [],
        "source_indicators": [
            "firefighting_foam", "airport", "military", "power_station",
        ],
    },
    "emerging": {
        "hebrew": "מזהמים מתעוררים",
        "members": set(),
        "degradation_chain": [],
        "source_indicators": [],
    },
    "sewage_markers": {
        "hebrew": "סמני שפכים / פרמצבטיקה",
        "members": {
            "Carbamazepine", "Caffeine", "Sulfamethoxazole",
            "Ibuprofen", "Diclofenac",
        },
        "degradation_chain": [],
        "source_indicators": ["sewage", "hospital", "pharmaceutical"],
    },
}

_PARAM_TO_GROUP: Dict[str, str] = {}
for _group_name, _group_def in CONTAMINANT_GROUPS.items():
    for _member in _group_def["members"]:
        _PARAM_TO_GROUP[_member] = _group_name
        _PARAM_TO_GROUP[_member.lower()] = _group_name
        _PARAM_TO_GROUP[_member.upper()] = _group_name


class ContaminantGrouper:
    """Assigns contaminants to families and computes group-level views."""

    def classify(self, parameter: str) -> Optional[str]:
        """Return the family name for a parameter, or None if unknown."""
        return _PARAM_TO_GROUP.get(parameter) or _PARAM_TO_GROUP.get(parameter.lower())

    def group_parameters(self, parameters: List[str]) -> Dict[str, List[str]]:
        """Partition a list of parameters into families.

        Returns ``{family_name: [param, ...], ...}``.
        Unrecognized parameters are placed under ``"unclassified"``.
        """
        result: Dict[str, List[str]] = {}
        for param in parameters:
            family = self.classify(param) or "unclassified"
            result.setdefault(family, []).append(param)
        return result

    def get_family_members(self, family: str) -> Set[str]:
        """Return the set of known members for a family."""
        group = CONTAMINANT_GROUPS.get(family)
        if group is None:
            return set()
        return set(group["members"])

    def get_degradation_chain(self, family: str) -> List[str]:
        """Return the degradation chain for a family (empty if none)."""
        group = CONTAMINANT_GROUPS.get(family)
        if group is None:
            return []
        return list(group["degradation_chain"])

    def get_source_indicators(self, family: str) -> List[str]:
        """Return industry types associated with a family."""
        group = CONTAMINANT_GROUPS.get(family)
        if group is None:
            return []
        return list(group["source_indicators"])
