"""DataSource plugin wrapping the existing Excel importer."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from core.contracts import TimeRange
from core.registry import register_plugin


@register_plugin("data_source", name="excel")
class ExcelPlugin:
    """Thin wrapper that adapts ExcelDataSource to the DataSource protocol."""

    name: str = "excel"

    def __init__(self, excel_path: Optional[Path] = None) -> None:
        self._excel_path = excel_path
        self._source = None

    def _get_source(self):
        if self._source is None:
            from data_sources.excel_importer import ExcelDataSource
            self._source = ExcelDataSource(excel_file=self._excel_path)
        return self._source

    def fetch(
        self, area: str, time_range: Optional[TimeRange] = None
    ) -> pd.DataFrame:
        df = self._get_source().load_water_quality_data()
        if df.empty:
            return df

        if "industrial_area" in df.columns:
            df = df[df["industrial_area"].str.lower() == area.lower()]

        if time_range and "date" in df.columns:
            if time_range.start:
                df = df[df["date"] >= time_range.start]
            if time_range.end:
                df = df[df["date"] <= time_range.end]

        return df
