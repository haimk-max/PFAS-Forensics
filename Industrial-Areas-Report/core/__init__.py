"""Core infrastructure: interfaces, contracts, registry, pipeline."""

from .interfaces import (
    DataSource,
    ContaminantFamilyAnalyzer,
    ForensicsModule,
    TrendDetector,
    SourceAttributor,
    ReportSection,
)
from .contracts import (
    TimeRange,
    BoreholeReading,
    FingerprintResult,
    TrendResult,
    FamilyReport,
    Attribution,
    ReportContext,
)
from .registry import register_plugin, discover_plugins, get_plugins, get_plugin
