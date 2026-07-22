"""flow_model.py — Flow-direction providers (surface & groundwater).

Provider-interface principle: every context layer enters through a narrow
interface carrying a quality tier, so today's assumption can be swapped for a
DEM derivation or organizational-GIS feed without touching consumers.

Quality tiers (ordered, weakest first):
    ASSUMED        — user-declared working assumption (no measurements)
    DERIVED_DEM    — derived from a terrain model (surface water only)
    DERIVED_HEADS  — derived from measured groundwater heads

Consumers (attribution) must cap hydrological confidence according to the
tier — an ASSUMED direction can make a candidate "עקבי" but never "מאושש".
"""

from dataclasses import dataclass
import math

ASSUMED = "assumed"
DERIVED_DEM = "derived_dem"
DERIVED_HEADS = "derived_heads"

_TIER_LABELS_HE = {
    ASSUMED: "הנחת עבודה — לא נגזר ממדידות",
    DERIVED_DEM: "נגזר ממודל גבהים (עילי)",
    DERIVED_HEADS: "נגזר ממפלסים מדודים",
}


@dataclass
class UniformFlowAssumption:
    """Uniform regional flow in a single declared direction.

    direction_deg: azimuth the water flows TOWARD, degrees clockwise from
    grid north (east→west flow = 270). Applies to both surface water and
    groundwater until replaced by per-domain providers.

    tolerance_deg: half-angle of the upgradient sector. A source is
    "upgradient" of a station if the bearing from station to source falls
    within ±tolerance of the up-flow direction. Wide default reflects the
    coarseness of a uniform assumption.
    """

    direction_deg: float = 270.0
    tolerance_deg: float = 60.0
    tier: str = ASSUMED
    declared_by: str = ""
    declared_on: str = ""

    @property
    def tier_label_he(self) -> str:
        return _TIER_LABELS_HE.get(self.tier, self.tier)

    def describe_he(self) -> str:
        compass = _azimuth_to_hebrew(self.direction_deg)
        src = f' (הוצהר ע"י {self.declared_by}, {self.declared_on})' if self.declared_by else ""
        return f"זרימה כללית {compass} · {self.tier_label_he}{src}"

    def upgradient_of(self, station_xy: tuple[float, float],
                      source_xy: tuple[float, float]) -> bool:
        """Is source upgradient of station under this flow field?"""
        dx = source_xy[0] - station_xy[0]
        dy = source_xy[1] - station_xy[1]
        if dx == 0 and dy == 0:
            return False
        bearing = math.degrees(math.atan2(dx, dy)) % 360  # from station to source
        up_direction = (self.direction_deg + 180) % 360    # where flow comes FROM
        diff = abs((bearing - up_direction + 180) % 360 - 180)
        return diff <= self.tolerance_deg

    def downgradient_distance_m(self, station_xy: tuple[float, float],
                                source_xy: tuple[float, float]) -> float:
        """Distance from source to station projected on the flow axis (m).
        Positive = station lies down-flow of the source."""
        dx = station_xy[0] - source_xy[0]
        dy = station_xy[1] - source_xy[1]
        rad = math.radians(self.direction_deg)
        return dx * math.sin(rad) + dy * math.cos(rad)


def _azimuth_to_hebrew(deg: float) -> str:
    names = ["מצפון לדרום", "מצפון-מזרח לדרום-מערב", "ממזרח למערב",
             "מדרום-מזרח לצפון-מערב", "מדרום לצפון", "מדרום-מערב לצפון-מזרח",
             "ממערב למזרח", "מצפון-מערב לדרום-מזרח"]
    idx = round(((deg % 360) - 180) % 360 / 45) % 8
    # direction_deg is where flow goes TOWARD; 270 → "ממזרח למערב"
    mapping = {0: "מדרום לצפון", 45: "מדרום-מערב לצפון-מזרח", 90: "ממערב למזרח",
               135: "מצפון-מערב לדרום-מזרח", 180: "מצפון לדרום",
               225: "מצפון-מזרח לדרום-מערב", 270: "ממזרח למערב",
               315: "מדרום-מזרח לצפון-מערב"}
    nearest = min(mapping, key=lambda k: abs((deg - k + 180) % 360 - 180))
    return mapping[nearest]
