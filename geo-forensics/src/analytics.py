"""
analytics.py - ניתוח סטטיסטי וכימי
====================================
מודול לחישוב:
1. Cosine Similarity בין תחנות
2. סיכום ממצאים אוטומטי
"""

import numpy as np
import pandas as pd

from src.contaminant_groups import ContaminantGroup
from src.data_model import build_fingerprint_matrix, calc_total_concentration


def cosine_similarity_matrix(df: pd.DataFrame, group: ContaminantGroup) -> pd.DataFrame:
    """
    מחשב מטריצת Cosine Similarity בין כל זוגות התחנות.

    הפרופיל הכימי של כל תחנה (אחוזי תרכובות) נחשב כווקטור,
    והדמיון מחושב על בסיס הזווית ביניהם.

    Args:
        df: DataFrame מעובד
        group: קבוצת מזהמים

    Returns:
        DataFrame מרובע: שורות ועמודות = תחנות, ערכים = % דמיון (0-100)
    """
    fingerprint = build_fingerprint_matrix(df, group)
    matrix = fingerprint.values

    # Normalize rows to unit vectors
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1  # avoid division by zero
    unit = matrix / norms

    # Cosine similarity = dot product of unit vectors
    sim = unit @ unit.T

    # Clip to [0, 1] to avoid floating point artifacts
    sim = np.clip(sim, 0, 1) * 100

    return pd.DataFrame(sim, index=fingerprint.index, columns=fingerprint.index)


def rank_stations_by_similarity(
    sim_matrix: pd.DataFrame, reference_station: str, top_n: int = 5
) -> pd.DataFrame:
    """
    מדרג תחנות לפי דמיון לתחנת ייחוס.

    Args:
        sim_matrix: מטריצת Cosine Similarity
        reference_station: שם תחנת הייחוס
        top_n: כמה תחנות דומות להציג

    Returns:
        DataFrame עם תחנות מדורגות לפי דמיון
    """
    if reference_station not in sim_matrix.index:
        raise KeyError(f"תחנה '{reference_station}' לא נמצאה במטריצה")

    scores = sim_matrix[reference_station].drop(reference_station).sort_values(ascending=False)
    result = scores.head(top_n).reset_index()
    result.columns = ["station_name", "similarity_pct"]
    return result


def generate_findings_summary(
    df: pd.DataFrame,
    group: ContaminantGroup,
    sim_matrix: pd.DataFrame,
    pca_data: dict | None = None,
) -> list[str]:
    """
    מייצר סיכום ממצאים אוטומטי לדוח.

    Returns:
        רשימת משפטי סיכום בעברית
    """
    findings = []
    fingerprint = build_fingerprint_matrix(df, group)
    totals = calc_total_concentration(df, group)

    # 1. Find station with highest concentration
    if not totals.empty:
        max_row = totals.loc[totals["total_concentration"].idxmax()]
        findings.append(
            f"<b>ריכוז הגבוה ביותר:</b> תחנה \"{max_row['station_name']}\" "
            f"({max_row['source_type']}) עם ריכוז כולל של "
            f"{max_row['total_concentration']:.2f} {group.unit}."
        )

    # 2. Dominant compound across all stations
    if not fingerprint.empty:
        mean_profile = fingerprint.mean()
        dominant = mean_profile.idxmax()
        dominant_pct = mean_profile.max()
        findings.append(
            f"<b>תרכובת דומיננטית:</b> {dominant} מהווה בממוצע "
            f"{dominant_pct:.1f}% מסך הריכוזים בכל התחנות."
        )

    # 3. High similarity clusters
    if not sim_matrix.empty:
        n = len(sim_matrix)
        high_sim_pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                val = sim_matrix.iloc[i, j]
                if val >= 95:
                    high_sim_pairs.append(
                        (sim_matrix.index[i], sim_matrix.columns[j], val)
                    )

        if high_sim_pairs:
            pair_strs = [f"\"{a}\" ↔ \"{b}\" ({v:.0f}%)" for a, b, v in high_sim_pairs[:5]]
            findings.append(
                f"<b>קורלציה חזקה ({len(high_sim_pairs)} זוגות ≥95%):</b> "
                f"{', '.join(pair_strs)}."
            )

        # 4. Find zero-data stations and outliers separately
        zero_stations = []
        low_sim_stations = []
        for i in range(n):
            # Check if station has all-zero similarity (except self)
            non_self_vals = [sim_matrix.iloc[i, j] for j in range(n) if j != i]
            if all(v == 0 for v in non_self_vals):
                zero_stations.append(sim_matrix.index[i])
            else:
                row_mean = sum(non_self_vals) / len(non_self_vals) if non_self_vals else 100
                if row_mean < 50:
                    low_sim_stations.append((sim_matrix.index[i], row_mean))

        if zero_stations:
            zero_strs = [f"\"{s}\"" for s in zero_stations]
            findings.append(
                f"<b>תחנות ללא ריכוזים משמעותיים ({'< LOD'}):</b> "
                f"{', '.join(zero_strs)} — "
                f"כל הריכוזים מתחת לסף הזיהוי. תחנות אלו לא נכללו בניתוח ההשוואתי."
            )

        if low_sim_stations:
            outlier_strs = [f"\"{s}\" (ממוצע דמיון {v:.0f}%)" for s, v in low_sim_stations]
            findings.append(
                f"<b>חריגים בהרכב הכימי:</b> "
                f"התחנות הבאות מציגות פרופיל שונה מרוב האחרות: "
                f"{', '.join(outlier_strs)}. "
                f"ייתכן שמדובר במקור זיהום נפרד או בתהליכי הנחתה (Retardation) "
                f"המשפיעים על ההרכב."
            )

    # 5. PCA cluster analysis
    if pca_data and len(pca_data.get("stations", [])) >= 2:
        var1 = pca_data["var_explained"][0] if len(pca_data["var_explained"]) > 0 else 0
        var2 = pca_data["var_explained"][1] if len(pca_data["var_explained"]) > 1 else 0
        total_var = var1 + var2
        n_pca = len(pca_data["stations"])

        # Identify clusters using simple distance-based grouping on PCA coords
        from scipy.cluster.hierarchy import fcluster, linkage as _linkage
        coords_arr = list(zip(pca_data["pc1"], pca_data["pc2"]))
        if len(coords_arr) >= 2:
            from scipy.spatial.distance import pdist
            dists = pdist(coords_arr)
            Z_pca = _linkage(dists, method='average')
            # Cut at 50% of max distance for meaningful clusters
            max_dist = Z_pca[-1, 2] if len(Z_pca) > 0 else 1.0
            cluster_labels = fcluster(Z_pca, t=max_dist * 0.35, criterion='distance')
            n_clusters = len(set(cluster_labels))
            clusters_dict = {}
            for idx, cl in enumerate(cluster_labels):
                clusters_dict.setdefault(cl, []).append(pca_data["stations"][idx])

            cluster_descs = []
            for cl_id, members in sorted(clusters_dict.items(), key=lambda x: -len(x[1])):
                if len(members) >= 2:
                    member_str = ", ".join(f"\"{m}\"" for m in members[:4])
                    if len(members) > 4:
                        member_str += f" ועוד {len(members) - 4}"
                    cluster_descs.append(f"אשכול ({len(members)} תחנות): {member_str}")
                else:
                    cluster_descs.append(f"בודדת: \"{members[0]}\"")

            findings.append(
                f"<b>ניתוח PCA — {n_clusters} אשכולות זוהו:</b> "
                f"שני הרכיבים הראשיים מסבירים {total_var:.1f}% מהשונות ({var1:.1f}% + {var2:.1f}%). "
                + " | ".join(cluster_descs) + "."
            )

    # Attenuation pattern
    if not totals.empty and len(totals) >= 3:
        sorted_totals = totals.sort_values("total_concentration", ascending=False)
        max_conc = sorted_totals.iloc[0]["total_concentration"]
        min_conc = sorted_totals.iloc[-1]["total_concentration"]
        if max_conc > 0 and min_conc > 0:
            ratio = max_conc / min_conc
            findings.append(
                f"<b>טווח ריכוזים:</b> יחס ריכוז מקסימלי/מינימלי = {ratio:.0f}x "
                f"(מ-{min_conc:.2f} עד {max_conc:.2f} {group.unit}), "
                f"המעיד על דעיכה (Attenuation) לאורך מסלולי הזרימה."
            )

    # 6. Station count and compounds
    n_stations = df["station_name"].nunique()
    n_compounds = df["compound"].nunique()
    n_sources = df["source_type"].nunique()
    findings.append(
        f"<b>היקף הסקר:</b> פריסת {n_stations} נקודות דיגום "
        f"ב-{n_sources} סוגי מקור, {n_compounds} תרכובות {group.name}."
    )

    return findings
