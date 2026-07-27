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


def _write_test_region(tmp_path, source_props=None):
    """Helper: minimal region + single candidate source at ITM (204000, 720000)."""
    import json

    props = {"id": "s1", "name_he": "אתר בדיקה", "itm": [204000, 720000],
             "kind": "test",
             "expected_profiles": ["afff_ecf_weathered", "afff_ecf_fresh"],
             "emission_evidence": ["עדות"],
             "evidence_tier": "user_testimony"}
    if source_props:
        props.update(source_props)
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
                      "properties": props}],
    }), encoding="utf-8")
    return str(tmp_path)


def _afff_fp_row():
    return {"PFOS": 50, "PFHxS": 20, "PFHxA": 15, "PFOA": 15}


class TestSignalThresholdAndWeighting:
    def test_weak_stations_excluded_from_chem_share(self, tmp_path):
        """Near-LOD stations (Σ < MIN_SIGNAL_UG_L) must not count as chemical
        evidence, but must be listed separately as weak_downgradient."""
        from src import attribution

        old = attribution.REGIONS_DIR
        attribution.REGIONS_DIR = _write_test_region(tmp_path)
        try:
            region = attribution.load_region("test_region")
            fp = pd.DataFrame([_afff_fp_row(), _afff_fp_row()], index=["STRONG", "WEAK"])
            max_event = pd.DataFrame([
                {"station_name": "STRONG", "total_concentration": 0.5,
                 "x_itm": 196000, "y_itm": 720000},
                {"station_name": "WEAK", "total_concentration": 0.004,
                 "x_itm": 195000, "y_itm": 720000},
            ])
            df = pd.DataFrame({"station_name": ["STRONG", "WEAK"],
                               "compound": ["PFOS", "PFOS"],
                               "concentration": [0.5, 0.004]})
            res = attribution.evaluate_candidates(df, fp, max_event, region)[0]
            assert res["n_downgradient"] == 1
            assert res["downgradient"] == ["STRONG"]
            assert res["weak_downgradient"] == ["WEAK"]
            assert res["chem_share"] == 1.0  # computed on STRONG only
        finally:
            attribution.REGIONS_DIR = old

    def test_weighted_share_favors_strong_stations(self, tmp_path):
        """A matching 1.0 µg/L station must outweigh a non-matching 0.02 µg/L
        station in the log-weighted score (weighted > plain share)."""
        from src import attribution

        old = attribution.REGIONS_DIR
        attribution.REGIONS_DIR = _write_test_region(tmp_path)
        try:
            region = attribution.load_region("test_region")
            # HOT matches AFFF; COLD is a carboxylate profile (won't match)
            fp = pd.DataFrame(
                [_afff_fp_row(),
                 {"PFOA": 60, "PFNA": 20, "PFDA": 20}],
                index=["HOT", "COLD"]).fillna(0)
            max_event = pd.DataFrame([
                {"station_name": "HOT", "total_concentration": 1.0,
                 "x_itm": 196000, "y_itm": 720000},
                {"station_name": "COLD", "total_concentration": 0.02,
                 "x_itm": 195000, "y_itm": 720000},
            ])
            df = pd.DataFrame({"station_name": ["HOT", "COLD"],
                               "compound": ["PFOS", "PFOA"],
                               "concentration": [1.0, 0.02]})
            res = attribution.evaluate_candidates(df, fp, max_event, region)[0]
            assert res["chem_share"] == 0.5
            assert res["chem_share_weighted"] > res["chem_share"]
        finally:
            attribution.REGIONS_DIR = old


class TestAttenuationEvidence:
    def _run(self, tmp_path, totals):
        """Stations placed 1,2,3,4 km due west of the source with given Σ."""
        from src import attribution

        old = attribution.REGIONS_DIR
        attribution.REGIONS_DIR = _write_test_region(tmp_path)
        try:
            region = attribution.load_region("test_region")
            names = [f"W{i}" for i in range(len(totals))]
            fp = pd.DataFrame([_afff_fp_row()] * len(totals), index=names)
            max_event = pd.DataFrame([
                {"station_name": n, "total_concentration": t,
                 "x_itm": 204000 - 1000 * (i + 1), "y_itm": 720000}
                for i, (n, t) in enumerate(zip(names, totals))
            ])
            df = pd.DataFrame({"station_name": names,
                               "compound": ["PFOS"] * len(names),
                               "concentration": totals})
            return attribution.evaluate_candidates(df, fp, max_event, region)[0]
        finally:
            attribution.REGIONS_DIR = old

    def test_decaying_concentrations_support_candidate(self, tmp_path):
        res = self._run(tmp_path, [10.0, 1.0, 0.1, 0.05])
        assert res["attenuation"]["r_conc"] is not None
        assert res["attenuation"]["r_conc"] <= -0.4
        assert any("דעיכת ריכוז" in e for e in res["evidence_for"])

    def test_increasing_concentrations_flag_extra_source(self, tmp_path):
        res = self._run(tmp_path, [0.05, 0.1, 1.0, 10.0])
        assert res["attenuation"]["r_conc"] >= 0.4
        assert any("מקור נוסף" in e for e in res["evidence_against"])


class TestAnchorStation:
    def test_confirmed_anchor_appears_in_evidence(self, tmp_path):
        from src import attribution

        old = attribution.REGIONS_DIR
        attribution.REGIONS_DIR = _write_test_region(tmp_path, {
            "anchor_station": "ANCHOR",
            "anchor_provenance": "אישור בדיקה",
            "evidence_tier": "user_confirmed_source_area",
        })
        try:
            region = attribution.load_region("test_region")
            fp = pd.DataFrame([_afff_fp_row()], index=["ANCHOR"])
            max_event = pd.DataFrame([
                {"station_name": "ANCHOR", "total_concentration": 1121.0,
                 "x_itm": 203900, "y_itm": 720000},
            ])
            df = pd.DataFrame({"station_name": ["ANCHOR"],
                               "compound": ["PFOS"], "concentration": [1121.0]})
            res = attribution.evaluate_candidates(df, fp, max_event, region)[0]
            assert any("תחנת עוגן" in e for e in res["evidence_for"])
        finally:
            attribution.REGIONS_DIR = old


class TestGradedPlausibility:
    """Approved 2026-07-27: Gaussian lateral decay, sigma=k*L, 4 tiers."""

    flow = UniformFlowAssumption(direction_deg=270)

    def test_on_flow_line_is_tier1(self):
        w, t = self.flow.plausibility((196000, 720000), (204000, 720000), k=0.2)
        assert t == "1" and w > 0.99

    def test_large_lateral_offset_is_tier4(self):
        # 12 km south at 10 km west — the Or-Akiva geometry: outside the plume
        w, t = self.flow.plausibility((194000, 708000), (204000, 720000), k=0.2)
        assert t == "4" and w < 0.01

    def test_moderate_offset_tier_depends_on_k(self):
        # Maayan-Zvi geometry: ~4.7 km lateral at ~10.6 km travel
        _, t02 = self.flow.plausibility((193140, 720042), (203747, 724655), k=0.2)
        _, t03 = self.flow.plausibility((193140, 720042), (203747, 724655), k=0.3)
        assert t02 in ("3", "4")
        assert t03 in ("2", "3")           # wider plume lifts the tier

    def test_upgradient_is_up(self):
        _, t = self.flow.plausibility((205000, 720000), (204000, 720000))
        assert t == "up"


class TestOutfallHandling:
    def test_sewer_outfall_station_not_in_surface_down(self, tmp_path):
        """A pond routed to the sewer must not count as surface-downgradient
        (corrected per user 2026-07-27: בריכה-1500 case)."""
        import json

        from src import attribution

        old = attribution.REGIONS_DIR
        base = _write_test_region(tmp_path)
        region_dir = tmp_path / "test_region"
        rj = json.loads((region_dir / "region.json").read_text(encoding="utf-8"))
        rj["outfalls"] = {"POND": {"to": "sewer"}}
        (region_dir / "region.json").write_text(json.dumps(rj), encoding="utf-8")
        attribution.REGIONS_DIR = base
        try:
            region = attribution.load_region("test_region")
            fp = pd.DataFrame([_afff_fp_row()], index=["POND"])
            max_event = pd.DataFrame([{
                "station_name": "POND", "total_concentration": 5.0,
                "x_itm": 200000, "y_itm": 720000,
                "source_type": "נקודה מזוהה בנחל",
            }])
            df = pd.DataFrame({"station_name": ["POND"], "compound": ["PFOS"],
                               "concentration": [5.0]})
            res = attribution.evaluate_candidates(df, fp, max_event, region)[0]
            assert "POND" not in res["downgradient"]
        finally:
            attribution.REGIONS_DIR = old


class TestDemFlowModel:
    def _model(self, fallback=None):
        from src.flow_model import DemFlowModel
        points = {
            "SRC": {"itm": [204000, 720000], "kind": "candidate_source"},
            "DOWN": {"itm": [200000, 719000], "kind": "station"},
            "OFF": {"itm": [204000, 723000], "kind": "station"},
        }
        relations = {("SRC", "DOWN"): 5500.0}
        return DemFlowModel(points=points, relations=relations, fallback=fallback)

    def test_relation_answers_upgradient_and_distance(self):
        m = self._model()
        assert m.upgradient_of((200000, 719000), (204000, 720000))       # SRC→DOWN
        assert not m.upgradient_of((204000, 723000), (204000, 720000))   # SRC→OFF: no relation
        assert m.downgradient_distance_m((200000, 719000), (204000, 720000)) == 5500.0

    def test_path_distance_beats_projection(self):
        """The whole point of the DEM: along-path distance (5500 m) differs
        from the aerial/projected distance (~4123 m)."""
        m = self._model()
        d = m.downgradient_distance_m((200000, 719000), (204000, 720000))
        aerial = ((204000 - 200000) ** 2 + (720000 - 719000) ** 2) ** 0.5
        assert d > aerial

    def test_unknown_point_falls_back_to_uniform(self):
        m = self._model(fallback=UniformFlowAssumption(direction_deg=270))
        # (150000, 719000) is not a named point → uniform E→W logic applies
        assert m.upgradient_of((150000, 719000), (204000, 720000))

    def test_tier_is_derived_dem(self):
        from src.flow_model import DERIVED_DEM
        assert self._model().tier == DERIVED_DEM


class TestWaterTransfers:
    def test_pumped_station_joins_downgradient_but_not_attenuation(self, tmp_path):
        """A pond fed by declared pumping from a stream reach on the source's
        runoff path counts as downgradient (marked), but stays out of the
        attenuation regression."""
        import json

        from src import attribution

        old = attribution.REGIONS_DIR
        base = _write_test_region(tmp_path)
        # region with a transfer + a fake DEM derived layer
        region_dir = tmp_path / "test_region"
        rj = json.loads((region_dir / "region.json").read_text(encoding="utf-8"))
        rj["water_transfers"] = [{
            "kind": "pumping", "to_stations": ["POND"], "max_reach_m": 2000,
            "provenance": "בדיקה",
        }]
        (region_dir / "region.json").write_text(json.dumps(rj), encoding="utf-8")
        derived = region_dir / "derived"
        derived.mkdir()
        # source path runs due west from the source; POND sits 1.5 km south
        # of the path at km 5; STREAM sits on the path at km 4
        path = [[204000 - i * 500, 720000] for i in range(21)]  # 0..10 km
        (derived / "flow_paths.json").write_text(json.dumps({
            "cell_m": 30, "near_path_m": 300,
            "points": {
                "s1": {"itm": [204000, 720000], "kind": "candidate_source",
                       "path_itm": path, "path_len_m": 10000},
                "STREAM": {"itm": [200000, 720000], "kind": "station",
                           "source_type": "נקודה מזוהה בנחל", "path_itm": [], "path_len_m": 0},
                "POND": {"itm": [199000, 718500], "kind": "station",
                         "source_type": "מאגר", "path_itm": [], "path_len_m": 0},
            },
            "relations": [{"from": "s1", "to": "STREAM", "path_distance_m": 4000,
                           "offset_m": 10}],
        }), encoding="utf-8")

        attribution.REGIONS_DIR = base
        try:
            region = attribution.load_region("test_region")
            fp = pd.DataFrame([_afff_fp_row(), _afff_fp_row()],
                              index=["STREAM", "POND"])
            max_event = pd.DataFrame([
                {"station_name": "STREAM", "total_concentration": 0.5,
                 "x_itm": 200000, "y_itm": 720000, "source_type": "נקודה מזוהה בנחל"},
                {"station_name": "POND", "total_concentration": 0.3,
                 "x_itm": 199000, "y_itm": 718500, "source_type": "מאגר"},
            ])
            df = pd.DataFrame({"station_name": ["STREAM", "POND"],
                               "compound": ["PFOS", "PFOS"],
                               "concentration": [0.5, 0.3]})
            res = attribution.evaluate_candidates(df, fp, max_event, region)[0]
            assert "POND" in res["downgradient"]          # joined via transfer
            assert "POND" in res["transfer_fed"]
            assert any("מוזנות-שאיבה" in e for e in res["evidence_for"])
        finally:
            attribution.REGIONS_DIR = old


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
