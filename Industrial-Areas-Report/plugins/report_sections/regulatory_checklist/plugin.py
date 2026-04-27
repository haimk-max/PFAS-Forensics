"""Regulatory checklist report section: family + attribution summary tables.

Lean v1: includes a non-binding general trend phrase per family computed from
raw data (first-half-mean vs second-half-mean). NOT a statistical test.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev
from typing import Dict, List

from core.contaminant_grouper import CONTAMINANT_GROUPS
from core.contracts import ReportContext
from core.pollution_index import index_label
from core.registry import register_plugin


def _general_trend_phrase(values_in_time_order: List[float]) -> str:
    """Heuristic, non-binding trend description (Hebrew). NOT statistical."""
    if len(values_in_time_order) < 4:
        return "אין מספיק נתונים"
    half = len(values_in_time_order) // 2
    first = values_in_time_order[:half]
    second = values_in_time_order[half:]
    if not first or not second:
        return "אין מספיק נתונים"
    avg_all = mean(values_in_time_order)
    if avg_all == 0:
        return "יציבות יחסית"
    cov = (pstdev(values_in_time_order) / avg_all) if avg_all > 0 else 0.0
    delta = (mean(second) - mean(first)) / abs(mean(first)) if mean(first) else 0.0
    if delta > 0.20:
        return "נטייה כללית לעלייה"
    if delta < -0.20:
        return "נטייה כללית לירידה"
    if cov > 0.30:
        return "תנודתיות"
    return "יציבות יחסית"


def _trend_per_family(raw: List[Dict]) -> Dict[str, str]:
    """Compute one general phrase per family from raw measurements."""
    from core.contaminant_grouper import ContaminantGrouper
    grouper = ContaminantGrouper()

    # group rows by family, then by date → max value (aggregate across wells/params)
    per_family_dates: Dict[str, Dict[str, float]] = defaultdict(dict)
    for row in raw:
        try:
            param = str(row["parameter"])
            date = str(row["date"])
            value = float(row["value"])
        except (KeyError, TypeError, ValueError):
            continue
        fam = grouper.classify(param) or "unclassified"
        prev = per_family_dates[fam].get(date, float("-inf"))
        if value > prev:
            per_family_dates[fam][date] = value

    out: Dict[str, str] = {}
    for fam, date_map in per_family_dates.items():
        ordered_vals = [v for _, v in sorted(date_map.items())]
        out[fam] = _general_trend_phrase(ordered_vals)
    return out


@register_plugin("report_section", name="regulatory_checklist")
class RegulatoryChecklistSection:
    """Static summary tables: families + attributions. Lean v1, no JS."""

    section_id: str = "regulatory_checklist"
    order: int = 4

    def render(self, ctx: ReportContext) -> str:
        prev = ctx.previous_context or {}
        raw = prev.get("raw_data", [])
        trends = _trend_per_family(raw)

        # ---- Table 1: contaminant families --------------------------------
        family_rows: List[str] = []
        for fr in ctx.family_reports:
            heb = CONTAMINANT_GROUPS.get(fr.family, {}).get("hebrew", fr.family)
            label = index_label(fr.max_index)
            trend_phrase = trends.get(fr.family, "—")
            n_wells = len(fr.wells_affected)
            family_rows.append(f"""
              <tr>
                <td>{heb}</td>
                <td><span class="idx-badge idx-{fr.max_index}">{fr.max_index}</span></td>
                <td>{label}</td>
                <td>{fr.dominant_contaminant or "—"}</td>
                <td>{trend_phrase}</td>
                <td>{n_wells}</td>
              </tr>""")

        if not family_rows:
            family_rows.append(
                '<tr><td colspan="6" style="text-align:center;color:#718096">'
                'לא נמצאו ממצאים בקבוצות הניטור</td></tr>'
            )

        # ---- Table 2: attribution candidates ------------------------------
        # Each facility may appear multiple times (once per family scored).
        # For the summary, keep the best-scoring entry per facility and
        # union the matched_families across all entries for that facility.
        best_per_facility: Dict[str, Dict] = {}
        for a in ctx.attributions:
            cur = best_per_facility.get(a.facility_id)
            if cur is None or a.score > cur["best"].score:
                best_per_facility.setdefault(a.facility_id, {
                    "best": a, "matched_union": set()
                })["best"] = a
            else:
                best_per_facility.setdefault(a.facility_id, {
                    "best": a, "matched_union": set()
                })
            best_per_facility[a.facility_id]["matched_union"].update(a.matched_families)

        ranked = sorted(
            best_per_facility.values(),
            key=lambda d: d["best"].score,
            reverse=True,
        )

        attr_rows: List[str] = []
        for entry in ranked[:8]:
            a = entry["best"]
            matched = sorted(entry["matched_union"])
            pct = round(a.score * 100)
            attr_rows.append(f"""
              <tr>
                <td>{a.facility_name}</td>
                <td>{pct}%</td>
                <td>{a.cautious_phrase}</td>
                <td><span class="tier-badge">דרג {a.tier}</span></td>
                <td>{", ".join(matched) if matched else "—"}</td>
              </tr>""")
        if not attr_rows:
            attr_rows.append(
                '<tr><td colspan="5" style="text-align:center;color:#718096">'
                'לא נמצאו מועמדים למקור</td></tr>'
            )

        return f"""
<section class="card">
  <h2>סיכום רגולטורי — קבוצות מזהמים ומועמדים למקור</h2>

  <h3>קבוצות מזהמים שנמדדו</h3>
  <table class="summary">
    <thead>
      <tr>
        <th>קבוצה</th>
        <th>אינדקס</th>
        <th>תיאור</th>
        <th>מזהם דומיננטי</th>
        <th>תיאור מגמה (כללי)</th>
        <th>מס' קידוחים</th>
      </tr>
    </thead>
    <tbody>{"".join(family_rows)}</tbody>
  </table>
  <p class="note">תיאור המגמה בעמודה זו הינו תיאורי וכללי בלבד, אינו ניתוח סטטיסטי מובהק. ניתוח מגמות מובהק יבוצע בגרסה הבאה (Mann-Kendall + Sen's slope).</p>

  <h3>מועמדים למקורות זיהום</h3>
  <table class="summary">
    <thead>
      <tr>
        <th>מתקן</th>
        <th>ציון</th>
        <th>סיווג זהיר</th>
        <th>דרג ענפי</th>
        <th>קבוצות תואמות</th>
      </tr>
    </thead>
    <tbody>{"".join(attr_rows)}</tbody>
  </table>
  <p class="note">הסיווג הזהיר נדרש משפטית בישראל: "מועמד ליבה" / "מועמד משני" / "רקע מקומי" — לעולם לא "המקור".</p>
</section>
"""
