"""Tests for flow_model, source_profiles and attribution modules."""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.flow_model import ASSUMED, UniformFlowAssumption
from src.source_profiles import PROFILES, marker_flags, match_profiles


class TestUniformFlow:
    """East→west flow: upgradient = east (within tolerance sector)."""

    flow = UniformFlowAssumption(direction_deg=270, tolerance_deg=60)

    def test_source_due_east_is_upgradient(self):
        assert self.flow.upgradient_of((200000, 720000), (204000, 720000))

    def test_source_due_west_is_not_upgradient(self):
        assert not self.flow.upgradient_of((200000, 720000), (196000, 720000))

    def test_source_due_north_is_not_upgradient(self):
        assert not self.flow.upgradient_of((200000, 720000), (200000, 724000))

    def test_downgradient_distance_sign(self):
        # station 4km west of source → positive down-flow distance
        d = self.flow.downgradient_distance_m((196000, 720000), (200000, 720000))
        assert d == pytest.approx(4000, abs=1)


class TestSourceProfiles:
    def test_synthetic_afff_station_matches_afff(self):
        """A PFOS+PFHxS-dominant fingerprint must rank an AFFF-ECF profile
        first — the core promise of the matching."""
        fp = pd.DataFrame(
            [{"PFOS": 45, "PFHxS": 20, "PFBS": 8, "PFHxA": 10, "PFOA": 9,
              "PFPeA": 4, "PFBA": 4}],
            index=["synthetic_afff"],
        ).fillna(0)
        m = match_profiles(fp, top_n=1)
        assert m.iloc[0]["profile_key"].startswith("afff_ecf")

    def test_synthetic_wwtp_station_matches_wwtp(self):
        fp = pd.DataFrame(
            [{"PFOA": 22, "PFHxA": 18, "PFBA": 15, "PFPeA": 13, "PFBS": 10,
              "PFOS": 8, "PFHpA": 8, "PFNA": 3, "PFDA": 3}],
            index=["synthetic_wwtp"],
        ).fillna(0)
        m = match_profiles(fp, top_n=1)
        assert m.iloc[0]["profile_key"] == "wwtp_effluent"

    def test_precursor_flag_requires_detection(self):
        df = pd.DataFrame({
            "station_name": ["A", "A", "B", "B"],
            "compound": ["FOSA", "PFOS", "FOSA", "PFOS"],
            "concentration": [0.01, 0.1, 0.0, 0.1],
        })
        flags = marker_flags(df)
        flagged = set(flags["station"])
        a_flags = " ".join(flags[flags["station"] == "A"]["flags"].iloc[0])
        assert "קדם-חומרים" in a_flags
        if "B" in flagged:
            b_flags = " ".join(flags[flags["station"] == "B"]["flags"].iloc[0])
            assert "קדם-חומרים" not in b_flags

    def test_all_profiles_reference_known_style_compounds(self):
        """Profile weights must use compound symbols, non-empty, positive."""
        for p in PROFILES:
            assert p.weights and all(w > 0 for w in p.weights.values())
            assert p.name_he


class TestAttributionTierCap:
    def test_assumed_flow_caps_tier(self, tmp_path):
        """With all three axes present but ASSUMED flow, the tier must stay
        'מועמד משני' — never 'מועמד ליבה' (governance: assumption ≠ measurement)."""
        import json

        from src import attribution

        region_dir = tmp_path / "test_region"
        region_dir.mkdir()
        (region_dir / "region.json").write_text(json.dumps({
            "name": "test_region", "crs": "EPSG:2039",
            "measurement_file": "x.xlsx",
            "flow": {"groundwater": {"direction_deg": 270, "tier": "assumed"},
                     "surface": {"direction_deg": 270, "tier": "assumed"}},
            "layers": [{"path": "sources.geojson", "kind": "potential_sources",
                        "quality": "test"}],
        }), encoding="utf-8")
        (region_dir / "sources.geojson").write_text(json.dumps({
            "type": "FeatureCollection",
            "features": [{"type": "Feature",
                          "geometry": {"type": "Point", "coordinates": [35, 32.5]},
                          "properties": {"id": "s1", "name_he": "אתר בדיקה",
                                         "itm": [204000, 720000],
                                         "kind": "test",
                                         "expected_profiles": ["afff_ecf_weathered", "afff_ecf_fresh"],
                                         "emission_evidence": ["עדות"],
                                         "evidence_tier": "user_testimony"}}],
        }), encoding="utf-8")

        monkey_regions = str(tmp_path)
        old = attribution.REGIONS_DIR
        attribution.REGIONS_DIR = monkey_regions
        try:
            region = attribution.load_region("test_region")
            df = pd.DataFrame({
                "station_name": ["W1"], "compound": ["PFOS"], "concentration": [0.5],
            })
            fp = pd.DataFrame(
                [{"PFOS": 50, "PFHxS": 20, "PFHxA": 15, "PFOA": 15}], index=["W1"]
            )
            max_event = pd.DataFrame([{
                "station_name": "W1", "total_concentration": 0.5,
                "x_itm": 196000, "y_itm": 720000,
            }])
            res = attribution.evaluate_candidates(df, fp, max_event, region)
            assert len(res) == 1
            assert "ליבה" not in res[0]["tier"]
            assert res[0]["n_downgradient"] == 1
            assert res[0]["would_refute"]  # counter-evidence axis is mandatory
        finally:
            attribution.REGIONS_DIR = old
