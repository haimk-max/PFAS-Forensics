"""attribution.py — Evidence fusion v0: candidate sources vs. measurements.

Three independent evidence axes per candidate (operationalizing the project's
Flow Direction Caution rule):
    chem     — do impacted stations match the candidate's expected profiles?
    hydro    — are impacted stations downgradient of the candidate?
    emission — independent evidence of emitting activity at the site.

Tier language is fixed by project policy: "מועמד ליבה" / "מועמד משני" /
"רקע מקומי" — never "המקור". While the flow model is an ASSUMPTION, the
hydro axis is capped: it can support consistency but cannot confirm, and no
candidate may exceed "מועמד משני" on assumed flow alone unless the chemical
axis is independently strong.

Every result carries evidence_for / evidence_against / would_refute — the
counter-evidence axis is mandatory (governance §18), not optional.
"""

import json
import math
import os

import pandas as pd

from config import MIN_SIGNAL_UG_L
from src.flow_model import UniformFlowAssumption, ASSUMED
from src.source_profiles import PRECURSORS, match_profiles

REGIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "regions")

# Attenuation-evidence thresholds (Spearman rho on projected distance).
# |r| below this is reported as inconclusive; above — as a pattern.
_ATTEN_R_THRESHOLD = 0.4
_ATTEN_MIN_N = 4


def load_region(name: str) -> dict:
    base = os.path.join(REGIONS_DIR, name)
    with open(os.path.join(base, "region.json"), encoding="utf-8") as f:
        region = json.load(f)
    region["_base"] = base
    return region


def load_sources(region: dict) -> list[dict]:
    feats = []
    for layer in region.get("layers", []):
        if layer.get("kind") != "potential_sources":
            continue
        with open(os.path.join(region["_base"], layer["path"]), encoding="utf-8") as f:
            gj = json.load(f)
        for feat in gj.get("features", []):
            props = dict(feat.get("properties", {}))
            props["_layer_quality"] = layer.get("quality", "unknown")
            feats.append(props)
    return feats


def flow_from_region(region: dict, domain: str = "groundwater") -> UniformFlowAssumption:
    cfg = region["flow"][domain]
    return UniformFlowAssumption(
        direction_deg=cfg["direction_deg"], tier=cfg["tier"],
        declared_by=cfg.get("declared_by", ""), declared_on=cfg.get("declared_on", ""),
    )


def evaluate_candidates(df: pd.DataFrame, fingerprint: pd.DataFrame,
                        max_event: pd.DataFrame, region: dict) -> list[dict]:
    """Score every declared candidate source against the loaded measurements.

    Returns a list of dicts (one per candidate) with axis summaries, a tier
    suggestion, and mandatory for/against/would-refute evidence lists.
    """
    sources = load_sources(region)
    flow = flow_from_region(region, "groundwater")
    matches = match_profiles(fingerprint, top_n=3)

    impacted = max_event[max_event["total_concentration"] > 0]
    stn_xy, stn_total = {}, {}
    for _, r in impacted.iterrows():
        if pd.notna(r.get("x_itm")) and pd.notna(r.get("y_itm")):
            stn_xy[r["station_name"]] = (r["x_itm"], r["y_itm"])
            stn_total[r["station_name"]] = float(r["total_concentration"])

    # Precursor share (%) per station, from the fingerprint columns
    prec_cols = [c for c in fingerprint.columns if c.upper() in {p.upper() for p in PRECURSORS}]
    prec_share = fingerprint[prec_cols].sum(axis=1) if prec_cols else pd.Series(dtype=float)

    results = []
    for src in sources:
        sx, sy = src["itm"]
        expected = set(src.get("expected_profiles", []))

        down_all = [s for s, xy in stn_xy.items() if flow.upgradient_of(xy, (sx, sy))]
        up_or_side = [s for s in stn_xy if s not in down_all]

        # --- signal threshold: near-LOD stations must not count as evidence ---
        down = [s for s in down_all if stn_total[s] >= MIN_SIGNAL_UG_L]
        weak_down = [s for s in down_all if stn_total[s] < MIN_SIGNAL_UG_L]

        # chem axis (strong-signal stations only): plain share + log-weighted
        chem_hits = []
        if not matches.empty:
            for s in down:
                top = matches[matches["station"] == s]
                if set(top["profile_key"]) & expected:
                    chem_hits.append(s)
        chem_share = len(chem_hits) / len(down) if down else 0.0

        def _w(s):  # evidence weight grows with orders of magnitude above threshold
            return max(0.0, math.log10(stn_total[s] / MIN_SIGNAL_UG_L))
        w_total = sum(_w(s) for s in down)
        w_hits = sum(_w(s) for s in chem_hits)
        chem_share_weighted = (w_hits / w_total) if w_total > 0 else 0.0

        # --- attenuation evidence (coarse: projected distance, until DEM) ---
        attenuation = {"n": 0, "r_conc": None, "r_precursor": None, "note_he": ""}
        atten_pts = [(flow.downgradient_distance_m(stn_xy[s], (sx, sy)), s)
                     for s in down]
        atten_pts = [(d, s) for d, s in atten_pts if d > 0]
        if len(atten_pts) >= _ATTEN_MIN_N:
            from scipy.stats import spearmanr
            dists = [d for d, _ in atten_pts]
            logs = [math.log10(stn_total[s]) for _, s in atten_pts]
            r_conc = float(spearmanr(dists, logs).statistic)
            attenuation.update(n=len(atten_pts), r_conc=round(r_conc, 2))
            if len(prec_share) > 0:
                prec_vals = [float(prec_share.get(s, 0.0)) for _, s in atten_pts]
                if any(v > 0 for v in prec_vals):
                    r_prec = float(spearmanr(dists, prec_vals).statistic)
                    attenuation["r_precursor"] = round(r_prec, 2)

        emission = src.get("emission_evidence", [])
        ev_tier = src.get("evidence_tier", "none")
        anchor = src.get("anchor_station")

        evidence_for, evidence_against = [], []
        if anchor and anchor in stn_total:
            evidence_for.append(
                f"תחנת עוגן מאושרת באתר: \"{anchor}\" "
                f"(Σ={stn_total[anchor]:,.1f} µg/L) — {src.get('anchor_provenance', 'אישור משתמש')}")
        if down:
            evidence_for.append(
                f"{len(down)} תחנות פגועות (מעל סף {MIN_SIGNAL_UG_L} µg/L) במורד המשוער "
                f"({flow.describe_he()})")
        if chem_hits:
            evidence_for.append(
                f"התאמה כימית לפרופילים הצפויים ב-{len(chem_hits)}/{len(down)} "
                f"מתחנות המורד; משוקלל-עוצמה: {chem_share_weighted*100:.0f}% "
                f"(עקבי עם — אינו מוכיח)")
        if attenuation["r_conc"] is not None:
            r = attenuation["r_conc"]
            if r <= -_ATTEN_R_THRESHOLD:
                attenuation["note_he"] = "דפוס דעיכה עקבי עם מקור באתר"
                evidence_for.append(
                    f"דעיכת ריכוז במורד (Spearman r={r}, n={attenuation['n']}) — "
                    f"עקבי עם מקור באתר (מרחק מוטל על ציר הזרימה — גס עד DEM)")
            elif r >= _ATTEN_R_THRESHOLD:
                attenuation["note_he"] = "ריכוז עולה במורד — מקור נוסף אפשרי"
                evidence_against.append(
                    f"ריכוז עולה עם המרחק במורד (r={r}, n={attenuation['n']}) — "
                    f"מרמז על מקור נוסף בין הנקודות (מרחק מוטל — גס עד DEM)")
            else:
                attenuation["note_he"] = "דפוס מרחבי לא חד-משמעי"
        if attenuation.get("r_precursor") is not None and \
                attenuation["r_precursor"] <= -_ATTEN_R_THRESHOLD:
            evidence_for.append(
                f"הזדקנות פרופיל נצפית: נתח קדם-חומרים יורד במורד "
                f"(r={attenuation['r_precursor']}) — עקבי עם התרחקות מהמקור")
        if emission:
            evidence_for.append("ראיית פליטה: " + "; ".join(emission) +
                                f" [רמה: {ev_tier}]")

        if not down:
            evidence_against.append(
                f"אין תחנות פגועות מעל סף-האות במורד המשוער של האתר")
        if down and chem_share < 0.3:
            evidence_against.append(
                "רוב תחנות המורד אינן תואמות את הפרופילים הצפויים מהמקור")
        # At-site stations (near the source or the confirmed anchor) are NOT
        # "elsewhere" — a similar profile there supports the candidate rather
        # than suggesting another source, so they are excluded from this list.
        def _near_site(s, radius_m=1000.0):
            x, y = stn_xy[s]
            return math.hypot(x - sx, y - sy) <= radius_m

        strong_up = [s for s in up_or_side
                     if stn_total[s] >= MIN_SIGNAL_UG_L
                     and s != anchor and not _near_site(s)
                     and s in set(matches[matches["rank"] == 1]["station"])
                     and set(matches[(matches["station"] == s)]["profile_key"]) & expected]
        if strong_up:
            evidence_against.append(
                f"תחנות שאינן במורד האתר מציגות פרופיל דומה ({', '.join(strong_up[:3])}"
                + ("..." if len(strong_up) > 3 else "")
                + ") — עקבי גם עם מקור אחר/נוסף")

        # Tier suggestion with the assumed-flow cap
        axes = sum([bool(down), chem_share >= 0.3, bool(emission)])
        if axes >= 3 and flow.tier != ASSUMED:
            tier = "מועמד ליבה"
        elif axes >= 2:
            tier = "מועמד משני"
            if flow.tier == ASSUMED and axes == 3:
                tier = "מועמד משני (תקרה: כיוון זרימה מונח, לא מדוד)"
        elif axes == 1:
            tier = "רקע מקומי / ראיה בודדת"
        else:
            tier = "אין תמיכה בנתונים הנוכחיים"

        results.append({
            "id": src.get("id"), "name_he": src.get("name_he"),
            "itm": (sx, sy), "kind": src.get("kind"),
            "location_quality": src.get("location_quality", ""),
            "tier": tier,
            "n_downgradient": len(down), "downgradient": down,
            "weak_downgradient": weak_down,
            "chem_share": round(chem_share, 2),
            "chem_share_weighted": round(chem_share_weighted, 2),
            "chem_hits": chem_hits,
            "attenuation": attenuation,
            "anchor_station": anchor,
            "emission_evidence": emission,
            "flow_caveat": flow.describe_he(),
            "evidence_for": evidence_for,
            "evidence_against": evidence_against,
            "would_refute": [
                "מפלסים מדודים המראים כיוון זרימה שונה מההנחה",
                "פרופיל דיגום בתחנה צמודה לאתר ללא חתימת הפרופילים הצפויים",
                "בירור שמערך הכיבוי באתר אינו/לא היה מבוסס קצף פלואורי (AFFF)",
            ],
        })
    return results
