"""Typed data contracts for all inter-module data flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple


@dataclass
class TimeRange:
    start: Optional[datetime] = None
    end: Optional[datetime] = None


@dataclass
class BoreholeReading:
    date: datetime
    borehole_id: str
    parameter: str
    value: float
    unit: str
    industrial_area: str = ""
    lab: str = ""


@dataclass
class TrendResult:
    trend_type: str  # rising/falling/stable/volatile/pulse/re_escalation/new_appearance
    p_value: Optional[float] = None
    slope: Optional[float] = None
    confidence: float = 0.0
    method: str = ""
    details: Dict = field(default_factory=dict)

    VALID_TYPES = frozenset({
        "rising", "falling", "stable", "volatile",
        "pulse", "re_escalation", "new_appearance",
        "insufficient_data",
    })

    def __post_init__(self):
        if self.trend_type not in self.VALID_TYPES:
            raise ValueError(
                f"Invalid trend_type '{self.trend_type}'. "
                f"Must be one of: {sorted(self.VALID_TYPES)}"
            )


@dataclass
class FingerprintResult:
    well_id: str
    dominant_group: str
    leading_contaminant: str
    secondary_contaminants: List[str] = field(default_factory=list)
    degradation_products: List[str] = field(default_factory=list)
    relative_ratios: Dict[str, float] = field(default_factory=dict)
    stability: str = "unknown"  # stable / shifting / new
    years_compared: List[str] = field(default_factory=list)


@dataclass
class FamilyReport:
    family: str
    max_index: int = 0
    dominant_contaminant: str = ""
    member_indices: Dict[str, int] = field(default_factory=dict)
    trend: Optional[TrendResult] = None
    fingerprint: Optional[FingerprintResult] = None
    wells_affected: List[str] = field(default_factory=list)


@dataclass
class Attribution:
    facility_id: str
    facility_name: str
    score: float  # 0.0–1.0
    tier: int  # 1–5
    cautious_phrase: str
    matched_families: List[str] = field(default_factory=list)
    evidence: Dict = field(default_factory=dict)

    VALID_PHRASES = frozenset({
        "מועמד ליבה",
        "מועמד משני",
        "רקע מקומי",
        "לא תומך בפלומה המרכזית",
        "מתאים למסלול נפרד",
    })

    def __post_init__(self):
        if self.cautious_phrase not in self.VALID_PHRASES:
            raise ValueError(
                f"Invalid cautious_phrase '{self.cautious_phrase}'. "
                f"Must be one of: {self.VALID_PHRASES}"
            )


@dataclass
class ReportContext:
    area_name: str
    area_hebrew: str
    year: int
    family_reports: List[FamilyReport] = field(default_factory=list)
    attributions: List[Attribution] = field(default_factory=list)
    previous_context: Optional[Dict] = None
    flow_direction_deg: Optional[float] = None
    boreholes: List[Dict] = field(default_factory=list)
    map_center: Tuple[float, float] = (32.19, 34.87)
