"""Tests for core infrastructure: pollution index, contaminant grouper, registry."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pollution_index import compute_index, compute_group_index, index_label
from core.contaminant_grouper import ContaminantGrouper
from core.contracts import TrendResult, Attribution, FingerprintResult
from core.registry import register_plugin, get_plugins, get_plugin, clear_registry


class TestPollutionIndex:

    def test_background(self):
        assert compute_index(1.0, 5.0) == 0  # ratio 0.2

    def test_traces(self):
        assert compute_index(2.0, 5.0) == 1  # ratio 0.4

    def test_approaching_standard(self):
        assert compute_index(4.0, 5.0) == 2  # ratio 0.8

    def test_mild_exceedance(self):
        assert compute_index(8.0, 5.0) == 3  # ratio 1.6

    def test_significant(self):
        assert compute_index(20.0, 5.0) == 4  # ratio 4.0

    def test_severe(self):
        assert compute_index(50.0, 5.0) == 5  # ratio 10.0

    def test_very_severe(self):
        assert compute_index(150.0, 5.0) == 6  # ratio 30.0

    def test_extreme(self):
        assert compute_index(300.0, 5.0) == 7  # ratio 60.0

    def test_critical(self):
        assert compute_index(500.0, 5.0) == 8  # ratio 100.0

    def test_raanana_tce_250(self):
        """Raanana TCE: 250 μg/L vs standard 5 μg/L → ratio 50 → index 6."""
        assert compute_index(250.0, 5.0) == 6

    def test_raanana_tce_310(self):
        """Raanana TCE peak: 310 μg/L vs standard 5 μg/L → ratio 62 → index 7."""
        assert compute_index(310.0, 5.0) == 7

    def test_zero_value(self):
        assert compute_index(0.0, 5.0) == 0

    def test_negative_value(self):
        assert compute_index(-1.0, 5.0) == 0

    def test_invalid_standard(self):
        with pytest.raises(ValueError):
            compute_index(10.0, 0.0)

    def test_group_index(self):
        indices = {"TCE": 7, "PCE": 4, "cis-1,2-DCE": 2}
        assert compute_group_index(indices) == 7

    def test_group_index_empty(self):
        assert compute_group_index({}) == 0

    def test_label_hebrew(self):
        assert index_label(0) == "רקע"
        assert index_label(8) == "זיהום קריטי"

    def test_label_english(self):
        assert index_label(5, hebrew=False) == "severe"


class TestContaminantGrouper:

    def setup_method(self):
        self.grouper = ContaminantGrouper()

    def test_classify_tce(self):
        assert self.grouper.classify("TCE") == "chlorinated_solvents"

    def test_classify_benzene(self):
        assert self.grouper.classify("Benzene") == "fuels"

    def test_classify_pfos(self):
        assert self.grouper.classify("PFOS") == "pfas"

    def test_classify_chromium(self):
        assert self.grouper.classify("Chromium") == "metals"

    def test_classify_chlorides(self):
        assert self.grouper.classify("Chlorides") == "inorganic"

    def test_classify_unknown(self):
        assert self.grouper.classify("UnknownChemical") is None

    def test_case_insensitive(self):
        assert self.grouper.classify("tce") == "chlorinated_solvents"

    def test_group_parameters(self):
        params = ["TCE", "PCE", "Benzene", "PFOS", "UnknownX"]
        grouped = self.grouper.group_parameters(params)
        assert "chlorinated_solvents" in grouped
        assert "TCE" in grouped["chlorinated_solvents"]
        assert "PCE" in grouped["chlorinated_solvents"]
        assert "fuels" in grouped
        assert "pfas" in grouped
        assert "unclassified" in grouped

    def test_degradation_chain(self):
        chain = self.grouper.get_degradation_chain("chlorinated_solvents")
        assert chain == ["PCE", "TCE", "cis-1,2-DCE", "Vinyl_Chloride"]

    def test_source_indicators(self):
        indicators = self.grouper.get_source_indicators("fuels")
        assert "gas_station" in indicators


class TestContracts:

    def test_trend_result_valid(self):
        t = TrendResult(trend_type="rising", p_value=0.01, slope=0.5)
        assert t.trend_type == "rising"

    def test_trend_result_invalid(self):
        with pytest.raises(ValueError):
            TrendResult(trend_type="invalid_type")

    def test_attribution_valid(self):
        a = Attribution(
            facility_id="F1", facility_name="Test", score=0.8,
            tier=1, cautious_phrase="מועמד ליבה",
        )
        assert a.score == 0.8

    def test_attribution_invalid_phrase(self):
        with pytest.raises(ValueError):
            Attribution(
                facility_id="F1", facility_name="Test", score=0.5,
                tier=2, cautious_phrase="the source",
            )

    def test_fingerprint_result(self):
        f = FingerprintResult(
            well_id="W1", dominant_group="chlorinated_solvents",
            leading_contaminant="TCE",
            secondary_contaminants=["PCE"],
            relative_ratios={"TCE/PCE": 5.2},
        )
        assert f.leading_contaminant == "TCE"


class TestRegistry:

    def setup_method(self):
        clear_registry()

    def test_register_and_get(self):
        @register_plugin("forensics", name="test_plugin")
        class TestPlugin:
            pass

        assert get_plugin("forensics", "test_plugin") is TestPlugin

    def test_invalid_category(self):
        with pytest.raises(ValueError):
            @register_plugin("nonexistent_category")
            class Bad:
                pass

    def test_get_plugins(self):
        @register_plugin("trend_detector", name="td1")
        class TD1:
            pass

        @register_plugin("trend_detector", name="td2")
        class TD2:
            pass

        plugins = get_plugins("trend_detector")
        assert len(plugins) == 2
        assert "td1" in plugins
        assert "td2" in plugins

    def test_get_nonexistent(self):
        assert get_plugin("forensics", "nonexistent") is None
