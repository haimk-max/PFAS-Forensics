"""contaminant_groups.py - הגדרת קבוצות מזהמים."""

from dataclasses import dataclass


@dataclass
class ContaminantGroup:
    name: str
    compounds: list[str]
    thresholds: dict[str, float]
    unit: str
    description: str = ""


# =============================================================================
# קבוצות מזהמים מוגדרות מראש
# =============================================================================

_BUILTIN_GROUPS: dict[str, ContaminantGroup] = {
    "PFAS": ContaminantGroup(
        name="PFAS",
        description="Per- and polyfluoroalkyl substances - חומרים פר/פולי פלואורואלקיליים",
        compounds=[
            "PFOS", "PFOA", "PFHxS", "PFNA", "PFDA", "PFUnDA", "PFBS", "GenX",
            "PFHxA", "PFHpA", "PFDoA", "PFBA", "ADONA", "6:2FT", "PFESA",
            "PFPeA", "PFHpS", "PFPeS", "PFTDA", "PFUnA",
        ],
        thresholds={
            "PFOS": 0.1,
            "PFOA": 0.1,
            "PFHxS": 0.1,
            "PFNA": 0.1,
            "PFDA": 0.1,
            "PFUnDA": 0.1,
            "PFBS": 0.1,
            "GenX": 0.1,
            "PFHxA": 0.1,
            "PFHpA": 0.1,
            "PFDoA": 0.1,
            "PFBA": 0.1,
            "ADONA": 0.1,
            "6:2FT": 0.1,
            "PFESA": 0.1,
            "PFPeA": 0.1,
            "PFHpS": 0.1,
            "PFPeS": 0.1,
            "PFTDA": 0.1,
            "PFUnA": 0.1,
        },
        unit="µg/L",
    ),
    "BTEX": ContaminantGroup(
        name="BTEX (דלקים)",
        description="Benzene, Toluene, Ethylbenzene, Xylenes - תרכובות דלק",
        compounds=["Benzene", "Toluene", "Ethylbenzene", "Xylene"],
        thresholds={
            "Benzene": 1.0,
            "Toluene": 26.0,
            "Ethylbenzene": 8.0,
            "Xylene": 20.0,
        },
        unit="µg/L",
    ),
    "Chlorinated Solvents": ContaminantGroup(
        name="ממסים כלוריים",
        description="Chlorinated solvents - ממסים כלוריים (TCE, PCE וכו')",
        compounds=["TCE", "PCE", "1,2-DCE", "Vinyl Chloride"],
        thresholds={
            "TCE": 5.0,
            "PCE": 5.0,
            "1,2-DCE": 5.0,
            "Vinyl Chloride": 2.0,
        },
        unit="µg/L",
    ),
    "Heavy Metals": ContaminantGroup(
        name="מתכות כבדות",
        description="Heavy metals - מתכות כבדות",
        compounds=["Pb", "Cd", "Cr", "As", "Hg", "Ni", "Zn"],
        thresholds={
            "Pb": 10.0,
            "Cd": 5.0,
            "Cr": 50.0,
            "As": 10.0,
            "Hg": 1.0,
            "Ni": 20.0,
            "Zn": 5000.0,
        },
        unit="µg/L",
    ),
    "Nitrates": ContaminantGroup(
        name="חנקות",
        description="Nitrates and nitrogen compounds - תרכובות חנקן",
        compounds=["NO3", "NO2", "NH4"],
        thresholds={
            "NO3": 50.0,
            "NO2": 0.5,
            "NH4": 1.5,
        },
        unit="mg/L",
    ),
}


# =============================================================================
# Public API - פונקציות לשימוש מבחוץ
# =============================================================================


def get_group(name: str) -> ContaminantGroup:
    if name not in _BUILTIN_GROUPS:
        available = ", ".join(_BUILTIN_GROUPS.keys())
        raise KeyError(f"קבוצה '{name}' לא נמצאה. קבוצות זמינות: {available}")
    return _BUILTIN_GROUPS[name]


def list_groups() -> list[str]:
    return list(_BUILTIN_GROUPS.keys())


def detect_group(compound_names: list[str]) -> str | None:
    compound_set = {c.upper().strip() for c in compound_names}

    best_match = None
    best_overlap = 0

    for group_name, group in _BUILTIN_GROUPS.items():
        group_compounds = {c.upper() for c in group.compounds}
        overlap = len(compound_set & group_compounds)
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = group_name

    # Require at least 2 matching compounds to declare a match
    if best_overlap >= 2:
        return best_match
    return None
