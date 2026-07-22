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
import os

import pandas as pd

from src.flow_model import UniformFlowAssumption, ASSUMED
from src.source_profiles import match_profiles

REGIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "regions")


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
    stn_xy = {r["station_name"]: (r["x_itm"], r["y_itm"])
              for _, r in impacted.iterrows()
              if pd.notna(r.get("x_itm")) and pd.notna(r.get("y_itm"))}

    results = []
    for src in sources:
        sx, sy = src["itm"]
        expected = set(src.get("expected_profiles", []))

        down = [s for s, xy in stn_xy.items() if flow.upgradient_of(xy, (sx, sy))]
        up_or_side = [s for s in stn_xy if s not in down]

        # chem axis: share of downgradient impacted stations whose top-3
        # matches intersect the candidate's expected profiles
        chem_hits = []
        if not matches.empty:
            for s in down:
                top = matches[matches["station"] == s]
                if set(top["profile_key"]) & expected:
                    chem_hits.append(s)
        chem_share = len(chem_hits) / len(down) if down else 0.0

        emission = src.get("emission_evidence", [])
        ev_tier = src.get("evidence_tier", "none")

        evidence_for, evidence_against = [], []
        if down:
            evidence_for.append(
                f"{len(down)} תחנות פגועות במורד המשוער ({flow.describe_he()})")
        if chem_hits:
            evidence_for.append(
                f"התאמה כימית לפרופילים הצפויים ב-{len(chem_hits)}/{len(down)} "
                f"מתחנות המורד (עקבי עם — אינו מוכיח)")
        if emission:
            evidence_for.append("ראיית פליטה: " + "; ".join(emission) +
                                f" [רמה: {ev_tier}]")

        if not down:
            evidence_against.append("אין תחנות פגועות במורד המשוער של האתר")
        if down and chem_share < 0.3:
            evidence_against.append(
                "רוב תחנות המורד אינן תואמות את הפרופילים הצפויים מהמקור")
        strong_up = [s for s in up_or_side
                     if s in set(matches[matches["rank"] == 1]["station"])
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
            "chem_share": round(chem_share, 2), "chem_hits": chem_hits,
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
