"""generate_case_report.py — Sample CASE-FILE report (draft template).

The standalone professional product of an investigation case: key judgments
with calibrated confidence, the conceptual site model (sources→pathways→
receptors), strict facts/analysis separation, alternatives & uncertainties,
an action-items tracker, the investigation log, and a methodology manifest.

TEMPLATE STATUS: DRAFT — the 8-chapter structure is NOT yet approved
(user 2026-07-27: wants to read a sample first). The confidence scale
(גבוהה/בינונית/נמוכה + basis) IS approved.

Usage (from geo-forensics/):
    python generate_case_report.py hagit
"""

import html
import json
import os
import subprocess
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))

from config import GW_PLUME_K, MIN_SIGNAL_UG_L
from generate_review_report import _prepare, _wgs


def _esc(s):
    return html.escape(str(s))


def _load(path):
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _conf(level, basis):
    cls = {"גבוהה": "hi", "בינונית": "mid", "נמוכה": "lo"}[level]
    return (f'<span class="conf {cls}">ודאות {level}</span>'
            f'<span class="basis">על סמך: {_esc(basis)}</span>')


def _judgments(data):
    """Compose the key-judgments chapter from the case state."""
    region = data["region"]
    out = []
    for c in data["candidates"]:
        att = c["attenuation"]
        out.append((
            f"האתר \"{c['name_he']}\" מדורג <b>{c['tier']}</b> כמקור {region.get('name_he','')}. "
            f"{c['n_surface_down']} תחנות במורד-נגר מוכח, "
            f"{len(c.get('transfer_fed', {}))} מוזנות-נתיב מוצהר, "
            f"התאמה כימית משוקללת {c['chem_share_weighted']*100:.0f}%.",
            "גבוהה" if "ליבה" in c["tier"] else "בינונית",
            "עוגן-מקור מאושר + מסלול DEM + נתיבים מוצהרים + התאמת פרופילים",
        ))
        if att.get("r_precursor") is not None and att["r_precursor"] <= -0.4:
            out.append((
                f"הזדקנות-פרופיל נצפית לאורך מסלול-הנגר (r={att['r_precursor']}): "
                f"נתח קדם-החומרים יורד עם המרחק — עקבי עם הסעה מהאתר.",
                "בינונית",
                "מרחקי-מסלול DEM; חתך לא-בו-זמני",
            ))
        if c.get("cascade_candidates"):
            out.append((
                f"קידוחים צמודי-ערוץ ({', '.join(c['cascade_candidates'])}) מסווגים "
                f"מועמדי-שרשרת (נחל←החדרת-גדות←תהום); מבחן-ההבחנה הכימי מטה "
                f"להסעה תת-קרקעית — שאלת ההפיכוּת פתוחה.",
                "בינונית",
                "פרקציונציה כרומטוגרפית בחתך יחיד",
            ))
    for q in (region.get("open_questions") or []):
        if q.get("status") == "open" and q["id"].startswith("Q"):
            out.append((
                f"{q['title_he']}: {q['statement_he']}",
                "נמוכה",
                "שאלה פתוחה — " + q.get("provenance", ""),
            ))
    return out


_CSS = """
:root{--bg:#f5f3ee;--surface:#fff;--ink:#1c1f24;--ink2:#4a4f57;--ink3:#7d8189;
--line:#e2ddd2;--accent:#2a9d8f;--warn:#d97a2c;--ok:#2d8b5e;--high:#7a3d9e;--bad:#c64a3b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);direction:rtl;
font-family:Assistant,"Segoe UI",system-ui,sans-serif;line-height:1.65}
.wrap{max-width:1000px;margin:0 auto;padding:26px}
h1{font-size:1.65rem;margin:.2em 0}
h2{font-size:1.22rem;border-bottom:2px solid var(--accent);padding-bottom:6px;margin-top:2em}
.sub{color:var(--ink3);font-size:.9rem}
.draft{background:#7a3d9e;color:#fff;border-radius:6px;padding:10px 16px;font-weight:600;margin:12px 0}
.card{background:var(--surface);border:1px solid var(--line);border-radius:8px;
padding:16px 20px;margin:12px 0;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.jd{border-right:4px solid var(--accent);padding:10px 14px;margin:10px 0;background:#fff;border-radius:4px}
.conf{display:inline-block;border-radius:100px;padding:1px 10px;font-size:.78rem;font-weight:700;margin-left:8px}
.conf.hi{background:#e3f2e8;color:var(--ok)}.conf.mid{background:#fdf1e4;color:var(--warn)}
.conf.lo{background:#fbe9e7;color:var(--bad)}
.basis{font-size:.78rem;color:var(--ink3)}
table{width:100%;border-collapse:collapse;font-size:.87rem}
th,td{text-align:right;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--ink2)}
.ev{list-style:none;padding:0;margin:6px 0}.ev li{padding:4px 0;border-bottom:1px dashed var(--line);font-size:.9rem}
.for::before{content:"➕ ";color:var(--ok)}.against::before{content:"➖ ";color:var(--warn)}
.ref::before{content:"❓ ";color:var(--ink3)}
.fact{background:#f2f7f5;border-right:3px solid var(--accent);padding:8px 12px;margin:6px 0;font-size:.9rem}
.assume{background:#fdf6ec;border-right:3px solid var(--warn);padding:8px 12px;margin:6px 0;font-size:.9rem}
.pri-h{color:var(--bad);font-weight:700}.pri-m{color:var(--warn);font-weight:600}
.foot{color:var(--ink3);font-size:.78rem;margin-top:26px;text-align:center}
.chain{background:#fff;border:1px dashed var(--line);border-radius:8px;padding:14px 18px;
font-size:.95rem;text-align:center;direction:rtl;line-height:2.2}
.chain b{background:#fbe9e7;border-radius:4px;padding:2px 8px}
.chain span{background:#eef4fb;border-radius:4px;padding:2px 8px}
.chain i{background:#e3f2e8;border-radius:4px;padding:2px 8px;font-style:normal}
"""


def main(region_name):
    data = _prepare(region_name)
    region = data["region"]
    actions = _load(os.path.join(region["_base"], "actions.json"))
    basins = _load(os.path.join(region["_base"], "derived", "basins.json"))
    claims = data["claims"]

    git = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True,
                         cwd=os.path.dirname(__file__) or ".").stdout.strip()

    S = []
    S.append(f"<h1>תיק ממצאים — {_esc(region.get('name_he', region_name))}</h1>")
    S.append('<div class="draft">טיוטה לדוגמה — מבנה הדוח (8 פרקים) טרם קובע; '
             'הוגש לקריאת המומחה (2026-07-27). סולם-הוודאות מאושר.</div>')
    sem = region.get("dataset_semantics", {})
    S.append(f'<div class="sub">נתונים: {_esc(os.path.basename(region["measurement_file"]))} · '
             f'{_esc(sem.get("snapshot_rule",""))} · טווח {_esc(sem.get("date_span",""))} · '
             f'{data["n_stations"]} תחנות בתחום-התיק</div>')

    # 0 — key judgments
    S.append("<h2>0 · שיפוטי-מפתח</h2>")
    for txt, lvl, basis in _judgments(data):
        S.append(f'<div class="jd">{txt}<br>{_conf(lvl, basis)}</div>')

    # 1 — CSM
    S.append("<h2>1 · מודל האתר התפיסתי (מקורות ← נתיבים ← רצפטורים)</h2>")
    if region_name == "hagit":
        S.append("""<div class="chain">
<b>תחנת הכוח חגית</b> (עוגן: בריכה-1500, Σ=1,121)<br>
← <span>נתיב 1: בריכה-200 → נחל חגית → נחל דליה → הים</span> ← <i>תחנות הנחל; קידוחי-גדה (טירלי) בהחדרה</i><br>
← <span>נתיב 2 (עומס עיקרי): קו ביוב → מט"ש חוף הכרמל → קולחים</span> ← <i>מאגרי מעין-צבי → השקיה → תהום?</i><br>
← <span>נתיב 3: שאיבה מהנחל</span> ← <i>בריכות הדגים</i>
</div>""")
    else:
        S.append("""<div class="chain">
<b>חוות המכלים חח"י קיסריה</b> (אינדיקטור: נד חשמל רדוד, סמנים טריים)<br>
← <span>חלחול מקומי לתהום; זרימה מתכנסת לשקע-השאיבה (קריאת מפת 2023)</span> ← <i>קידוחי חדרה/מנשה/קיסריה</i>
</div>""")
    if basins:
        from collections import Counter
        cnt = Counter(basins["assignments"].values())
        S.append('<div class="sub">אגנים בתחום-התיק: ' +
                 " · ".join(f"{k}: {v}" for k, v in cnt.items()) +
                 f' — {_esc(basins["quality_note"])}</div>')

    # 2 — facts
    S.append("<h2>2 · עובדות (מדידות והצהרות מתועדות)</h2>")
    top = sorted(data["stations"], key=lambda s: -s["sigma"])[:8]
    S.append('<div class="card"><table><tr><th>תחנה</th><th>Σ (µg/L)</th><th>סוג</th><th>התאמה מובילה</th></tr>')
    for s in top:
        S.append(f"<tr><td>{_esc(s['name'])}</td><td>{s['sigma']:.3f}</td>"
                 f"<td>{_esc(s['source_type'])}</td><td>{_esc(s['profile'])} ({s['score']:.0f}%)</td></tr>")
    S.append("</table></div>")
    for name, o in (region.get("outfalls") or {}).items():
        S.append(f'<div class="fact"><b>{_esc(name)}</b> ← {_esc(o.get("to"))}'
                 + (f' · {_esc(o.get("history_he",""))}' if o.get("history_he") else "")
                 + f' <span class="basis">[{_esc(o.get("provenance",""))}]</span></div>')

    # 3 — analysis & evidence
    S.append("<h2>3 · ניתוח וראיות</h2>")
    for c in data["candidates"]:
        S.append(f'<div class="card"><b>{_esc(c["name_he"])}</b> — {_esc(c["tier"])}'
                 f'<div class="sub">{_esc(c["flow_caveat"])}</div><ul class="ev">')
        for e in c["evidence_for"]:
            S.append(f'<li class="for">{_esc(e)}</li>')
        S.append("</ul></div>")

    # 4 — alternatives & uncertainties
    S.append("<h2>4 · הסברים חלופיים, אי-ודאויות והנחות פעילות</h2>")
    for c in data["candidates"]:
        S.append('<div class="card"><ul class="ev">')
        for e in c["evidence_against"] or ["(אין ראיות-נגד פעילות)"]:
            S.append(f'<li class="against">{_esc(e)}</li>')
        for e in c["would_refute"]:
            S.append(f'<li class="ref">{_esc(e)}</li>')
        S.append("</ul></div>")
    for cl in (claims["claims"] if claims else []):
        if cl["type"] == "assumption" and cl["status"] not in ("resolved",):
            S.append(f'<div class="assume"><b>{cl["id"]} · {_esc(cl["title_he"])}</b> — '
                     f'{_esc(cl["statement_he"])} <span class="basis">{_esc(cl["status_he"])}</span></div>')

    # 5 — actions
    S.append("<h2>5 · פעולות נדרשות</h2>")
    if actions:
        S.append('<div class="card"><table><tr><th>#</th><th>פעולה</th><th>מכריעה את</th><th>תפוקה צפויה</th><th>עדיפות</th></tr>')
        for a in actions["actions"]:
            pcls = "pri-h" if "גבוהה" in a["priority"] else "pri-m"
            S.append(f"<tr><td>{a['id']}</td><td>{_esc(a['what_he'])}</td>"
                     f"<td>{_esc(a['resolves_he'])}</td><td>{_esc(a['yield_he'])}</td>"
                     f"<td class='{pcls}'>{_esc(a['priority'])}</td></tr>")
        S.append("</table></div>")

    # 6 — investigation log
    S.append("<h2>6 · יומן חקירה</h2>")
    S.append('<div class="card"><table><tr><th>סבב</th><th>עיקרי</th></tr>'
             '<tr><td>1 (07/2026)</td><td>פרופילי-מקור, DEM עילי, סף-אות ושקלול, עוגן 1,121, השאיבה לבריכות; זיהוי עיוור של מקור-קיסריה מסמנים טריים</td></tr>'
             '<tr><td>2 (07/2026)</td><td>קואורדינטות רשמיות; פיצול לשני תיקים; נתיב ביוב←מט"ש←מאגרים; מוצאי-בריכות והיסטוריית ההסבה; מדרגות-תהום k=0.2; אגנים; דירוג הועלה למועמד-ליבה (לעיון)</td></tr>'
             '</table><div class="sub">הפירוט המלא: claims.json + היסטוריית git.</div></div>')

    # 7 — methodology manifest
    S.append("<h2>7 · נספח מתודולוגי (מניפסט)</h2>")
    S.append(f'<div class="card"><table>'
             f'<tr><td>גרסת מתודולוגיה (commit)</td><td dir="ltr">{git}</td></tr>'
             f'<tr><td>סף-אות</td><td>{MIN_SIGNAL_UG_L} µg/L</td></tr>'
             f'<tr><td>רוחב-עננה יחסי k</td><td>{GW_PLUME_K} (A6, בר-כיול)</td></tr>'
             f'<tr><td>סף צמידות-לערוץ</td><td>300 מ׳ (כויל על בת-שלמה)</td></tr>'
             f'<tr><td>DEM</td><td>Copernicus GLO-30, D8, ערוץ ≥0.5 קמ"ר</td></tr>'
             f'<tr><td>פרופילי-מקור</td><td>domains/pfas/source_profiles.json (היוריסטיקה ספרותית)</td></tr>'
             f'<tr><td>שפת ייחוס</td><td>"עקבי עם"; מועמד ליבה/משני/רקע — לעולם לא "המקור"</td></tr>'
             f'</table></div>')

    body = "\n".join(S)
    out_html = (f'<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width, initial-scale=1">'
                f'<title>תיק ממצאים — {_esc(region.get("name_he", region_name))}</title>'
                f'<style>{_CSS}</style></head><body><div class="wrap">{body}'
                f'<div class="foot">נוצר מ-generate_case_report.py · commit {git} · '
                f'טיוטת-תבנית לעיון</div></div></body></html>')
    out = os.path.join(region["_base"], f"case_report_{region_name}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(out_html)
    print(f"wrote {out} ({len(out_html)//1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1])
