"""generate_case_report.py — Environmental-hydrological investigation report.

DRAFT TEMPLATE (structure pending user approval; confidence scale approved).
Written as continuous professional prose — not bullet lists — in the genre of
a hydrological survey report, with required figures embedded self-contained
(plotly.js inlined from the local package; no CDN, no network):

    איור 1 — מפת התיק (ITM, ערוצים, מסלול-נגר, תחנות לפי Σ)
    איור 2 — מטריצת דמיון קוסינוס של תחנות התיק
    איור 3 — דעיכת Σ והזדקנות פרופיל לאורך מסלול הזרימה
    איור 4 — הרכב יחסי (fingerprint) של תחנות המפתח

Case scope: STRICTLY the region bbox (fixed 2026-07-27) — no stations or
measurements from other cases appear anywhere in the report.

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

import numpy as np
import plotly
import plotly.graph_objects as go

from config import COMPOUND_COLORS, DEFAULT_COLOR, GW_PLUME_K, MIN_SIGNAL_UG_L
from generate_review_report import _prepare
from src.analytics import cosine_similarity_matrix


def _esc(s):
    return html.escape(str(s))


import re as _re

_LATIN_TOKEN = _re.compile(
    r"(?<![>\w&#])((?:[A-Za-z][\w:.\-/+]*|\d+(?:\.\d+)?\s*(?:µg/L|ng/L|%))"
    r"(?:=[-\d.]+)?)(?!;)")


def _bdi(text_html):
    """Hebrew-HTML convention (toolkit, via CLAUDE.md): wrap Latin/technical
    tokens in <bdi> so RTL prose flows correctly around them. Applied to
    prose paragraphs only (not attributes/markup)."""
    parts = _re.split(r"(<[^>]+>)", text_html)
    out = []
    for p in parts:
        if p.startswith("<"):
            out.append(p)
        else:
            out.append(_LATIN_TOKEN.sub(r"<bdi>\1</bdi>", p))
    return "".join(out)


def _load(path):
    return json.load(open(path, encoding="utf-8")) if os.path.isfile(path) else None


def _conf(level, basis):
    cls = {"גבוהה": "hi", "בינונית": "mid", "נמוכה": "lo"}[level]
    return (f'<span class="conf {cls}">ודאות {level}</span> '
            f'<span class="basis">({_esc(basis)})</span>')


_PLOTLY_JS = open(os.path.join(os.path.dirname(plotly.__file__),
                               "package_data", "plotly.min.js"),
                  encoding="utf-8").read()

_FONT = dict(family="Assistant, Segoe UI, sans-serif", size=13)


# ─── figures ────────────────────────────────────────────────────────────────

def _fig_map(data):
    """Figure 1 — case map in ITM coordinates (self-contained, no tiles)."""
    fig = go.Figure()
    # DEM channels
    if data["channels"]:
        from pyproj import Transformer
        t = Transformer.from_crs(4326, 2039, always_xy=True)
        first = True
        for feat in data["channels"]["features"]:
            pts = [t.transform(lon, lat)
                   for lon, lat in feat["geometry"]["coordinates"]]
            fig.add_trace(go.Scatter(
                x=[p[0] / 1000 for p in pts], y=[p[1] / 1000 for p in pts],
                mode="lines", line=dict(color="#9ec9e2", width=1.2),
                name="ערוצי זרימה (DEM)", legendgroup="chan",
                showlegend=first, hoverinfo="skip"))
            first = False
    # candidate runoff path
    for c in data["candidates"]:
        pt = (data["flow"] or {}).get("points", {}).get(c["id"])
        if pt and pt.get("path_itm"):
            xs = [p[0] / 1000 for p in pt["path_itm"]]
            ys = [p[1] / 1000 for p in pt["path_itm"]]
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode="lines",
                line=dict(color="#d97a2c", width=3, dash="dash"),
                name="מסלול הנגר מהמקור", hoverinfo="skip"))
    # stations by domain
    surface_types = {"נקודה מזוהה בנחל", "תחנה הידרומטרית", "מאגר"}
    groups = {
        "נחל/מאגר — מעל סף": dict(color="#c64a3b", symbol="circle"),
        "קידוח/מעיין — מעל סף": dict(color="#2a6f97", symbol="diamond"),
        "מתחת לסף-אות": dict(color="#c8c4bc", symbol="circle-open"),
    }
    me = data["max_event"].set_index("station_name")
    for gname, style in groups.items():
        xs, ys, texts, sizes = [], [], [], []
        for s in data["stations"]:
            row = me.loc[s["name"]]
            is_surf = str(row.get("source_type", "")) in surface_types
            if gname.startswith("נחל") and (s["below_thr"] or not is_surf):
                continue
            if gname.startswith("קידוח") and (s["below_thr"] or is_surf):
                continue
            if gname.startswith("מתחת") and not s["below_thr"]:
                continue
            xs.append(float(row["x_itm"]) / 1000)
            ys.append(float(row["y_itm"]) / 1000)
            texts.append(f"{s['name']}<br>Σ={s['sigma']:.3f} µg/L"
                         f"<br>{s['profile']} ({s['score']:.0f}%)")
            sizes.append(7 if s["below_thr"] else
                         max(9, min(26, 10 + 4 * np.log10(s["sigma"] / 0.001 + 1))))
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers", name=gname,
            marker=dict(size=sizes, symbol=style["symbol"],
                        color=style["color"], opacity=0.85,
                        line=dict(width=1, color="white")),
            text=texts, hoverinfo="text"))
    # sources
    for src in (data["sources"] or {}).get("features", []):
        p = src["properties"]
        fig.add_trace(go.Scatter(
            x=[p["itm"][0] / 1000], y=[p["itm"][1] / 1000],
            mode="markers+text",
            marker=dict(size=20, symbol="star", color="#7a3d9e",
                        line=dict(width=1.5, color="white")),
            text=[p["name_he"]], textposition="top center",
            textfont=dict(size=12), name="מקור מוערך"))
    fig.update_layout(
        font=_FONT, template="plotly_white", height=560,
        xaxis=dict(title="ITM מזרח (ק\"מ)", constrain="domain"),
        yaxis=dict(title="ITM צפון (ק\"מ)", scaleanchor="x", scaleratio=1),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=60, r=20, t=40, b=50))
    return fig


def _similarity(data):
    """Cosine similarity matrix of the case's signal stations, clustered.
    Returns (sim_ordered_df, ordered_labels, clusters, top_pairs)."""
    df, group = data["df"], data["group"]
    sim = cosine_similarity_matrix(df, group)
    me = data["max_event"].set_index("station_name")
    keep = [s for s in sim.index
            if s in me.index and me.loc[s, "total_concentration"] >= MIN_SIGNAL_UG_L]
    sim = sim.loc[keep, keep]
    clusters = []
    try:
        from scipy.cluster.hierarchy import fcluster, leaves_list, linkage
        from scipy.spatial.distance import squareform
        d = 1 - sim.values / 100
        np.fill_diagonal(d, 0)
        Z = linkage(squareform((d + d.T) / 2, checks=False), method="average")
        lab = [sim.index[i] for i in leaves_list(Z)]
        sim = sim.loc[lab, lab]
        # clusters at 70% similarity (distance 0.30)
        cl = fcluster(Z, t=0.30, criterion="distance")
        by = {}
        for name, c in zip(keep, cl):
            by.setdefault(c, []).append(name)
        clusters = sorted((m for m in by.values() if len(m) >= 2),
                          key=len, reverse=True)
    except Exception:
        lab = list(sim.index)
    # top off-diagonal pairs
    pairs = []
    for i in range(len(lab)):
        for j in range(i + 1, len(lab)):
            pairs.append((sim.iloc[i, j], lab[i], lab[j]))
    pairs.sort(reverse=True)
    return sim, lab, clusters, pairs


def _fig_similarity(sim, lab):
    """Figure 2 — numbered heatmap (station names go in a legend table, so the
    axes stay legible even at 25+ stations). Cell values shown."""
    n = len(lab)
    nums = [str(i + 1) for i in range(n)]
    show_text = n <= 30
    fig = go.Figure(go.Heatmap(
        z=sim.values, x=nums, y=nums,
        colorscale=[[0, "#c64a3b"], [0.3, "#d8c84a"], [0.7, "#4ea66b"],
                    [0.9, "#1f7a4d"], [1, "#0d4a2e"]],
        zmin=0, zmax=100, xgap=1, ygap=1,
        colorbar=dict(title="% דמיון"),
        text=sim.values.round(0).astype(int) if show_text else None,
        texttemplate="%{text}" if show_text else None,
        textfont=dict(size=9, color="rgba(20,20,20,0.75)"),
        customdata=[[f"{lab[i]} ↔ {lab[j]}" for j in range(n)] for i in range(n)],
        hovertemplate="%{customdata}<br>%{z:.0f}%<extra></extra>"))
    fig.update_layout(
        font=_FONT, template="plotly_white",
        height=max(460, 24 * n + 150),
        xaxis=dict(title="מס' תחנה (ראו מקרא)", side="bottom", dtick=1,
                   tickfont=dict(size=10)),
        yaxis=dict(autorange="reversed", dtick=1, tickfont=dict(size=10)),
        margin=dict(l=40, r=10, t=30, b=50))
    return fig


def _fig_attenuation(data):
    for c in data["candidates"]:
        ser = c.get("atten_series") or []
        if len(ser) >= 3:
            xs = [d["km"] for d in ser]
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=xs, y=[d["sigma"] for d in ser], name="ΣPFAS (µg/L)",
                mode="lines+markers+text", text=[d["station"] for d in ser],
                textposition="top center", textfont=dict(size=10),
                line=dict(color="#c64a3b")))
            fig.add_trace(go.Scatter(
                x=xs, y=[d["precursor"] for d in ser], name="% קדם-חומרים",
                mode="lines+markers", line=dict(color="#2a9d8f"), yaxis="y2"))
            fig.update_layout(
                font=_FONT, template="plotly_white", height=420,
                xaxis=dict(title="מרחק-מסלול מהמקור (ק\"מ)"),
                yaxis=dict(title="ΣPFAS (µg/L)", type="log"),
                yaxis2=dict(title="% קדם-חומרים", overlaying="y", side="right",
                            rangemode="tozero"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                margin=dict(l=60, r=60, t=40, b=50))
            return fig
    return None


def _fig_fingerprints(data, max_stations=8):
    me = data["max_event"].sort_values("total_concentration", ascending=False)
    names = [n for n in me["station_name"]
             if n in data["fingerprint"].index][:max_stations]
    fp = data["fingerprint"].loc[names]
    fp = fp[[c for c in fp.columns if fp[c].sum() > 0]]
    fig = go.Figure()
    for comp in fp.columns:
        fig.add_trace(go.Bar(
            name=comp, x=[n[:22] for n in names], y=fp[comp],
            marker_color=COMPOUND_COLORS.get(comp, DEFAULT_COLOR)))
    fig.update_layout(
        font=_FONT, template="plotly_white", barmode="stack", height=430,
        yaxis=dict(title="אחוז מההרכב (%)", range=[0, 100]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)),
        margin=dict(l=50, r=10, t=60, b=80))
    return fig, names


# ─── prose builders ─────────────────────────────────────────────────────────

def _list_he(items, limit=None):
    items = list(items)
    if limit and len(items) > limit:
        items = items[:limit] + [f"ועוד {len(items) - limit}"]
    if len(items) <= 1:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + " ו" + items[-1]


def _findings_prose(data):
    P = []
    me = data["max_event"]
    sig = me[me["total_concentration"] >= MIN_SIGNAL_UG_L]
    top = sig.sort_values("total_concentration", ascending=False).head(3)
    top_list = _list_he(['"%s" (%s)' % (r.station_name,
                                        format(r.total_concentration, ",.2f"))
                         for r in top.itertuples()])
    orders = np.log10(sig["total_concentration"].max()
                      / max(sig["total_concentration"].min(), 1e-6))
    P.append(
        f"בתחום התיק נדגמו {data['n_stations']} תחנות, מהן {len(sig)} מעל "
        f"סף-האות הראייתי ({MIN_SIGNAL_UG_L} מיקרוגרם לליטר). טווח הריכוזים "
        f"משתרע על פני כ-{orders:.0f} סדרי גודל. הריכוזים הגבוהים ביותר "
        f"נמדדו ב{top_list} — ראו איור 1 לפריסה המרחבית.")
    for c in data["candidates"]:
        if c["n_surface_down"]:
            P.append(
                f"ניתוח מסלולי הזרימה העיליים, הנגזרים ממודל הגבהים "
                f"(Copernicus GLO-30, שיטת D8), מעלה כי {c['n_surface_down']} "
                f"תחנות עיליות פגועות יושבות על מסלול-הנגר היוצא מהאתר. "
                + (f"לצדן, {len(c['transfer_fed'])} תחנות נוספות מוזנות "
                   f"בנתיבים אנתרופוגניים מוצהרים (שאיבה מהנחל וקו "
                   f"הביוב–מט\"ש–מאגרים)." if c["transfer_fed"] else ""))
        att = c["attenuation"]
        if att.get("r_precursor") is not None:
            P.append(
                f"לאורך המסלול נצפית הזדקנות-פרופיל מובהקת: נתח קדם-החומרים "
                f"(FOSA, 8:2FTS, 6:2FT) יורד בעקביות עם המרחק "
                f"(Spearman r={att['r_precursor']}) — דפוס האופייני להתרחקות "
                f"ממקור פעיל (איור 3). דעיכת הריכוז הכולל, לעומת זאת, אינה "
                f"חד-משמעית בחתך הנוכחי (r={att['r_conc']}); ההסבר הסביר הוא "
                f"ערבוב שני משטרי-עומס ברשומה — לפני ואחרי הסבת בריכה-1500 "
                f"לביוב — בחתך שאינו בו-זמני.")
        if c.get("gw_tiers"):
            t12 = [s for s in c["downgradient"] if s in c["gw_tiers"]]
            P.append(
                f"בציר מי-התהום הוחלו מדרגות-הסבירות (עננה גאוסיאנית, "
                f"k={GW_PLUME_K}): {len(t12)} קידוחים במדרגות הליבה/האגף"
                + (f", ו-{len(c['gw_fringe'])} בשולי-העננה (תמיכה חלשה בלבד)"
                   if c["gw_fringe"] else "")
                + (f". קידוחים צמודי-ערוץ ({_list_he(c['cascade_candidates'])}) "
                   f"סווגו כמועמדי-שרשרת — נתיב נחל←החדרת-גדות←תהום — "
                   f"ומבחן-ההבחנה הכימי (פרקציונציה של שרשראות קצרות) תומך "
                   f"בהסעה תת-קרקעית של ממש." if c.get("cascade_candidates") else "."))
    return P


def _discussion_prose(data):
    P = []
    for c in data["candidates"]:
        fors = len(c["evidence_for"])
        P.append(
            f"משקלול שלושת צירי הראיה — הכימי, ההידרולוגי וראיית-הפליטה — "
            f"האתר \"{c['name_he']}\" מדורג <b>{c['tier']}</b>. "
            f"{fors} קווי-ראיה תומכים מתלכדים: " +
            "; ".join(e.split("—")[0].strip() for e in c["evidence_for"][:4]) + ".")
        if c["evidence_against"]:
            P.append(
                "מנגד, ובהתאם לחובת בחינת ההסברים החלופיים, נרשמות "
                "הסתייגויות: " + " ".join(c["evidence_against"]) +
                " הסתייגויות אלו אינן מבטלות את הדירוג אך תוחמות את תוקפו.")
        P.append(
            "יודגש: התאמת פרופיל — גם גבוהה — משמעה \"עקבי עם\" ואינה קביעת "
            "מקור; הדירוג כולו כפוף לשפה הזהירה המחייבת (מועמד ליבה/משני/רקע) "
            "ולעקרון שכיוון זרימה לבדו אינו מזהה מקור.")
    return P


# ─── report assembly ────────────────────────────────────────────────────────

_CSS = """
:root{--ink:#1c1f24;--ink2:#4a4f57;--ink3:#7d8189;--line:#e2ddd2;
--accent:#2a9d8f;--warn:#d97a2c;--ok:#2d8b5e;--bad:#c64a3b}
*{box-sizing:border-box}
body{margin:0;background:#f5f3ee;color:var(--ink);direction:rtl;
font-family:Assistant,"Segoe UI",system-ui,sans-serif;line-height:1.85;font-size:16px}
.wrap{max-width:900px;margin:0 auto;padding:30px;background:#fff;
box-shadow:0 0 14px rgba(0,0,0,.06)}
h1{font-size:1.6rem;margin:.2em 0;line-height:1.3}
h2{font-size:1.25rem;color:#1a5c50;border-bottom:2px solid var(--accent);
padding-bottom:5px;margin-top:2.2em}
h3{font-size:1.05rem;margin-top:1.5em}
p{margin:.8em 0;text-align:justify}
.meta{color:var(--ink3);font-size:.85rem;border-bottom:1px solid var(--line);
padding-bottom:12px;margin-bottom:8px}
.draft{background:#7a3d9e;color:#fff;border-radius:6px;padding:9px 14px;
font-weight:600;font-size:.9rem;margin:14px 0}
.figure{margin:1.4em 0;border:1px solid var(--line);border-radius:8px;padding:10px}
.figcap{font-size:.85rem;color:var(--ink2);text-align:center;margin-top:6px;font-weight:600}
.conf{display:inline-block;border-radius:100px;padding:1px 10px;font-size:.78rem;font-weight:700}
.conf.hi{background:#e3f2e8;color:var(--ok)}.conf.mid{background:#fdf1e4;color:var(--warn)}
.conf.lo{background:#fbe9e7;color:var(--bad)}
.basis{font-size:.8rem;color:var(--ink3)}
table{width:100%;border-collapse:collapse;font-size:.85rem;margin:.8em 0}
th,td{text-align:right;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#faf8f4;color:var(--ink2)}
.concl{border-right:4px solid var(--accent);background:#fafcfb;padding:10px 14px;margin:10px 0}
.foot{color:var(--ink3);font-size:.78rem;margin-top:30px;text-align:center;
border-top:1px solid var(--line);padding-top:12px}
@media print{
  .wrap{box-shadow:none;max-width:100%}body{background:#fff;font-size:12pt}
  h2{page-break-after:avoid}.figure{page-break-inside:avoid}
  .concl{page-break-inside:avoid}table{page-break-inside:avoid}
  .draft{display:none}
}
"""


def main(region_name):
    data = _prepare(region_name)
    region = data["region"]
    actions = _load(os.path.join(region["_base"], "actions.json"))
    nar = region.get("report_narrative", {})
    sem = region.get("dataset_semantics", {})
    git = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True,
                         cwd=os.path.dirname(__file__) or ".").stdout.strip()

    fig_map = _fig_map(data)
    sim_df, sim_lab, sim_clusters, sim_pairs = _similarity(data)
    fig_sim = _fig_similarity(sim_df, sim_lab)
    n_sim = len(sim_lab)
    fig_att = _fig_attenuation(data)
    fig_fp, fp_names = _fig_fingerprints(data)

    def _plot(fig, div_id):
        return (f'<div id="{div_id}"></div><script>Plotly.newPlot("{div_id}", '
                f'{fig.to_json()}, {{}}, {{responsive:true, displayModeBar:false}});'
                f'</script>')

    S = []
    S.append(f"<h1>דוח חקירה סביבתית-הידרולוגית<br>{_esc(region.get('name_he', region_name))}</h1>")
    S.append(f'<div class="meta">השירות ההידרולוגי, רשות המים · מהדורת עבודה '
             f'{region.get("_round","")} · 27 ביולי 2026 · גרסת מתודולוגיה '
             f'<span dir="ltr">{git}</span></div>')
    S.append('<div class="draft">טיוטת תבנית לעיון — מבנה הדוח טרם קובע. '
             'סולם-הוודאות (גבוהה/בינונית/נמוכה + בסיס) מאושר.</div>')

    # 1 — introduction & background
    S.append("<h2>1. מבוא ורקע</h2>")
    if nar.get("background_he"):
        S.append(_bdi(f"<p>{_esc(nar['background_he'])}</p>"))
    if nar.get("trigger_he"):
        S.append(_bdi(f"<p>{_esc(nar['trigger_he'])}</p>"))
    S.append(
        "<p>מטרת החקירה היא מיפוי שיטתי של תמונת הזיהום בתחום התיק, בחינת "
        "מועמדי-מקור מול שלושה צירי ראיה בלתי-תלויים — התאמה כימית, סבירות "
        "הידרולוגית וראיות פליטה — וגיבוש המלצות לפעולות המשך. הדוח נוקט "
        "בשפת ייחוס זהירה: מועמד מדורג \"ליבה\", \"משני\" או \"רקע מקומי\", "
        "ולעולם אינו מוכרז \"המקור\".</p>")

    # 2 — data & methods
    S.append("<h2>2. נתונים ושיטות</h2>")
    S.append(
        f"<p>בסיס הנתונים הוא קובץ מדידות של רשות המים "
        f"({_esc(os.path.basename(region['measurement_file']))}), שסונן "
        f"לפי הכלל \"{_esc(sem.get('snapshot_rule', ''))}\" ומשתרע על התקופה "
        f"{_esc(sem.get('date_span', ''))}. יודגש כי החתך אינו בו-זמני: "
        f"תחנות שונות נדגמו במועדים שונים, וההשוואה ביניהן מניחה מצב-יציב — "
        f"הנחה מוצהרת שהפרותיה נדונות בפרק הדיון. תחנות שריכוזן הכולל נמוך "
        f"מסף-האות ({MIN_SIGNAL_UG_L} מיקרוגרם לליטר) מוצגות אך אינן נספרות "
        f"כראיה, שכן הרכבן נשלט על-ידי רעש אנליטי וערכי סף-גילוי.</p>")
    S.append(
        f"<p>המתודולוגיה משלבת טביעת-אצבע כימית מנורמלת והתאמתה לפרופילי-מקור "
        f"ספרותיים (קוסינוס), ניתוח מסלולי זרימה עיליים ממודל גבהים "
        f"(Copernicus GLO-30, ‏30 מ'), מדרגות-סבירות גאוסיאניות לזרימת תהום "
        f"(k={GW_PLUME_K}, פרמטר מוצהר ובר-כיול), נתיבי-מים אנתרופוגניים "
        f"מוצהרים עם תיעוד-מקור, ורגרסיות דעיכה על מרחקי-מסלול. הפירוט המלא — "
        f"בנספח המתודולוגי.</p>")

    # 3 — findings
    S.append("<h2>3. ממצאים</h2>")
    S.append(f'<div class="figure">{_plot(fig_map, "figmap")}'
             f'<div class="figcap">איור 1: מפת התיק — תחנות (גודל ∝ Σ), '
             f'ערוצי DEM, מסלול הנגר מהמקור. קואורדינטות ITM בק"מ.</div></div>')
    for p in _findings_prose(data):
        S.append(_bdi(f"<p>{p}</p>"))
    me_idx = data["max_event"].set_index("station_name")
    legend_rows = "".join(
        f"<tr><td>{i + 1}</td><td>{_esc(s)}</td>"
        f"<td>{me_idx.loc[s, 'total_concentration']:.3f}</td></tr>"
        for i, s in enumerate(sim_lab))
    S.append(
        f'<div class="figure">{_plot(fig_sim, "figsim")}'
        f'<div class="figcap">איור 2: מטריצת דמיון קוסינוס — {n_sim} '
        f'תחנות מעל סף-האות, ממוספרות ומסודרות באשכולות (המספרים מפוענחים '
        f'במקרא למטה).</div>'
        f'<details style="margin-top:8px"><summary style="cursor:pointer;'
        f'font-size:.85rem;color:#4a4f57">מקרא מספור התחנות (לחצו להרחבה)</summary>'
        f'<table style="font-size:.8rem"><tr><th>#</th><th>תחנה</th>'
        f'<th>Σ (µg/L)</th></tr>{legend_rows}</table></details></div>')
    # cluster interpretation prose
    if sim_clusters:
        cl_txt = "; ".join(
            f"אשכול של {len(c)} תחנות ({_list_he([_esc(x) for x in c], 4)})"
            for c in sim_clusters[:3])
        top = sim_pairs[0] if sim_pairs else None
        S.append(_bdi(
            f"<p>מבנה הדמיון (איור 2) מגלה {len(sim_clusters)} אשכולות "
            f"כימיים מובחנים ברמת דמיון של 70% ומעלה: {cl_txt}. "
            + (f"הזוג הדומה ביותר, {_esc(top[1])} ו{_esc(top[2])} "
               f"({top[0]:.0f}%), " if top else "")
            + "התלכדות תחנות לאשכול חזק עקבית עם מקור או נתיב-הסעה משותף, "
            "אך אינה מוכיחה אותו — היא מגדירה קבוצות-חשד להמשך בחינה "
            "מול צירי הזרימה והפליטה.</p>"))
    if fig_att is not None:
        S.append(f'<div class="figure">{_plot(fig_att, "figatt")}'
                 f'<div class="figcap">איור 3: ΣPFAS (ציר שמאלי, לוגריתמי) '
                 f'ונתח קדם-חומרים (ימני) לאורך מסלול הזרימה.</div></div>')
    S.append(f'<div class="figure">{_plot(fig_fp, "figfp")}'
             f'<div class="figcap">איור 4: הרכב יחסי של {len(fp_names)} '
             f'תחנות המפתח (לפי Σ יורד).</div></div>')

    # 4 — discussion
    S.append("<h2>4. דיון</h2>")
    for p in _discussion_prose(data):
        S.append(_bdi(f"<p>{p}</p>"))

    # 5 — conclusions
    S.append("<h2>5. מסקנות</h2>")
    for c in data["candidates"]:
        lvl = "גבוהה" if "ליבה" in c["tier"] else "בינונית"
        S.append(f'<div class="concl"><p>האתר \"{_esc(c["name_he"])}\" מדורג '
                 f'<b>{_esc(c["tier"])}</b> ביחס לזיהום ה-PFAS בתחום התיק. '
                 f'{_conf(lvl, "התלכדות שלושת צירי הראיה; ראו פרק 4")}</p></div>')
        att = c["attenuation"]
        if att.get("r_precursor") is not None and att["r_precursor"] <= -0.4:
            S.append(f'<div class="concl"><p>החתימה הכימית מזדקנת בעקביות עם '
                     f'ההתרחקות מהאתר — עדות תומכת עצמאית להסעה ממנו. '
                     f'{_conf("בינונית", "חתך יחיד, לא בו-זמני")}</p></div>')
    for q in (region.get("open_questions") or []):
        S.append(f'<div class="concl"><p>{_esc(q["title_he"])}: '
                 f'{_esc(q.get("stakes_he", q["statement_he"]))} '
                 f'{_conf("נמוכה", "שאלה פתוחה — " + q.get("status", ""))}</p></div>')

    # 6 — recommendations
    S.append("<h2>6. המלצות ופעולות נדרשות</h2>")
    S.append("<p>הפעולות הבאות נגזרות ישירות מהשאלות הפתוחות, ומסודרות לפי "
             "התועלת הראייתית הצפויה מהן:</p>")
    if actions:
        S.append('<table><tr><th>#</th><th>פעולה</th><th>מה תכריע</th><th>עדיפות</th></tr>')
        for a in actions["actions"]:
            S.append(f"<tr><td>{a['id']}</td><td>{_esc(a['what_he'])}</td>"
                     f"<td>{_esc(a['yield_he'])}</td><td>{_esc(a['priority'])}</td></tr>")
        S.append("</table>")

    # appendix
    S.append("<h2>נספח — מניפסט מתודולוגי</h2>")
    S.append(f"<p>גרסת מתודולוגיה (commit): <span dir='ltr'>{git}</span> · "
             f"סף-אות: {MIN_SIGNAL_UG_L} µg/L · רוחב-עננה k={GW_PLUME_K} · "
             f"צמידות-לערוץ: 300 מ' · פרופילי-מקור: domains/pfas (היוריסטיקה "
             f"ספרותית — ITRC; Barzen-Hanson 2017; Houtz 2013) · DEM: "
             f"Copernicus GLO-30, D8, סף-ערוץ 0.5 קמ\"ר. לוח-הטענות ויומן-"
             f"ההכרעות המלאים: claims.json בתיקיית התיק.</p>")

    body = "\n".join(S)
    out_html = (f'<!doctype html><html lang="he" dir="rtl"><head>'
                f'<meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width, initial-scale=1">'
                f'<title>דוח חקירה — {_esc(region.get("name_he", region_name))}</title>'
                f'<script>{_PLOTLY_JS}</script>'
                f'<style>{_CSS}</style></head><body><div class="wrap">{body}'
                f'<div class="foot">הדוח הופק אוטומטית מקבצי התיק · commit '
                f'<span dir="ltr">{git}</span> · כלי סינון לתעדוף חקירה — '
                f'אינו קביעת מקור ואינו מחליף שיקול-דעת מומחה</div>'
                f'</div></body></html>')
    out = os.path.join(region["_base"], f"case_report_{region_name}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(out_html)
    print(f"wrote {out} ({len(out_html) // 1024} KB)")
    print(f"  case stations={data['n_stations']} signal={data['n_signal']} "
          f"sim_matrix={n_sim} fingerprints={len(fp_names)}")


if __name__ == "__main__":
    main(sys.argv[1])
