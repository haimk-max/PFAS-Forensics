"""attribution.py — Evidence fusion v0: candidate sources vs. measurements.

Three COMPLEMENTARY evidence axes per candidate (they rest on different kinds
of information and reinforce each other; they are not statistically
independent — wording fixed 2026-08-12):
    chem     — do impacted stations match the candidate's expected profiles?
    hydro    — are impacted stations downgradient of the candidate?
    emission — independent evidence of emitting activity at the site.

Tier language is fixed by project policy (vocabulary migrated 2026-08-12,
methodology v1.0): "מועמד מרכזי" / "מועמד משני" / "מקור אפשרי" /
"לא נתמך בשלב זה" — never "המקור". While the flow model is an ASSUMPTION,
the hydro axis is capped: it can support consistency but cannot confirm, and
no candidate may exceed "מועמד משני" on assumed flow alone.

The chemical axis is reported as FOUR separate, transparent components
(methodology v1.0 §5-§7) — never as one composite "XX% match":
    chem_similarity_median — composition similarity to the expected profile
                             (0-1; median over counted downgradient stations)
    weathering_fit         — does the composition change along the path match
                             the expected weathering direction? (path level
                             only — there is no per-station basis for it)
    signal_quality         — how reliable are the fingerprints behind it
    chem_support           — rule-based overall rating, anchored to the same
                             threshold that feeds the tier (chem_share>=0.3)

Every result carries evidence_for / evidence_against / would_refute — the
counter-evidence axis is mandatory (governance §18), not optional.
"""

import json
import math
import os

import pandas as pd

from config import (
    CLUSTER_MIN_SIGNAL_UG_L,
    GW_PLUME_K,
    JUNCTION_MARKER_JUMP_PP,
    JUNCTION_PREC_DEPLETED_PP,
    JUNCTION_PREC_REBOUND_PP,
    JUNCTION_RISE_FACTOR,
    JUNCTION_SIM_REBOUND_PP,
    MIN_SIGNAL_UG_L,
    PRODUCTION_CAPTURE_RADIUS_M,
    WELL_MONITORING_PREFIXES,
    WELL_PRODUCTION_PREFIXES,
)
from src.flow_model import ASSUMED, DemFlowModel, UniformFlowAssumption
from src.source_profiles import PRECURSORS, match_profiles

REGIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "regions")

# Attenuation-evidence thresholds (Spearman rho on downgradient distance).
# |r| below this is reported as inconclusive; above — as a pattern.
_ATTEN_R_THRESHOLD = 0.4
_ATTEN_MIN_N = 4

# Station source_types transported by surface runoff; everything else
# (wells, springs) is treated as groundwater-domain.
SURFACE_TYPES = {"נקודה מזוהה בנחל", "תחנה הידרומטרית", "מאגר"}

# Stable terminal markers for the junction-load ratio test: shares of these
# compounds are conservative under transport, so a between-reach jump flags
# added load even from a similar-composition (same-family) second source.
_JUNCTION_MARKERS = ("PFOA", "PFOS")


def classify_well(name, source_type=""):
    """Well class by the Water Authority naming convention (approved
    2026-08-12): monitoring wells (נד/נת/מח) sample a point; production
    wells (פ/מק) integrate an ill-defined pumping capture zone. The name
    prefix is primary; an explicit source_type ("קידוח ניטור"/"קידוח
    הפקה") is the fallback for unprefixed names.
    Returns 'monitoring' | 'production' | 'unknown'."""
    tok = str(name).strip().split()[0] if str(name).strip() else ""
    tok = tok.rstrip(".'’׳")
    if tok in WELL_MONITORING_PREFIXES:
        return "monitoring"
    if tok in WELL_PRODUCTION_PREFIXES:
        return "production"
    st = str(source_type)
    if "ניטור" in st:
        return "monitoring"
    if "הפקה" in st:
        return "production"
    return "unknown"


def _cos_sim(a, b):
    num = float((a * b).sum())
    den = math.sqrt(float((a * a).sum())) * math.sqrt(float((b * b).sum()))
    return 100.0 * num / den if den > 0 else 0.0


def junction_scan(series, fingerprint, head_name):
    """Junction-load test (approved 2026-08-11): scan a flow stem for
    segment anomalies that indicate load joining between consecutive
    stations — signals a SIMILAR-composition second source would still
    trip, because they work on ratios and monotonicity, not on overall
    similarity:

      1. local Σ rise (next/prev ≥ JUNCTION_RISE_FACTOR) even when the
         global trend decays;
      2. similarity-to-head rebound (≥ JUNCTION_SIM_REBOUND_PP above the
         running minimum) — weathering must not move a station CLOSER to
         the source profile;
      3. stable-marker share jump (PFOA/PFOS, ≥ JUNCTION_MARKER_JUMP_PP
         and at least doubled);
      4. precursor-share return after depletion (fresh markers cannot
         reappear downstream without fresh input).

    series: ordered [{"km", "station", "sigma"}] along the stem (signal
    stations only). fingerprint: normalized %-composition matrix.
    head_name: reference profile (anchor / most source-adjacent station).
    Returns [{"segment", "km", "signals"}] — one entry per flagged segment.
    """
    rows = [d for d in series if d["station"] in fingerprint.index]
    if len(rows) < 2 or head_name not in fingerprint.index:
        return []
    prec_cols = [c for c in fingerprint.columns
                 if c.upper() in {p.upper() for p in PRECURSORS}]
    head = fingerprint.loc[head_name]

    def prec_share(s):
        return float(fingerprint.loc[s, prec_cols].sum()) if prec_cols else 0.0

    sims = [_cos_sim(fingerprint.loc[d["station"]], head) for d in rows]
    findings = []
    run_min_sim = sims[0]
    run_min_prec = prec_share(rows[0]["station"])
    for i in range(1, len(rows)):
        a, b = rows[i - 1], rows[i]
        signals = []
        if a["sigma"] > 0 and b["sigma"] / a["sigma"] >= JUNCTION_RISE_FACTOR:
            signals.append(f"עליית Σ מקומית פי {b['sigma'] / a['sigma']:.1f} "
                           f"({a['sigma']:.3f}←{b['sigma']:.3f})")
        if sims[i] >= run_min_sim + JUNCTION_SIM_REBOUND_PP:
            signals.append(f"ההרכב נעשה דומה יותר למוקד ככל שמתרחקים "
                           f"({run_min_sim:.0f}%←{sims[i]:.0f}%) — מנוגד "
                           f"לכיוון הבליה הצפוי")
        for m in _JUNCTION_MARKERS:
            if m in fingerprint.columns:
                ma = float(fingerprint.loc[a["station"], m])
                mb = float(fingerprint.loc[b["station"], m])
                if mb - ma >= JUNCTION_MARKER_JUMP_PP and mb >= 2 * ma:
                    signals.append(f"קפיצת נתח {m}: {ma:.1f}%←{mb:.1f}%")
        pb = prec_share(b["station"])
        if run_min_prec <= JUNCTION_PREC_DEPLETED_PP and \
                pb >= run_min_prec + JUNCTION_PREC_REBOUND_PP:
            signals.append(f"שיבת קדם-חומרים במורד ({run_min_prec:.1f}%←"
                           f"{pb:.1f}%)")
        if signals:
            findings.append({
                "segment": (a["station"], b["station"]),
                "km": (a["km"], b["km"]),
                "signals": signals,
            })
        run_min_sim = min(run_min_sim, sims[i])
        run_min_prec = min(run_min_prec, prec_share(b["station"]))
    return findings


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


def flow_from_region(region: dict, domain: str = "groundwater"):
    """Flow provider for a domain. Surface auto-upgrades to the DEM-derived
    model when regions/<name>/derived/flow_paths.json exists; the declared
    uniform assumption remains as fallback for uncovered points."""
    cfg = region["flow"][domain]
    uniform = UniformFlowAssumption(
        direction_deg=cfg["direction_deg"], tier=cfg["tier"],
        declared_by=cfg.get("declared_by", ""), declared_on=cfg.get("declared_on", ""),
    )
    if domain == "surface" and "_base" in region:
        dem = DemFlowModel.from_region_dir(region["_base"], fallback=uniform)
        if dem is not None:
            return dem
    return uniform


def evaluate_candidates(df: pd.DataFrame, fingerprint: pd.DataFrame,
                        max_event: pd.DataFrame, region: dict) -> list[dict]:
    """Score every declared candidate source against the loaded measurements.

    Returns a list of dicts (one per candidate) with axis summaries, a tier
    suggestion, and mandatory for/against/would-refute evidence lists.
    """
    sources = load_sources(region)
    flow_gw = flow_from_region(region, "groundwater")
    flow_surface = flow_from_region(region, "surface")
    dem_active = isinstance(flow_surface, DemFlowModel)
    # Expert may void the groundwater GEOMETRIC axis for a case (local perched
    # water in a clay unit: a regional flow direction has no meaning, and the
    # production wells draw from a deeper unit). Declared per region as
    # flow.groundwater.mode == "local_perched". Consequence: wells are neither
    # counted downgradient nor called upgradient — they carry no geometric
    # verdict at all. The chemical axis and the cascade (bank-infiltration)
    # channel are unaffected.
    _gw_cfg = (region.get("flow", {}) or {}).get("groundwater", {}) or {}
    gw_axis_off = _gw_cfg.get("mode") == "local_perched"
    gw_axis_off_he = _gw_cfg.get("mode_note_he", "")
    matches = match_profiles(fingerprint, top_n=3)

    impacted = max_event[max_event["total_concentration"] > 0]
    # Case scope: only stations inside the region bbox belong to this case
    # (cases may share a measurement file — the split is by bbox).
    bbox = region.get("bbox_itm")
    outfalls = region.get("outfalls", {})
    stn_xy, stn_total, stn_domain, stn_srctype = {}, {}, {}, {}
    for _, r in impacted.iterrows():
        if pd.notna(r.get("x_itm")) and pd.notna(r.get("y_itm")):
            name = r["station_name"]
            if bbox and not (bbox[0] <= r["x_itm"] <= bbox[2]
                             and bbox[1] <= r["y_itm"] <= bbox[3]):
                continue
            stn_xy[name] = (r["x_itm"], r["y_itm"])
            stn_total[name] = float(r["total_concentration"])
            stn_domain[name] = ("surface"
                               if str(r.get("source_type", "")) in SURFACE_TYPES
                               else "groundwater")
            stn_srctype[name] = str(r.get("source_type", ""))

    def _flow_for(s):
        return flow_surface if stn_domain.get(s) == "surface" else flow_gw

    def _outfall_to(s):
        return outfalls.get(s, {}).get("to")

    # Precursor share (%) per station, from the fingerprint columns
    prec_cols = [c for c in fingerprint.columns if c.upper() in {p.upper() for p in PRECURSORS}]
    prec_share = fingerprint[prec_cols].sum(axis=1) if prec_cols else pd.Series(dtype=float)

    # Cross-candidate site union: a station inside ANY declared source
    # complex tells that complex's story — it must not surface as another
    # candidate's chain candidate.
    def _in_any_site(s):
        for _src in sources:
            toks = _src.get("site_name_tokens") or []
            if toks and any(t in s for t in toks) and math.hypot(
                    stn_xy[s][0] - _src["itm"][0],
                    stn_xy[s][1] - _src["itm"][1]) <= 5000.0:
                return True
        return False

    results = []
    for src in sources:
        sx, sy = src["itm"]
        expected = set(src.get("expected_profiles", []))

        # Site envelope (approved 2026-08-12, TEMPORARY name rule): stations
        # whose name contains a declared site token belong to the source
        # complex. Basin-scale series must not resolve intra-site dynamics —
        # site members are excluded from the attenuation series, the
        # junction scan and the similar-profile counter-evidence. A 5 km
        # sanity radius guards against token collisions in combined names.
        site_tokens = src.get("site_name_tokens") or []

        def _in_site(s):
            if not site_tokens or not any(t in s for t in site_tokens):
                return False
            return math.hypot(stn_xy[s][0] - sx, stn_xy[s][1] - sy) <= 5000.0

        site_members = sorted(s for s in stn_xy if _in_site(s))

        # Surface stations: on-path (DEM) or uniform-sector logic.
        # Groundwater stations: graded plume-plausibility tiers (approved
        # 2026-07-27) — tiers 1-2 count as downgradient support, tier 3 is
        # listed as weak-fringe, tier 4/upgradient is NOT explained by this
        # source (a contaminated tier-4 station is a finding, not noise).
        gw_tiers = {}
        down_all = []
        for s, xy in stn_xy.items():
            if stn_domain[s] == "surface":
                if flow_surface.upgradient_of(xy, (sx, sy)) and \
                        _outfall_to(s) != "sewer":
                    down_all.append(s)
            elif gw_axis_off:
                gw_tiers[s] = {"w": 0.0, "tier": "off",
                               "well_class": classify_well(
                                   s, stn_srctype.get(s, ""))}
            else:
                w, t = flow_gw.plausibility(xy, (sx, sy), k=GW_PLUME_K) \
                    if isinstance(flow_gw, UniformFlowAssumption) else (
                        (1.0, "1") if flow_gw.upgradient_of(xy, (sx, sy))
                        else (0.0, "4"))
                wc = classify_well(s, stn_srctype.get(s, ""))
                gw_tiers[s] = {"w": round(w, 3), "tier": t, "well_class": wc}
                # Production wells: pumping blurs the sampling location —
                # report the BEST tier within the declared capture radius
                # alongside the wellhead tier (approved 2026-08-12).
                # Counting stays by the wellhead tier (conservative).
                if wc == "production" and \
                        isinstance(flow_gw, UniformFlowAssumption):
                    _, t_best = flow_gw.plausibility(
                        xy, (sx, sy), k=GW_PLUME_K,
                        lateral_slack_m=PRODUCTION_CAPTURE_RADIUS_M)
                    if t_best != t:
                        gw_tiers[s]["tier_best"] = t_best
                if t in ("1", "2"):
                    down_all.append(s)
        gw_fringe = [s for s, v in gw_tiers.items() if v["tier"] == "3"
                     and stn_total[s] >= MIN_SIGNAL_UG_L]

        # Declared water transfers (pumping etc.): a station fed from a stream
        # reach that lies on the candidate's runoff path inherits downgradient
        # status. Anthropogenic pathway — invisible to the DEM, so it must be
        # declared in region.json with provenance. Marked and kept out of the
        # attenuation regression (pond residence time breaks transport decay).
        transfer_fed = {}
        for tr in region.get("water_transfers", []):
            kind = tr.get("kind", "transfer")
            for s in tr.get("to_stations", []):
                if s not in stn_xy or s in down_all:
                    continue
                if kind == "pumping":
                    # pumping draws from an adjacent stream reach — valid only
                    # if that reach lies on the candidate's runoff path
                    if not dem_active:
                        continue
                    reach = float(tr.get("max_reach_m", 2000))
                    hit = flow_surface.near_path((sx, sy), stn_xy[s], reach)
                    if hit is None:
                        continue
                    transfer_fed[s] = {"path_distance_m": hit[0],
                                       "offset_m": hit[1], "kind": kind}
                else:
                    # piped/declared endpoint transfer (e.g. sewer→WWTP→
                    # reservoirs): geometry-independent by nature
                    transfer_fed[s] = {"path_distance_m": None,
                                       "offset_m": None, "kind": kind}
                down_all.append(s)

        # Channel-adjacent groundwater stations are CASCADE candidates
        # (stream → bank infiltration → GW, the Tirli/D1 mechanism). The
        # chain pathway competes with the direct-plume explanation, so the
        # scan covers ALL gw stations with signal — including ones that are
        # nominally downgradient under the assumed direction (user feedback
        # 2026-08-12, item 4). A production well's capture zone blurs its
        # geometry: the declared capture radius extends the 300 m adjacency
        # threshold, and such a hit is marked coarse. A chain candidate is
        # neither direct evidence nor counter-evidence (decided by paired
        # sampling) — it is pulled out of the counted downgradient pool.
        cascade_candidates = []
        cascade_meta = {}
        if dem_active:
            for s in stn_xy:
                if stn_domain.get(s) != "groundwater" or \
                        stn_total[s] < MIN_SIGNAL_UG_L or _in_any_site(s) or \
                        s == src.get("anchor_station"):
                    continue
                wc = classify_well(s, stn_srctype.get(s, ""))
                slack = (PRODUCTION_CAPTURE_RADIUS_M if wc == "production"
                         else 0.0)
                hit = flow_surface.near_path((sx, sy), stn_xy[s],
                                             300.0 + slack)
                if hit is not None:
                    cascade_candidates.append(s)
                    cascade_meta[s] = {
                        "path_km": round(hit[0] / 1000.0, 2),
                        "offset_m": int(round(hit[1])),
                        "well_class": wc,
                        "coarse": bool(hit[1] > 300.0),
                    }
            down_all = [s for s in down_all if s not in cascade_meta]

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
            base = max(0.0, math.log10(stn_total[s] / MIN_SIGNAL_UG_L))
            # groundwater stations: weight is further scaled by plume
            # plausibility (approved 2026-07-27) — a flank station carries
            # less chemical-evidence weight than an on-line station
            if s in gw_tiers:
                base *= gw_tiers[s]["w"]
            return base
        w_total = sum(_w(s) for s in down)
        w_hits = sum(_w(s) for s in chem_hits)
        # kept for backend/audit use only — never shown as an "XX% match"
        # (methodology v1.0 §7; user round 2026-08-12)
        chem_share_weighted = (w_hits / w_total) if w_total > 0 else 0.0

        # composition similarity (0-1): median of the matched profiles'
        # similarity scores over the counted downgradient stations. This is a
        # similarity measure, NOT a probability and NOT a station count.
        _sims = []
        if not matches.empty:
            for s in chem_hits:
                rows = matches[(matches["station"] == s)
                               & (matches["profile_key"].isin(expected))]
                if not rows.empty:
                    _sims.append(float(rows["score"].max()) / 100.0)
        chem_similarity_median = (round(sorted(_sims)[len(_sims) // 2], 2)
                                  if _sims else None)

        # signal quality: how reliable are the fingerprints this rests on.
        # Uses the two thresholds already declared in config — no new ones.
        if down:
            _reliable = sum(1 for s in down
                            if stn_total[s] >= CLUSTER_MIN_SIGNAL_UG_L)
            _rel_share = _reliable / len(down)
            signal_quality = ("גבוהה" if _rel_share >= 0.75 else
                              "בינונית" if _rel_share >= 0.4 else "נמוכה")
        else:
            signal_quality = "נמוכה"

        # --- attenuation evidence ---
        # Preferred basis: DEM path distances over surface stations on the
        # candidate's runoff path (+ the confirmed anchor at distance 0).
        # Falls back to coarse projected distances when DEM is unavailable.
        anchor = src.get("anchor_station")
        attenuation = {"n": 0, "r_conc": None, "r_precursor": None,
                       "note_he": "", "basis": "projected"}
        atten_pts = []
        _momentary = {s for s, o in outfalls.items() if o.get("momentary")}
        if dem_active:
            for s in down:
                if stn_domain.get(s) != "surface" or s in transfer_fed \
                        or s in _momentary or _in_site(s):
                    continue
                d = flow_surface.downgradient_distance_m(stn_xy[s], (sx, sy))
                if d is not None and d > 0:
                    atten_pts.append((d, s))
            # Stream-series head: at-site stations whose declared outfall is
            # the STREAM (e.g. בריכה-200). A sewer-routed pond (בריכה-1500)
            # must NOT head the stream series — its load leaves via the WWTP
            # line (corrected per user 2026-07-27).
            for s in stn_total:
                # momentary-outlet measurements are excluded from load
                # regressions BY DECLARATION — the head insertion must
                # honor that too (bug surfaced by the junction scan,
                # 2026-08-11: a momentary outlet re-entered as series head)
                if _outfall_to(s) == "stream" \
                        and not outfalls.get(s, {}).get("momentary") \
                        and s not in {x for _, x in atten_pts}:
                    d0 = math.hypot(stn_xy[s][0] - sx, stn_xy[s][1] - sy)
                    if d0 <= 1000:
                        atten_pts.append((max(d0, 100.0), s))
            if len(atten_pts) >= _ATTEN_MIN_N:
                attenuation["basis"] = "path_dem"
        if len(atten_pts) < _ATTEN_MIN_N:
            atten_pts = [(flow_gw.downgradient_distance_m(stn_xy[s], (sx, sy)), s)
                         for s in down]
            atten_pts = [(d, s) for d, s in atten_pts if d and d > 0]
            attenuation["basis"] = "projected"
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

        # --- junction-load test (approved 2026-08-11) ---
        # Runs on true path distances only; the reference profile is the
        # confirmed anchor, or failing that the most source-adjacent
        # signal station.
        junction_findings = []
        if attenuation["basis"] == "path_dem" and len(atten_pts) >= 3:
            series = sorted(
                [{"km": d / 1000, "station": s, "sigma": stn_total[s]}
                 for d, s in atten_pts], key=lambda x: x["km"])
            head_ref = anchor if (anchor and anchor in fingerprint.index) \
                else next(iter(sorted(
                    (s for s in stn_xy
                     if stn_total[s] >= MIN_SIGNAL_UG_L
                     and s in fingerprint.index),
                    key=lambda s: math.hypot(stn_xy[s][0] - sx,
                                             stn_xy[s][1] - sy))), None)
            if head_ref:
                junction_findings = junction_scan(series, fingerprint, head_ref)

        emission = src.get("emission_evidence", [])
        ev_tier = src.get("evidence_tier", "none")

        n_surf_down = sum(1 for s in down if stn_domain.get(s) == "surface")
        n_gw_down = len(down) - n_surf_down
        _basis_he = ("מרחק-מסלול DEM" if attenuation["basis"] == "path_dem"
                     else "מרחק מוטל — גס")

        evidence_for, evidence_against = [], []
        if anchor and anchor in stn_total:
            evidence_for.append(
                f"תחנת עוגן מאושרת באתר: \"{anchor}\" "
                f"(Σ={stn_total[anchor]:,.1f} µg/L) — {src.get('anchor_provenance', 'אישור משתמש')}")
        if down:
            _parts = []
            if n_surf_down:
                _parts.append(f"עילי: {n_surf_down} ({flow_surface.describe_he()})")
            if n_gw_down:
                _t1 = sum(1 for s in down if gw_tiers.get(s, {}).get("tier") == "1")
                _t2 = n_gw_down - _t1
                _parts.append(
                    f"תהום: {n_gw_down} במדרגות 1-2 (ליבה {_t1}/אגף {_t2}, "
                    f"k={GW_PLUME_K}) — {flow_gw.describe_he()}")
            evidence_for.append(
                f"{len(down)} תחנות פגועות (מעל סף {MIN_SIGNAL_UG_L} µg/L) במורד — "
                + " | ".join(_parts))
        if gw_fringe:
            evidence_for.append(
                f"שולי-עננה (מדרגה 3, תמיכה חלשה בלבד): {', '.join(gw_fringe)}")
        _tf_pump = [s for s in transfer_fed if s in down
                    and transfer_fed[s]["kind"] == "pumping"]
        _tf_pipe = [s for s in transfer_fed if s in down
                    and transfer_fed[s]["kind"] != "pumping"]
        if _tf_pump:
            evidence_for.append(
                f"{len(_tf_pump)} תחנות מוזנות-שאיבה ממקטע נחל שבמורד האתר "
                f"({', '.join(_tf_pump)}) — נתיב אנתרופוגני מוצהר; "
                f"אינן ברגרסיית הדעיכה")
        if _tf_pipe:
            evidence_for.append(
                f"{len(_tf_pipe)} תחנות מוזנות-נתיב-מתועל (ביוב←מט\"ש←קולחים): "
                f"{', '.join(_tf_pipe)} — הצהרת משתמש; ראו תחזית P1")
        if cascade_candidates:
            _casc_parts = []
            for s in cascade_candidates:
                m = cascade_meta.get(s, {})
                tag = " (אזור-לכידה, גס)" if m.get("coarse") else ""
                _casc_parts.append(f"{s}{tag}")
            evidence_for.append(
                f"מועמדי-שרשרת (קידוחים צמודי-ערוץ למסלול הנגר; "
                f"בקידוח-הפקה — עד רדיוס-הלכידה המוצהר): "
                f"{', '.join(_casc_parts)} — עקבי עם החדרת-גדות; "
                f"לא נספרים כראיה ישירה ולא כראיית-נגד — מוכרע בדיגום מזווג")
        if chem_hits:
            evidence_for.append(
                f"ב-{len(chem_hits)} מתוך {len(down)} תחנות המורד הנספרות, "
                f"הפרופיל הצפוי הוא הקרוב ביותר להרכב שנמדד"
                + (f" (דמיון חציוני בהרכב: {chem_similarity_median})"
                   if chem_similarity_median is not None else "")
                + " — עקבי עם המקור, אינו מוכיח אותו")
        if attenuation["r_conc"] is not None:
            r = attenuation["r_conc"]
            if r <= -_ATTEN_R_THRESHOLD:
                attenuation["note_he"] = "דפוס דעיכה עקבי עם מקור באתר"
                evidence_for.append(
                    f"דעיכת ריכוז במורד (Spearman r={r}, n={attenuation['n']}, "
                    f"{_basis_he}) — עקבי עם מקור באתר")
            elif r >= _ATTEN_R_THRESHOLD:
                attenuation["note_he"] = "ריכוז עולה במורד — מקור נוסף אפשרי"
                evidence_against.append(
                    f"ריכוז עולה עם המרחק במורד (r={r}, n={attenuation['n']}, "
                    f"{_basis_he}) — מרמז על מקור נוסף בין הנקודות")
            else:
                attenuation["note_he"] = "דפוס מרחבי לא חד-משמעי"
        if attenuation.get("r_precursor") is not None and \
                attenuation["r_precursor"] <= -_ATTEN_R_THRESHOLD:
            evidence_for.append(
                f"הזדקנות פרופיל נצפית: נתח קדם-חומרים יורד במורד "
                f"(r={attenuation['r_precursor']}) — עקבי עם התרחקות מהמקור")
        if junction_findings:
            # one line per suspected segment, in plain words; the
            # non-simultaneity caveat is stated ONCE for the whole group
            # rather than repeated on every line (report-language round §6.6)
            for jf in junction_findings:
                evidence_against.append(
                    f"במקטע שבין \"{jf['segment'][0]}\" ל\"{jf['segment'][1]}\" "
                    f"({jf['km'][0]:.1f}–{jf['km'][1]:.1f} ק\"מ) ניכרת תוספת "
                    f"זיהום שאינה מוסברת היטב על ידי המקור שבמעלה: "
                    + "; ".join(jf["signals"]) + ".")
            _sem = region.get("dataset_semantics", {})
            if _sem.get("simultaneous") is False:
                evidence_against.append(
                    "הערה לכל המקטעים החשודים: התחנות לא נדגמו בו-זמנית, "
                    "ולכן חלק מההפרש בין מקטעים עשוי לנבוע מהפרשי מועד ולא "
                    "מתוספת זיהום.")
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
                     and not _in_site(s)
                     and s not in cascade_candidates
                     and s in set(matches[matches["rank"] == 1]["station"])
                     and set(matches[(matches["station"] == s)]["profile_key"]) & expected]
        # Stations under a declared transfer HYPOTHESIS (not yet confirmed)
        # are conditional counter-evidence: similar profile off-gradient, but
        # a pending explanation exists. Reported separately — not silenced,
        # not counted as resolved.
        _hyp_stations = {s for h in region.get("transfer_hypotheses", [])
                         for s in h.get("to_stations", [])}
        conditional = [s for s in strong_up if s in _hyp_stations]
        strong_up = [s for s in strong_up if s not in _hyp_stations]
        # Voided groundwater axis: "not downgradient" is itself a geometric
        # verdict, so a well with a similar profile is neither support nor
        # counter-evidence here — it is an ungraded observation.
        gw_ungraded = []
        if gw_axis_off:
            gw_ungraded = [s for s in strong_up
                           if stn_domain.get(s) == "groundwater"]
            strong_up = [s for s in strong_up if s not in gw_ungraded]
        # Production wells: capture geometry is soft (pumping radius
        # undefined), so "similar profile elsewhere" is NOT counted as
        # counter-evidence for them (approved 2026-08-12). Listed
        # separately as an area-screen observation.
        production_soft = [s for s in strong_up
                           if classify_well(s, stn_srctype.get(s, ""))
                           == "production"]
        strong_up = [s for s in strong_up if s not in production_soft]
        if strong_up:
            evidence_against.append(
                f"תחנות שאינן במורד האתר מציגות פרופיל דומה ({', '.join(strong_up[:3])}"
                + ("..." if len(strong_up) > 3 else "")
                + ") — עקבי גם עם מקור אחר/נוסף")
        if conditional:
            evidence_against.append(
                f"ראיית-נגד מותנית: {', '.join(conditional)} — פרופיל דומה שלא במורד, "
                f"אך קיים חשד מוצהר להזנת-שאיבה (בבדיקה); אם יאושר — יעברו למורד")
        if gw_ungraded:
            evidence_for.append(
                f"תצפית ללא הכרעה גיאומטרית: קידוחים עם פרופיל דומה — "
                f"{', '.join(gw_ungraded[:3])}"
                + ("..." if len(gw_ungraded) > 3 else "")
                + " — ציר-התהום הגיאומטרי מבוטל בתיק זה, ולכן אין באלה תמיכה "
                  "ואין בהם ראיית-נגד")
        if production_soft:
            evidence_for.append(
                f"תצפית-סריקה (לא ראיה ולא ראיית-נגד): קידוחי-הפקה עם פרופיל "
                f"דומה שלא במורד — {', '.join(production_soft[:3])}"
                + ("..." if len(production_soft) > 3 else "")
                + f" — דגימתם משקללת אזור-לכידה בלתי-מוגדר; "
                f"מומלץ חיבוק בקידוחי-ניטור")

        # Tier suggestion with the assumed-flow cap. The cap is keyed to the
        # weakest flow tier the evidence relies on: surface may be DEM-derived,
        # but groundwater stays an assumption until measured heads arrive.
        _gw_assumed = flow_gw.tier == ASSUMED and n_gw_down > 0
        _hydro_all_derived = (not _gw_assumed) and (
            not dem_active or n_surf_down > 0 or n_gw_down > 0)
        # --- chemical-support rating (methodology v1.0 §7) ---
        # Rule-based and anchored to the SAME threshold that feeds the tier
        # (chem_share >= 0.3), so the report can never show "low chemical
        # support" while the engine counts the chemical axis as present.
        _chem_axis = chem_share >= 0.3
        if not down:
            chem_support = "אין די ראיות"
        elif not _chem_axis:
            chem_support = "נמוכה"
        elif (chem_similarity_median is not None
                and chem_similarity_median >= 0.8
                and signal_quality == "גבוהה"
                and chem_share >= 0.6):
            chem_support = "גבוהה"
        else:
            chem_support = "בינונית"

        # weathering fit — path level only; there is no per-station basis
        _rp = attenuation.get("r_precursor")
        if _rp is None or attenuation.get("n", 0) < 3:
            weathering_fit = "לא ניתן להעריך"
        elif _rp <= -0.6:
            weathering_fit = "גבוהה"
        elif _rp <= -_ATTEN_R_THRESHOLD:
            weathering_fit = "בינונית"
        else:
            weathering_fit = "נמוכה"

        # --- tier (vocabulary v1.0; thresholds unchanged) ---
        axes = sum([bool(down), _chem_axis, bool(emission)])
        if axes >= 3 and _hydro_all_derived:
            tier = "מועמד מרכזי"
        elif axes >= 2:
            tier = "מועמד משני"
            if axes == 3 and _gw_assumed:
                tier = ("מועמד משני (תקרה: זרימת התהום מונחת; "
                        "העילי נגזר-DEM)" if dem_active and n_surf_down
                        else "מועמד משני (תקרה: כיוון זרימה מונח, לא מדוד)")
        elif axes == 1:
            tier = "מקור אפשרי"
        else:
            tier = "לא נתמך בשלב זה"

        results.append({
            "id": src.get("id"), "name_he": src.get("name_he"),
            "itm": (sx, sy), "kind": src.get("kind"),
            "location_quality": src.get("location_quality", ""),
            "site_members": site_members,
            "tier": tier,
            "n_downgradient": len(down), "downgradient": down,
            "n_surface_down": n_surf_down, "n_gw_down": n_gw_down,
            "transfer_fed": transfer_fed,
            "conditional_counter": conditional,
            "production_soft_similar": production_soft,
            "gw_tiers": gw_tiers, "gw_fringe": gw_fringe,
            "cascade_candidates": cascade_candidates,
            "cascade_meta": cascade_meta,
            "weak_downgradient": weak_down,
            "chem_share": round(chem_share, 2),
            "chem_share_weighted": round(chem_share_weighted, 2),
            "chem_similarity_median": chem_similarity_median,
            "weathering_fit": weathering_fit,
            "signal_quality": signal_quality,
            "chem_support": chem_support,
            "chem_hits": chem_hits,
            "attenuation": attenuation,
            "junction_findings": junction_findings,
            "anchor_station": anchor,
            "emission_evidence": emission,
            "expert_determination_he": src.get("expert_determination_he"),
            "expert_claim_id": src.get("expert_claim_id"),
            "flow_caveat": (
                f"עילי: {flow_surface.describe_he()} | "
                + (f"תהום: ציר גיאומטרי מבוטל — {gw_axis_off_he}"
                   if gw_axis_off else f"תהום: {flow_gw.describe_he()}")),
            "gw_axis_off": gw_axis_off,
            "gw_axis_off_he": gw_axis_off_he,
            "gw_ungraded": gw_ungraded,
            "evidence_for": evidence_for,
            "evidence_against": evidence_against,
            "would_refute": [
                "מפלסים מדודים המראים כיוון זרימה שונה מההנחה",
                "פרופיל דיגום בתחנה צמודה לאתר ללא חתימת הפרופילים הצפויים",
                "בירור שמערך הכיבוי באתר אינו/לא היה מבוסס קצף פלואורי (AFFF)",
            ],
        })
    return results
