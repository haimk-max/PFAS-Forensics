"""Chlorinated solvents forensics plugin.

Performs chemical fingerprinting on chlorinated solvent detections
per well: identifies leading contaminant, degradation chain products,
and inter-compound ratios useful for plume distinction.
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from core.contracts import FingerprintResult
from core.registry import register_plugin

# Chlorinated solvent compounds tracked by this module.
CHLORINATED_COMPOUNDS: List[str] = [
    "PCE",
    "TCE",
    "cis-1,2-DCE",
    "trans-1,2-DCE",
    "1,1-DCE",
    "Vinyl_Chloride",
    "1,1,1-TCA",
]

# Sequential reductive dechlorination chain (parent → daughter).
# Each tuple is (parent, daughter).
DEGRADATION_CHAIN: List[tuple[str, str]] = [
    ("PCE", "TCE"),
    ("TCE", "cis-1,2-DCE"),
    ("cis-1,2-DCE", "Vinyl_Chloride"),
]

# Minimum value to consider a compound "detected" (above typical MDL).
DETECTION_THRESHOLD: float = 0.1  # µg/L


@register_plugin("forensics", name="chlorinated")
class ChlorinatedForensics:
    """Chemical fingerprinting for the chlorinated-solvents family."""

    family: str = "chlorinated_solvents"
    version: str = "1.0"

    def fingerprint(self, well_data: pd.DataFrame) -> FingerprintResult:
        """Fingerprint a single well's chlorinated solvent profile.

        Parameters
        ----------
        well_data : pd.DataFrame
            Must contain columns: ``date``, ``borehole_id``,
            ``parameter``, ``value``.

        Returns
        -------
        FingerprintResult
        """
        # --- 1. Resolve well identifier -----------------------------------
        well_id = str(well_data["borehole_id"].iloc[0])

        # --- 2. Filter to chlorinated compounds only ----------------------
        mask = well_data["parameter"].isin(CHLORINATED_COMPOUNDS)
        chlor = well_data.loc[mask].copy()

        if chlor.empty:
            return FingerprintResult(
                well_id=well_id,
                dominant_group=self.family,
                leading_contaminant="none",
                stability="unknown",
            )

        # --- 3. Compute peak (max) concentration per compound -------------
        peak: Dict[str, float] = (
            chlor.groupby("parameter")["value"].max().to_dict()
        )

        # Keep only compounds above detection threshold.
        detected = {k: v for k, v in peak.items() if v >= DETECTION_THRESHOLD}

        if not detected:
            return FingerprintResult(
                well_id=well_id,
                dominant_group=self.family,
                leading_contaminant="below_detection",
                stability="unknown",
            )

        # --- 4. Leading contaminant (highest peak) ------------------------
        leading = max(detected, key=detected.get)  # type: ignore[arg-type]

        # --- 5. Secondary contaminants ------------------------------------
        secondaries = sorted(
            [c for c in detected if c != leading],
            key=lambda c: detected[c],
            reverse=True,
        )

        # --- 6. Degradation products present in the data ------------------
        degradation_products: List[str] = []
        for _parent, daughter in DEGRADATION_CHAIN:
            if daughter in detected:
                degradation_products.append(daughter)

        # --- 7. Relative ratios between detected pairs --------------------
        ratios: Dict[str, float] = {}
        detected_names = sorted(detected.keys())
        for i, numerator in enumerate(detected_names):
            for denominator in detected_names[i + 1 :]:
                denom_val = detected[denominator]
                if denom_val > 0:
                    ratio = round(detected[numerator] / denom_val, 3)
                    ratios[f"{numerator}/{denominator}"] = ratio

        # --- 8. Build result ---------------------------------------------
        return FingerprintResult(
            well_id=well_id,
            dominant_group=self.family,
            leading_contaminant=leading,
            secondary_contaminants=secondaries,
            degradation_products=degradation_products,
            relative_ratios=ratios,
            stability="unknown",
        )
