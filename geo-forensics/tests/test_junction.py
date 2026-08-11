"""Junction-load test (approved 2026-08-11): segment anomalies along a flow
stem that indicate load joining between consecutive stations. Each detector
gets a synthetic case + a clean-decay case that must stay silent."""

import pandas as pd
import pytest

from src.attribution import junction_scan


def _fp(rows):
    """fingerprint frame from {station: {compound: pct}} (rows sum ~100)."""
    return pd.DataFrame(rows).T.fillna(0.0)


HEAD = "head"


def _series(*items):
    return [{"km": km, "station": s, "sigma": sig} for km, s, sig in items]


def test_clean_decay_is_silent():
    fp = _fp({
        HEAD: {"PFOS": 50, "PFHxS": 10, "6:2FT": 30, "PFOA": 2, "PFBA": 8},
        "s1": {"PFOS": 40, "PFHxS": 15, "6:2FT": 20, "PFOA": 2, "PFBA": 23},
        "s2": {"PFOS": 30, "PFHxS": 20, "6:2FT": 10, "PFOA": 3, "PFBA": 37},
        "s3": {"PFOS": 25, "PFHxS": 22, "6:2FT": 5, "PFOA": 3, "PFBA": 45},
    })
    ser = _series((1, "s1", 10.0), (5, "s2", 2.0), (10, "s3", 0.5))
    assert junction_scan(ser, fp, HEAD) == []


def test_local_sigma_rise_flags_segment():
    fp = _fp({
        HEAD: {"PFOS": 50, "PFOA": 2, "PFBA": 48},
        "s1": {"PFOS": 40, "PFOA": 2, "PFBA": 58},
        "s2": {"PFOS": 38, "PFOA": 2, "PFBA": 60},
        "s3": {"PFOS": 39, "PFOA": 2, "PFBA": 59},
    })
    # global trend decays, but s2->s3 rises x3
    ser = _series((1, "s1", 10.0), (5, "s2", 0.2), (8, "s3", 0.6))
    out = junction_scan(ser, fp, HEAD)
    assert len(out) == 1
    assert out[0]["segment"] == ("s2", "s3")
    assert any("עליית Σ" in s for s in out[0]["signals"])


def test_similarity_rebound_flags_segment():
    fp = _fp({
        HEAD: {"PFOS": 80, "PFBA": 20},
        "s1": {"PFOS": 75, "PFBA": 25},          # close to head
        "s2": {"PFOS": 10, "PFBA": 90},          # weathered far away
        "s3": {"PFOS": 78, "PFBA": 22},          # snaps BACK to head-like
    })
    ser = _series((1, "s1", 10.0), (5, "s2", 1.0), (10, "s3", 0.5))
    out = junction_scan(ser, fp, HEAD)
    assert any(any("מונוטוניות-הבליה" in sig for sig in f["signals"])
               for f in out)


def test_marker_jump_flags_segment():
    fp = _fp({
        HEAD: {"PFOS": 60, "PFOA": 1, "PFBA": 39},
        "s1": {"PFOS": 50, "PFOA": 1, "PFBA": 49},
        "s2": {"PFOS": 48, "PFOA": 10, "PFBA": 42},   # PFOA 1% -> 10%
    })
    ser = _series((1, "s1", 5.0), (6, "s2", 2.0))
    out = junction_scan(ser, fp, HEAD)
    assert any(any("PFOA" in sig for sig in f["signals"]) for f in out)


def test_precursor_rebound_flags_segment():
    fp = _fp({
        HEAD: {"PFOS": 40, "6:2FT": 35, "PFBA": 25},
        "s1": {"PFOS": 60, "6:2FT": 1, "PFBA": 39},    # depleted
        "s2": {"PFOS": 55, "6:2FT": 9, "PFBA": 36},    # fresh markers return
    })
    ser = _series((5, "s1", 2.0), (20, "s2", 0.5))
    out = junction_scan(ser, fp, HEAD)
    assert any(any("שיבת קדם-חומרים" in sig for sig in f["signals"])
               for f in out)


def test_short_series_and_missing_head_are_silent():
    fp = _fp({HEAD: {"PFOS": 100}, "s1": {"PFOS": 100}})
    assert junction_scan(_series((1, "s1", 1.0)), fp, HEAD) == []
    assert junction_scan(_series((1, "s1", 1.0), (2, "s1", 1.0)),
                         fp, "no-such-head") == []
