"""DataSource plugin wrapping the existing Water Authority connector."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from core.contracts import TimeRange
from core.registry import register_plugin


@register_plugin("data_source", name="water_authority")
class WaterAuthorityPlugin:
    """Thin wrapper that adapts WaterAuthorityDataSource to the DataSource protocol."""

    name: str = "water_authority"

    def __init__(self, api_url: str = "https://data.gov.il") -> None:
        self._api_url = api_url
        self._source = None

    def _get_source(self):
        if self._source is None:
            from data_sources.water_authority import WaterAuthorityDataSource
            self._source = WaterAuthorityDataSource(api_url=self._api_url)
        return self._source

    def fetch(
        self, area: str, time_range: Optional[TimeRange] = None
    ) -> pd.DataFrame:
        start = time_range.start.strftime("%Y-%m-%d") if time_range and time_range.start else None
        end = time_range.end.strftime("%Y-%m-%d") if time_range and time_range.end else None
        return self._get_source().get_borehole_data(
            industrial_area=area,
            start_date=start,
            end_date=end,
        )
