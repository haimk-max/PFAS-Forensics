"""source_profiles.py — Reference PFAS source-type fingerprints & matching.

Screening-level heuristic profiles compiled from the PFAS source-typology
literature (ITRC PFAS Technical Guidance; Barzen-Hanson et al. 2017;
Houtz et al. 2013 — AFFF composition & transformation). Relative weights,
not measured standards: matching output is "consistent with" (עקבי עם) —
NEVER a source determination.

Weathering: precursors (FOSA, 6:2FT, 8:2FTS) degrade along the transport
path and short chains travel faster, so most source types carry a "fresh"
and a "weathered" variant. A weathered match far downgradient and a fresh
match near the source are BOTH consistent with the same source type.

Matching math is the existing unit-vector cosine — no new machinery.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class SourceProfile:
    key: str
    name_he: str
    state: str                      # "fresh" | "weathered" | "generic"
    weights: dict[str, float]       # relative composition, any scale
    markers: list[str] = field(default_factory=list)  # diagnostic congeners
    notes_he: str = ""


# Screening-level relative compositions. [heuristic — see module docstring]
PROFILES: list[SourceProfile] = [
    SourceProfile(
        key="afff_ecf_fresh", state="fresh",
        name_he="AFFF ותיק (ECF) — טרי",
        weights={"PFOS": 40, "PFHxS": 15, "6:2FT": 10, "82FTS": 8, "FOSA": 6,
                 "PFBS": 5, "PFHxA": 5, "PFOA": 4, "PFHpS": 3, "PFPeS": 2,
                 "PFDS": 2},
        markers=["FOSA", "82FTS", "PFHxS"],
        notes_he="קצף כיבוי מבוסס ECF (דור ישן): דומיננטיות PFOS+PFHxS עם קדם-חומרים נוכחים.",
    ),
    SourceProfile(
        key="afff_ecf_weathered", state="weathered",
        name_he="AFFF ותיק (ECF) — בלוי במורד",
        weights={"PFOS": 45, "PFHxS": 20, "PFBS": 8, "PFHxA": 10, "PFOA": 8,
                 "PFPeA": 4, "PFHpS": 2, "FOSA": 1, "6:2FT": 1, "82FTS": 1},
        markers=["PFHxS"],
        notes_he="אותו מקור לאחר הסעה: קדם-חומרים התפרקו, סולפונטים יציבים שולטים.",
    ),
    SourceProfile(
        key="afff_ft_modern", state="fresh",
        name_he="AFFF פלואורוטלומרי (מודרני)",
        weights={"6:2FT": 35, "82FTS": 12, "PFHxA": 18, "PFPeA": 10,
                 "PFBA": 8, "PFOA": 6, "PFBS": 5, "PFOS": 3, "PFHpA": 3},
        markers=["6:2FT", "82FTS"],
        notes_he="קצף דור חדש (אחרי ~2003): טלומרים ושרשראות קצרות, PFOS שולי.",
    ),
    SourceProfile(
        key="wwtp_effluent", state="generic",
        name_he="קולחי מט\"ש / שפכים מוניציפליים",
        weights={"PFOA": 20, "PFHxA": 17, "PFBA": 14, "PFPeA": 13,
                 "PFBS": 10, "PFOS": 9, "PFHpA": 8, "PFNA": 4, "PFDA": 3,
                 "PFHxS": 2},
        markers=[],
        notes_he="העשרת שרשראות קצרות ו-PFOA>PFOS — דפוס אופייני לקולחים.",
    ),
    SourceProfile(
        key="landfill_leachate", state="generic",
        name_he="תשטיפי מטמנה",
        weights={"6:2FT": 20, "PFBA": 15, "PFHxA": 15, "PFPeA": 12,
                 "PFOA": 12, "PFBS": 10, "PFOS": 6, "PFHpA": 6, "PFNA": 2},
        markers=["6:2FT"],
        notes_he="6:2FT גבוה + שרשראות קצרות; יחס A/S גבוה.",
    ),
    SourceProfile(
        key="fluoropolymer_industry", state="generic",
        name_he="תעשיית ציפויים/פלואורופולימרים",
        weights={"PFOA": 45, "PFNA": 12, "PFHxA": 10, "PFDA": 8, "PFHpA": 8,
                 "PFUnA": 5, "PFBA": 5, "PFOS": 3, "PFDoA": 2},
        markers=["PFNA", "PFUnA"],
        notes_he="דומיננטיות קרבוקסילטים (PFOA וארוכים) — עיבוד פולימרים/טקסטיל/נייר.",
    ),
    SourceProfile(
        key="diffuse_background", state="generic",
        name_he="רקע מפוזר (אטמוספרי/חקלאי)",
        weights={"PFOA": 20, "PFOS": 18, "PFHxA": 12, "PFBA": 10,
                 "PFPeA": 8, "PFHxS": 8, "PFBS": 7, "PFHpA": 6, "PFNA": 5,
                 "PFDA": 4},
        markers=[],
        notes_he="פיזור רחב ללא דומיננט חד — שקיעה אטמוספרית, בוצה, השקיה בקולחים.",
    ),
]


def _unit(vec: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(vec)
    return vec / n if n > 0 else vec


def match_profiles(fingerprint: pd.DataFrame, top_n: int = 2,
                   min_score: float = 50.0) -> pd.DataFrame:
    """Cosine-match station fingerprints against all reference profiles.

    fingerprint: stations × compounds (%) — output of build_fingerprint_matrix.
    Returns long DataFrame: station, rank, profile_key, profile_he, state,
    score (0-100). Stations with empty fingerprints are omitted.
    """
    rows = []
    compounds = list(fingerprint.columns)
    prof_vecs = {}
    for p in PROFILES:
        v = np.array([p.weights.get(c, 0.0) for c in compounds], dtype=float)
        if v.sum() > 0:
            prof_vecs[p.key] = (_unit(v), p)

    for station, row in fingerprint.iterrows():
        sv = _unit(row.values.astype(float))
        if not sv.any():
            continue
        scores = [(float(np.dot(sv, pv) * 100), p) for pv, p in prof_vecs.values()]
        scores.sort(key=lambda t: -t[0])
        for rank, (score, p) in enumerate(scores[:top_n], start=1):
            if score < min_score and rank > 1:
                continue
            rows.append({
                "station": station, "rank": rank, "profile_key": p.key,
                "profile_he": p.name_he, "state": p.state,
                "score": round(score, 1),
            })
    return pd.DataFrame(rows)


def marker_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Data-driven diagnostic flags per station (independent of matching).

    df: processed measurement DataFrame (station_name, compound, concentration).
    Flags raised only on detected (>0) concentrations.
    """
    out = []
    for station, g in df.groupby("station_name"):
        detected = set(g.loc[g["concentration"] > 0, "compound"].str.upper())
        flags = []
        precursors = detected & {"FOSA", "82FTS", "6:2FT"}
        if precursors:
            flags.append("סמני קדם-חומרים פעילים (" + ", ".join(sorted(precursors)) +
                         ") — עקביים עם מקור קרוב/טרי")
        if {"PFOS", "PFHXS"} <= detected:
            flags.append("צמד PFOS+PFHxS — עקבי עם AFFF מסוג ECF")
        if flags:
            out.append({"station": station, "flags": flags})
    return pd.DataFrame(out)
