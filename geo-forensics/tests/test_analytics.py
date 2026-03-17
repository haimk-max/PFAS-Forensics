"""Tests for data_model analytics functions."""

import sys
import os

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.contaminant_groups import get_group, detect_group, list_groups
from src.data_model import process_file, calc_total_concentration, build_fingerprint_matrix


class TestContaminantGroups:
    """Test contaminant group operations."""

    def test_list_groups(self):
        groups = list_groups()
        assert "PFAS" in groups
        assert "BTEX" in groups
        assert len(groups) >= 5

    def test_get_group(self):
        pfas = get_group("PFAS")
        assert pfas.name == "PFAS"
        assert "PFOS" in pfas.compounds
        assert pfas.unit == "µg/L"

    def test_get_unknown_group_raises(self):
        with pytest.raises(KeyError):
            get_group("NonExistent")

    def test_detect_pfas(self):
        result = detect_group(["PFOS", "PFOA", "PFHxS"])
        assert result == "PFAS"

    def test_detect_btex(self):
        result = detect_group(["Benzene", "Toluene", "Xylene"])
        assert result == "BTEX"

    def test_detect_unknown(self):
        result = detect_group(["SomeRandomCompound"])
        assert result is None


class TestFullPipeline:
    """Test the full data processing pipeline with sample data."""

    @pytest.fixture
    def sample_data(self):
        sample_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "sample", "sample_pfas.xlsx"
        )
        if not os.path.exists(sample_path):
            pytest.skip("Sample data not generated yet")
        return process_file(sample_path)

    def test_process_file(self, sample_data):
        df, group = sample_data
        assert len(df) > 0
        assert group.name == "PFAS"
        assert "lat" in df.columns
        assert "lon" in df.columns
        assert df["lat"].notna().all()

    def test_total_concentration(self, sample_data):
        df, group = sample_data
        totals = calc_total_concentration(df, group)
        assert "total_concentration" in totals.columns
        assert len(totals) > 0
        assert totals["total_concentration"].min() >= 0

    def test_fingerprint_matrix(self, sample_data):
        df, group = sample_data
        fp = build_fingerprint_matrix(df, group)
        # Each row should sum to ~100%
        row_sums = fp.sum(axis=1)
        for s in row_sums:
            assert abs(s - 100.0) < 0.1
