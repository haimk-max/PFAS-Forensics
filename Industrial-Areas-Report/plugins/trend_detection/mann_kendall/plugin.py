"""Mann-Kendall trend detection plugin.

Uses the pymannkendall library to perform a non-parametric monotonic trend
test on groundwater contaminant time-series.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from core.contracts import TrendResult
from core.registry import register_plugin

log = logging.getLogger(__name__)

try:
    import pymannkendall as mk
    _HAS_MK = True
except ImportError:
    _HAS_MK = False
    log.warning("pymannkendall not installed — mann_kendall plugin will return insufficient_data")


@register_plugin("trend_detector", name="mann_kendall")
class MannKendallTrendDetector:
    """Detect monotonic trends via the Mann-Kendall statistical test."""

    name: str = "mann_kendall"

    def detect(
        self,
        series: pd.Series,
        dates: Optional[pd.Series] = None,
    ) -> TrendResult:
        if not _HAS_MK:
            return TrendResult(
                trend_type="insufficient_data",
                method="mann_kendall",
                details={"warning": "pymannkendall library is not installed"},
            )

        values = series.dropna()
        if len(values) < 3:
            return TrendResult(
                trend_type="insufficient_data",
                method="mann_kendall",
                details={"n": len(values)},
            )

        result = mk.original_test(values)
        # result fields: trend, h, p, z, Tau, s, var_s, slope, intercept

        p_value: float = result.p
        slope: float = result.slope

        # Coefficient of variation (guard against zero mean)
        mean = values.mean()
        cov = float(values.std() / mean) if mean != 0 else 0.0

        if p_value < 0.05 and slope > 0:
            trend_type = "rising"
        elif p_value < 0.05 and slope < 0:
            trend_type = "falling"
        elif cov < 0.3:
            trend_type = "stable"
        else:
            trend_type = "volatile"

        return TrendResult(
            trend_type=trend_type,
            p_value=p_value,
            slope=slope,
            confidence=1.0 - p_value,
            method="mann_kendall",
            details={
                "tau": result.Tau,
                "z": result.z,
                "s": result.s,
                "intercept": result.intercept,
                "cov": cov,
            },
        )
