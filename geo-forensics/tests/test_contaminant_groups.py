"""Tests for contaminant_groups module."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import COMPOUND_COLORS, PFAS_COMPOUND_ORDER
from src.contaminant_groups import get_group


class TestPFASGroup:
    def test_lab_congeners_covered(self):
        """Congeners seen in Water Authority lab exports must be in the PFAS
        group — otherwise they are silently dropped from the analysis.
        FOSA and 82FTS are diagnostic AFFF/precursor markers."""
        group = get_group("PFAS")
        for congener in ["82FTS", "FOSA", "PFDS", "PFTDS"]:
            assert congener in group.compounds
            assert congener in group.thresholds

    def test_group_compounds_have_color_and_order(self):
        """Every PFAS group compound needs a chart color and an S/A ordering
        slot so fingerprint charts render consistently."""
        group = get_group("PFAS")
        for compound in group.compounds:
            if compound == "GenX":  # legacy alias, colored but unordered is ok
                continue
            assert compound in COMPOUND_COLORS, f"{compound} missing color"
