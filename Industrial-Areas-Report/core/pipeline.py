"""Pipeline orchestrator — discovers and chains registered plugins."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .contaminant_grouper import ContaminantGrouper
from .contracts import Attribution, FamilyReport, ReportContext
from .pollution_index import compute_group_index, compute_index
from .registry import discover_plugins, get_plugins

log = logging.getLogger(__name__)


class Pipeline:
    """Run the full analysis pipeline for one industrial area + year.

    Phases:
        A. Ingest data from enabled DataSource plugins
        B. Group contaminants into families
        C. For each family, compute pollution index + run ForensicsModule
        D. Run TrendDetector plugins on per-well time series
        E. Run SourceAttributor plugins
        F. Assemble ReportContext and render via ReportSection plugins
    """

    def __init__(self, area_config: Dict, standards: Dict[str, float]):
        self.area_config = area_config
        self.standards = standards
        self.grouper = ContaminantGrouper()
        discover_plugins()

    # ------------------------------------------------------------------
    # Phase A: Data Ingestion
    # ------------------------------------------------------------------

    def ingest(self, area: str) -> pd.DataFrame:
        """Fetch and concatenate data from all enabled DataSource plugins."""
        enabled = set(self.area_config.get("data_sources", []))
        sources = get_plugins("data_source")
        frames: List[pd.DataFrame] = []

        for name, cls in sources.items():
            if enabled and name not in enabled:
                continue
            try:
                src = cls()
                df = src.fetch(area)
                if df is not None and not df.empty:
                    frames.append(df)
                    log.info("Ingested %d rows from %s", len(df), name)
            except Exception as exc:  # noqa: BLE001
                log.warning("DataSource %s failed: %s", name, exc)

        if not frames:
            return pd.DataFrame(
                columns=["date", "borehole_id", "parameter", "value", "unit"]
            )
        return pd.concat(frames, ignore_index=True)

    # ------------------------------------------------------------------
    # Phase B+C: Group contaminants, compute indices, run forensics
    # ------------------------------------------------------------------

    def analyze_families(
        self, data: pd.DataFrame
    ) -> List[FamilyReport]:
        """Group contaminants and produce a FamilyReport per active family."""
        if data.empty:
            return []

        params = data["parameter"].unique().tolist()
        grouped = self.grouper.group_parameters(params)
        reports: List[FamilyReport] = []

        for family, members in grouped.items():
            if family == "unclassified":
                continue

            family_data = data[data["parameter"].isin(members)]
            member_indices: Dict[str, int] = {}
            for param in members:
                param_vals = family_data[family_data["parameter"] == param]["value"]
                if param_vals.empty:
                    continue
                std = self.standards.get(param)
                if std and std > 0:
                    member_indices[param] = compute_index(
                        float(param_vals.max()), std
                    )

            dominant = max(member_indices, key=member_indices.get) if member_indices else ""
            wells = family_data["borehole_id"].unique().tolist() if "borehole_id" in family_data.columns else []

            report = FamilyReport(
                family=family,
                max_index=compute_group_index(member_indices),
                dominant_contaminant=dominant,
                member_indices=member_indices,
                wells_affected=wells,
            )

            # Run forensics plugins for this family
            report.fingerprint = self._run_forensics(family, family_data)

            reports.append(report)

        reports.sort(key=lambda r: r.max_index, reverse=True)
        return reports

    def _run_forensics(
        self, family: str, data: pd.DataFrame
    ) -> Optional["FingerprintResult"]:
        """Run the first matching ForensicsModule plugin for *family*."""
        enabled = set(self.area_config.get("forensics", []))
        forensics = get_plugins("forensics")

        for name, cls in forensics.items():
            if enabled and name not in enabled:
                continue
            try:
                mod = cls()
                if getattr(mod, "family", None) == family:
                    return mod.fingerprint(data)
            except Exception as exc:  # noqa: BLE001
                log.warning("Forensics %s failed: %s", name, exc)
        return None

    # ------------------------------------------------------------------
    # Phase D: Trend Detection
    # ------------------------------------------------------------------

    def detect_trends(
        self, data: pd.DataFrame, reports: List[FamilyReport]
    ) -> None:
        """Run enabled TrendDetector plugins and attach results to reports."""
        enabled = set(self.area_config.get("trend_detectors", []))
        detectors = get_plugins("trend_detector")

        for report in reports:
            family_data = data[
                data["parameter"].isin(
                    self.grouper.get_family_members(report.family)
                )
            ]
            if family_data.empty or "date" not in family_data.columns:
                continue

            agg = (
                family_data.groupby("date")["value"]
                .max()
                .sort_index()
            )
            if len(agg) < 3:
                continue

            for name, cls in detectors.items():
                if enabled and name not in enabled:
                    continue
                try:
                    det = cls()
                    result = det.detect(agg, agg.index)
                    report.trend = result
                    break  # use first successful detector
                except Exception as exc:  # noqa: BLE001
                    log.warning("TrendDetector %s failed: %s", name, exc)

    # ------------------------------------------------------------------
    # Phase E: Source Attribution
    # ------------------------------------------------------------------

    def attribute_sources(
        self,
        reports: List[FamilyReport],
        candidates: List[Dict],
        flow_direction_deg: Optional[float] = None,
    ) -> List[Attribution]:
        """Run enabled SourceAttributor plugins."""
        enabled = set(self.area_config.get("source_attributors", []))
        attributors = get_plugins("source_attributor")
        all_attributions: List[Attribution] = []

        for name, cls in attributors.items():
            if enabled and name not in enabled:
                continue
            try:
                attr = cls()
                for report in reports:
                    results = attr.attribute(report, candidates, flow_direction_deg)
                    all_attributions.extend(results)
            except Exception as exc:  # noqa: BLE001
                log.warning("SourceAttributor %s failed: %s", name, exc)

        all_attributions.sort(key=lambda a: a.score, reverse=True)
        return all_attributions

    # ------------------------------------------------------------------
    # Phase F: Report Assembly
    # ------------------------------------------------------------------

    def render_report(self, ctx: ReportContext) -> str:
        """Render all ReportSection plugins in order, return combined HTML."""
        enabled = self.area_config.get("report_sections", ["*"])
        sections = get_plugins("report_section")

        instances = []
        for name, cls in sections.items():
            if "*" not in enabled and name not in enabled:
                continue
            instances.append(cls())

        instances.sort(key=lambda s: getattr(s, "order", 999))

        parts = []
        for section in instances:
            try:
                html = section.render(ctx)
                if html:
                    parts.append(html)
            except Exception as exc:  # noqa: BLE001
                log.warning("ReportSection %s failed: %s", getattr(section, "section_id", "?"), exc)

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Full run
    # ------------------------------------------------------------------

    def run(
        self,
        area: str,
        year: int,
        candidates: Optional[List[Dict]] = None,
        flow_direction_deg: Optional[float] = None,
    ) -> ReportContext:
        """Execute the complete pipeline for *area* / *year*."""
        log.info("Pipeline: starting %s %d", area, year)

        data = self.ingest(area)
        log.info("Pipeline: ingested %d rows", len(data))

        family_reports = self.analyze_families(data)
        log.info("Pipeline: %d families analyzed", len(family_reports))

        self.detect_trends(data, family_reports)

        attributions = self.attribute_sources(
            family_reports, candidates or [], flow_direction_deg
        )
        log.info("Pipeline: %d attributions", len(attributions))

        ctx = ReportContext(
            area_name=area,
            area_hebrew=self.area_config.get("hebrew", area),
            year=year,
            family_reports=family_reports,
            attributions=attributions,
            flow_direction_deg=flow_direction_deg,
        )

        report_html = self.render_report(ctx)
        log.info("Pipeline: report rendered (%d chars)", len(report_html))

        return ctx
