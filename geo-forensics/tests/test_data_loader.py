"""Tests for data_loader module."""

import sys
import os

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data_loader import normalize_columns, validate_schema, clean_data, _parse_concentration


class TestNormalizeColumns:
    """Test Hebrew column name mapping."""

    def test_hebrew_columns(self):
        df = pd.DataFrame({"שם תחנה": ["A"], "X (ITM)": [200000], "Y (ITM)": [660000]})
        result = normalize_columns(df)
        assert "station_name" in result.columns
        assert "x_itm" in result.columns
        assert "y_itm" in result.columns

    def test_english_columns_passthrough(self):
        df = pd.DataFrame({"station_name": ["A"], "x_itm": [200000]})
        result = normalize_columns(df)
        assert "station_name" in result.columns

    def test_mixed_columns(self):
        df = pd.DataFrame({"שם תחנה": ["A"], "x_itm": [200000]})
        result = normalize_columns(df)
        assert "station_name" in result.columns
        assert "x_itm" in result.columns


class TestValidateSchema:
    """Test schema validation."""

    def test_valid_schema(self):
        df = pd.DataFrame({
            "station_name": ["A"],
            "x_itm": [200000],
            "y_itm": [660000],
            "sample_date": ["2024-01-01"],
            "compound": ["PFOS"],
            "concentration": [0.5],
        })
        is_valid, missing = validate_schema(df)
        assert is_valid is True
        assert missing == []

    def test_missing_columns(self):
        df = pd.DataFrame({"station_name": ["A"], "x_itm": [200000]})
        is_valid, missing = validate_schema(df)
        assert is_valid is False
        assert "y_itm" in missing
        assert "compound" in missing


class TestParseConcentration:
    """Test concentration parsing including LOD handling."""

    def test_normal_number(self):
        assert _parse_concentration(0.5) == 0.5

    def test_string_number(self):
        assert _parse_concentration("1.23") == 1.23

    def test_below_lod(self):
        assert _parse_concentration("<0.01") == 0.0

    def test_not_detected(self):
        assert _parse_concentration("N.D.") == 0.0
        assert _parse_concentration("ND") == 0.0

    def test_none(self):
        assert _parse_concentration(None) is None

    def test_invalid_string(self):
        assert _parse_concentration("abc") is None


class TestCleanData:
    """Test data cleaning."""

    def test_date_parsing(self):
        df = pd.DataFrame({"sample_date": ["15/03/2024"], "concentration": [0.5]})
        result = clean_data(df)
        assert pd.api.types.is_datetime64_any_dtype(result["sample_date"])

    def test_concentration_cleaning(self):
        df = pd.DataFrame({"concentration": ["<0.01", "0.5", "N.D.", "1.2"]})
        result = clean_data(df)
        assert result["concentration"].tolist() == [0.0, 0.5, 0.0, 1.2]
