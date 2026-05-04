"""Six extension-point Protocols that every plugin must implement."""

from __future__ import annotations

from typing import Dict, List, Optional, Protocol, runtime_checkable

import pandas as pd

from .contracts import (
    Attribution,
    FamilyReport,
    FingerprintResult,
    ReportContext,
    TimeRange,
    TrendResult,
)


@runtime_checkable
class DataSource(Protocol):
    """Fetch raw measurements from an external source."""

    name: str

    def fetch(
        self, area: str, time_range: Optional[TimeRange] = None
    ) -> pd.DataFrame:
        """Return DataFrame with columns: date, borehole_id, parameter, value, unit."""
        ...


@runtime_checkable
class ContaminantFamilyAnalyzer(Protocol):
    """Per-family group analysis (index, dominant contaminant)."""

    family: str

    def applies_to(self, contaminants: List[str]) -> bool:
        ...

    def analyze(
        self, data: pd.DataFrame, standards: Dict[str, float]
    ) -> FamilyReport:
        ...


@runtime_checkable
class ForensicsModule(Protocol):
    """Chemical fingerprinting per well for a specific contaminant family."""

    family: str
    version: str

    def fingerprint(self, well_data: pd.DataFrame) -> FingerprintResult:
        ...


@runtime_checkable
class TrendDetector(Protocol):
    """Detect trend type in a single time series."""

    name: str

    def detect(
        self, series: pd.Series, dates: Optional[pd.Series] = None
    ) -> TrendResult:
        ...


@runtime_checkable
class SourceAttributor(Protocol):
    """Rank candidate pollution sources with cautious phrasing."""

    def attribute(
        self,
        family_report: FamilyReport,
        candidates: List[Dict],
        flow_direction_deg: Optional[float] = None,
    ) -> List[Attribution]:
        ...


@runtime_checkable
class ReportSection(Protocol):
    """Render one HTML section of the final report."""

    section_id: str
    order: int

    def render(self, ctx: ReportContext) -> str:
        ...
