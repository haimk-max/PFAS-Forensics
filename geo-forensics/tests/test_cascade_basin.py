"""Tests for the cascade chain-candidate rules (production capture slack,
user feedback 2026-08-12 item 4) and the declared basin screen (item 6)."""

import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _region_with_dem(tmp_path, stations):
    """Region + candidate at (204000,720000) with a due-west runoff path and
    the given station points (name -> (x, y, source_type))."""
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
                      "properties": {
                          "id": "s1", "name_he": "אתר בדיקה",
                          "itm": [204000, 720000], "kind": "test",
                          "expected_profiles": ["afff_ecf_weathered",
                                                "afff_ecf_fresh"],
                          "emission_evidence": ["עדות"],
                          "evidence_tier": "user_testimony"}}],
    }), encoding="utf-8")
    derived = region_dir / "derived"
    derived.mkdir()
    path = [[204000 - i * 500, 720000] for i in range(21)]  # 0..10 km west
    points = {"s1": {"itm": [204000, 720000], "kind": "candidate_source",
                     "path_itm": path, "path_len_m": 10000}}
    for name, (x, y, st) in stations.items():
        points[name] = {"itm": [x, y], "kind": "station", "source_type": st,
                        "path_itm": [], "path_len_m": 0}
    (derived / "flow_paths.json").write_text(json.dumps({
        "cell_m": 30, "near_path_m": 300,
        "points": points, "relations": []}), encoding="utf-8")
    return str(tmp_path)


def _run(tmp_path, stations):
    from src import attribution

    old = attribution.REGIONS_DIR
    attribution.REGIONS_DIR = _region_with_dem(tmp_path, stations)
    try:
        region = attribution.load_region("test_region")
        names = list(stations)
        fp = pd.DataFrame(
            [{"PFOS": 50, "PFHxS": 20, "PFHxA": 15, "PFOA": 15}] * len(names),
            index=names)
        max_event = pd.DataFrame([
            {"station_name": n, "total_concentration": 0.5,
             "x_itm": stations[n][0], "y_itm": stations[n][1],
             "source_type": stations[n][2]}
            for n in names])
        df = pd.DataFrame({"station_name": names,
                           "compound": ["PFOS"] * len(names),
                           "concentration": [0.5] * len(names)})
        return attribution.evaluate_candidates(df, fp, max_event, region)[0]
    finally:
        attribution.REGIONS_DIR = old


class TestCascadeCaptureSlack:
    def test_monitoring_well_beyond_300m_not_cascade(self, tmp_path):
        # 700 m south of the runoff path — outside the 300 m adjacency rule
        res = _run(tmp_path, {"נד בדיקה": (200000, 719300, "קידוח")})
        assert "נד בדיקה" not in res["cascade_candidates"]

    def test_production_well_capture_zone_reaches_channel(self, tmp_path):
        """A production well 700 m off-path: its declared 500 m capture
        radius closes the gap (700-500=200 <= 300) — chain candidate, coarse."""
        res = _run(tmp_path, {"פ בדיקה": (200000, 719300, "קידוח")})
        assert "פ בדיקה" in res["cascade_candidates"]
        meta = res["cascade_meta"]["פ בדיקה"]
        assert meta["well_class"] == "production"
        assert meta["coarse"] is True

    def test_monitoring_well_within_300m_is_cascade_sharp(self, tmp_path):
        res = _run(tmp_path, {"נד בדיקה": (200000, 719800, "קידוח")})
        assert "נד בדיקה" in res["cascade_candidates"]
        assert res["cascade_meta"]["נד בדיקה"]["coarse"] is False

    def test_cascade_member_not_counted_downgradient(self, tmp_path):
        """The chain pathway competes with the plume explanation — a chain
        candidate must not be counted as direct downgradient evidence."""
        res = _run(tmp_path, {"נד בדיקה": (200000, 719800, "קידוח")})
        assert "נד בדיקה" not in res["downgradient"]


class TestBasinScreen:
    def _screen(self, tmp_path, with_screen=True):
        from generate_review_report import _basin_screen

        base = tmp_path / "case"
        (base / "derived").mkdir(parents=True)
        trunk = [[204000 - i * 500, 720000] for i in range(21)]
        joins = [[202000, 722000], [202000, 721000], [202000, 720000]]
        west = [[203000, 726000], [201000, 727000], [199000, 728000]]
        (base / "derived" / "flow_paths.json").write_text(json.dumps({
            "cell_m": 30, "near_path_m": 300,
            "points": {
                "SRC": {"itm": [204000, 720000], "path_itm": trunk},
                "IN": {"itm": [202000, 722000], "path_itm": joins},
                "OUT": {"itm": [203000, 726000], "path_itm": west},
            }, "relations": []}), encoding="utf-8")
        region = {"basin_screen": {
            "rule": "d8_converges_with_trunk", "trunk_source": "SRC",
            "cell_match_m": 40}} if with_screen else {}
        df = pd.DataFrame({
            "station_name": ["IN", "IN", "OUT"],
            "compound": ["PFOS", "PFOA", "PFOS"],
            "concentration": [0.5, 0.1, 0.9],
        })
        return _basin_screen(df, region, str(base))

    def test_diverging_station_excluded_and_listed(self, tmp_path):
        df, excluded = self._screen(tmp_path)
        assert set(df["station_name"]) == {"IN"}
        assert [e["name"] for e in excluded] == ["OUT"]
        assert "אגן אחר" in excluded[0]["reason_he"]

    def test_no_declaration_no_screen(self, tmp_path):
        df, excluded = self._screen(tmp_path, with_screen=False)
        assert set(df["station_name"]) == {"IN", "OUT"}
        assert excluded == []
