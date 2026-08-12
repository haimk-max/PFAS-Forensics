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
import math
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
from src.attribution import SURFACE_TYPES


def _esc(s):
    return html.escape(str(s))


import re as _re

# numbers may carry thousands-commas (1,121.11) — without covering them the
# comma splits the bidi run and the digits reorder in RTL prose
_NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
# a "word" may start with a short digit prefix (3M, 6:2FT) and end with a
# trademark sign; consecutive Latin words joined by single spaces are ONE
# token — wrapping each word in its own <bdi> isolate lets RTL layout reverse
# multi-word names ("3M Light Water" rendered as "Water Light 3M")
_LATIN_WORD = r"\d{0,4}[A-Za-z][\w:.\-/+]*[™®]?"
_LATIN_TOKEN = _re.compile(
    r"(?<![>\w&#])((?:"
    rf"(?:{_LATIN_WORD})(?: {_LATIN_WORD})*"
    rf"|{_NUM}\s*(?:µg/L|ng/L|%)"
    rf"|{_NUM}\s*–\s*{_NUM}"
    r")(?:=[-\d.]+)?)(?!;)")


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


# ─── transport families ─────────────────────────────────────────────────────
# Six evidence families (approved verbally 2026-08-11) + two display-only
# groups ("other" = stations not assigned to any candidate pathway, "below" =
# under the signal threshold). Order = narrative order: source outward.

FAMILY_ORDER = ["focus", "stream", "pumped", "piped", "cascade", "gw",
                "other", "below"]

FAMILIES = {
    "focus":   dict(name_he="מוקד — מתקן וניקוז צמוד", short_he="מוקד",
                    color="#7a3d9e", symbol="star", time_he="—"),
    "stream":  dict(name_he="נתיב הנחל (עילי)", short_he="נחל",
                    color="#c64a3b", symbol="circle", time_he="שעות–ימים"),
    "pumped":  dict(name_he="מוזנות-שאיבה (בריכות דגים)", short_he="שאיבה",
                    color="#d97a2c", symbol="triangle-up",
                    time_he="ימים–שבועות (שהות בבריכה)"),
    "piped":   dict(name_he="נתיב מתועל (ביוב←מט\"ש←מאגרים)", short_he="מתועל",
                    color="#8a5a44", symbol="square", time_he="ימים (מתועל)"),
    "cascade": dict(name_he="החדרת-גדות (קידוחי גדה)", short_he="גדות",
                    color="#2a9d8f", symbol="diamond-wide",
                    time_he="שבועות–חודשים"),
    "gw":      dict(name_he="תהום (מדרגות-עננה)", short_he="תהום",
                    color="#2a6f97", symbol="diamond", time_he="שנים"),
    "other":   dict(name_he="לא משויך לנתיב (בבדיקה)", short_he="לא-משויך",
                    color="#8d8d8d", symbol="circle-x", time_he="—"),
    "below":   dict(name_he="מתחת לסף-אות", short_he="מתחת-סף",
                    color="#c8c4bc", symbol="circle-open", time_he="—"),
}

# Evidence status per family: computed HERE (not narrative data) so the
# mechanism text can never overstate the evidence tier. (level, css, label)
def _family_status(key, c):
    if key == "focus":
        return ("hi", "עוגן מאושר-מקור") if c.get("anchor_station") \
            else ("mid", "מוצהר")
    if key == "stream":
        basis = c.get("attenuation", {}).get("basis")
        return ("hi", "נגזר-DEM") if basis == "path_dem" \
            else ("lo", "הנחת-כיוון")
    if key == "pumped":
        return ("mid", "נתיב מוצהר (עדות)")
    if key == "piped":
        return ("mid", "נתיב מוצהר; חתימת מט\"ש טרם נדגמה")
    if key == "cascade":
        return ("lo", "השערת-מנגנון — יוכרע בדיגום מזווג")
    if key == "gw":
        return ("lo", "הנחת-כיוון — ממתין למפלסים")
    if key == "other":
        return ("lo", "בבדיקה (השערות-העברה)")
    return ("lo", "")


def _classify_families(data):
    """Assign each case station to one transport family, using only facts
    already established by the attribution layer (no new judgement here)."""
    fam = {}
    c = data["candidates"][0] if data["candidates"] else None
    me = data["max_event"].set_index("station_name")
    region = data["region"]
    outfalls = region.get("outfalls", {})
    if c is None:
        return {s["name"]: ("below" if s["below_thr"] else "other")
                for s in data["stations"]}
    sx, sy = c["itm"]
    down = set(c.get("downgradient", []))
    tf = c.get("transfer_fed", {})
    cascade = set(c.get("cascade_candidates", []))
    gw_tiers = c.get("gw_tiers", {})
    anchor = c.get("anchor_station")
    # Site envelopes (temporary name rule, 2026-08-12): every declared
    # source's site members belong to the focus family — the basin view
    # collapses each source complex to one node.
    site_union = {s for cand in data["candidates"]
                  for s in cand.get("site_members", [])}
    for s in data["stations"]:
        name = s["name"]
        if s["below_thr"]:
            fam[name] = "below"
            continue
        row = me.loc[name]
        # Focus = DECLARED at-site stations (anchor / outfalls), site-
        # envelope members, or the tier-1 at-site radius (250 m). Bare
        # 250-1000 m proximity must NOT precede pathway assignment: in
        # kesariya it swallowed the Or-Akiva cascade candidates (776-981 m
        # from the site, 9-131 m off the runoff channel) into "focus" and
        # hid the pathway finding.
        at_site = math.hypot(float(row["x_itm"]) - sx,
                             float(row["y_itm"]) - sy) <= 250.0
        if name == anchor or name in outfalls or at_site \
                or name in site_union:
            fam[name] = "focus"
        elif name in tf:
            fam[name] = "pumped" if tf[name].get("kind") == "pumping" else "piped"
        elif name in cascade:
            fam[name] = "cascade"
        elif str(row.get("source_type", "")) in SURFACE_TYPES:
            fam[name] = "stream" if name in down else "other"
        elif name in gw_tiers:
            fam[name] = "gw"
        else:
            fam[name] = "other"
    return fam


def _fam_members(data, fam_of, key):
    """Family members sorted by Σ descending."""
    rows = [s for s in data["stations"] if fam_of.get(s["name"]) == key]
    return sorted(rows, key=lambda s: -s["sigma"])


def _csm_html(data, fam_of, nar_families):
    """Figure 2 — conceptual site model: source → pathways → receptor
    families, each carrying mechanism, timescale, expected weathering and a
    computed evidence-status chip. Pure HTML/CSS (print-safe, RTL)."""
    c = data["candidates"][0] if data["candidates"] else None
    if c is None:
        return ""
    me = data["max_event"].set_index("station_name")
    anchor = c.get("anchor_station")
    anchor_sig = (float(me.loc[anchor, "total_concentration"])
                  if anchor and anchor in me.index else None)
    cards = []
    for key in ["stream", "pumped", "piped", "cascade", "gw"]:
        members = _fam_members(data, fam_of, key)
        if not members:
            continue
        f = FAMILIES[key]
        lvl, label = _family_status(key, c)
        nf = (nar_families or {}).get(key, {})
        weather = nf.get("weathering_he", "")
        names = ", ".join(m["name"] for m in members[:3])
        if len(members) > 3:
            names += f" ועוד {len(members) - 3}"
        cards.append(
            f'<div class="csm-card" style="border-right-color:{f["color"]}">'
            f'<div class="csm-head"><span class="csm-dot" '
            f'style="background:{f["color"]}"></span>'
            f'<b>{_esc(f["name_he"])}</b>'
            f'<span class="conf {lvl}">{_esc(label)}</span></div>'
            f'<div class="csm-row">קצב-הסעה אופייני: {_esc(f["time_he"])} · '
            f'{len(members)} תחנות</div>'
            + (f'<div class="csm-row">בליה צפויה: {_bdi(_esc(weather))}</div>'
               if weather else "")
            + f'<div class="csm-row csm-rec">רצפטורים: {_bdi(_esc(names))}</div>'
            f'</div>')
    src_line = f'<b>{_esc(c["name_he"])}</b>'
    if anchor_sig:
        src_line += (f' · עוגן מאושר "{_esc(anchor)}" '
                     f'(<span dir="ltr">Σ={anchor_sig:,.0f} µg/L</span>)')
    return (f'<div class="csm"><div class="csm-src">{_bdi(src_line)}</div>'
            f'<div class="csm-flow">⬐ נתיבי ההסעה ⬎</div>'
            f'<div class="csm-grid">{"".join(cards)}</div></div>')


def _conf(level, basis):
    cls = {"גבוהה": "hi", "בינונית": "mid", "נמוכה": "lo"}[level]
    return (f'<span class="conf {cls}">ודאות {level}</span> '
            f'<span class="basis">({_esc(basis)})</span>')


_PLOTLY_JS = open(os.path.join(os.path.dirname(plotly.__file__),
                               "package_data", "plotly.min.js"),
                  encoding="utf-8").read()

# Leaflet is vendored (vendor/leaflet, BSD-2-Clause) and inlined: the reports
# must stay self-contained — an Artifact page cannot reach a CDN.
_LEAFLET_DIR = os.path.join(os.path.dirname(__file__), "vendor", "leaflet")
_LEAFLET_JS = open(os.path.join(_LEAFLET_DIR, "leaflet.js"),
                   encoding="utf-8").read()
_LEAFLET_CSS = open(os.path.join(_LEAFLET_DIR, "leaflet.css"),
                    encoding="utf-8").read()

_FONT = dict(family="Assistant, Segoe UI, sans-serif", size=13)


# ─── figures ────────────────────────────────────────────────────────────────

def _map_payload(data, fam_of):
    """Figure 1 data for the embedded Leaflet map (approved 2026-08-12).

    Plotly was the wrong tool for a map: its zoom/pan is a chart interaction,
    not map navigation. Leaflet is vendored locally (vendor/leaflet) and the
    map runs on CRS.Simple with axes in ITM kilometres, so no projection or
    tile server is involved — the shaded-relief PNG is the only backdrop and
    it is embedded as a data URI. Returns a JSON-ready dict."""
    region = data["region"]
    me = data["max_event"].set_index("station_name")
    bbox = region.get("bbox_itm") or [0, 0, 1, 1]
    P = {"bbox": [bbox[0] / 1000, bbox[1] / 1000,
                  bbox[2] / 1000, bbox[3] / 1000],
         "famColors": {k: v["color"] for k, v in FAMILIES.items()},
         "famNames": {k: v["name_he"] for k, v in FAMILIES.items()}}

    # backdrops: satellite imagery (base) + shaded relief (toggleable)
    import base64

    def _overlay(img_name, meta_name, mime):
        img_p = os.path.join(region["_base"], "derived", img_name)
        meta_p = os.path.join(region["_base"], "derived", meta_name)
        if not (os.path.isfile(img_p) and os.path.isfile(meta_p)):
            return None
        m = json.load(open(meta_p, encoding="utf-8"))
        b = m["bbox_itm"]
        return {"url": f"data:{mime};base64," +
                base64.b64encode(open(img_p, "rb").read()).decode(),
                "bounds": [b[0] / 1000, b[1] / 1000, b[2] / 1000, b[3] / 1000],
                "meta": m}

    sat = _overlay("basemap.jpg", "basemap_meta.json", "image/jpeg")
    if sat:
        dates = ", ".join(s["datetime"][:10] for s in sat["meta"]["scenes"])
        P["satellite"] = {"url": sat["url"], "bounds": sat["bounds"],
                          "credit": (f'{sat["meta"]["attribution_he"]} · '
                                     f'{dates}')}
    hs = _overlay("hillshade.png", "hillshade_meta.json", "image/png")
    if hs:
        P["hillshade"] = {"url": hs["url"], "bounds": hs["bounds"]}

    # channel network, split minor/major by drainage area
    P["channels"] = {"minor": [], "major": []}
    if data["channels"]:
        from pyproj import Transformer
        t = Transformer.from_crs(4326, 2039, always_xy=True)
        feats = data["channels"]["features"]
        accs = [f.get("properties", {}).get("max_acc_cells", 0) for f in feats]
        thr = np.percentile([a for a in accs if a], 85) if any(accs) else 0
        for feat, acc in zip(feats, accs):
            line = []
            for lon, lat in feat["geometry"]["coordinates"]:
                x, y = t.transform(lon, lat)
                line.append([round(x / 1000, 4), round(y / 1000, 4)])
            P["channels"]["major" if acc >= thr else "minor"].append(line)

    # candidate runoff paths + declared connectors
    P["paths"], P["connectors"] = [], []
    colors = ["#d97a2c", "#7a3d9e", "#2a9d8f"]
    for i, c in enumerate(data["candidates"]):
        pt = (data["flow"] or {}).get("points", {}).get(c["id"])
        path = pt.get("path_itm") if pt else None
        short = c["name_he"].split("—")[0].strip()
        if path:
            P["paths"].append({
                "name": f"מסלול הנגר — {short}",
                "color": colors[i % len(colors)],
                "pts": [[round(p[0] / 1000, 4), round(p[1] / 1000, 4)]
                        for p in path]})
        sx, sy = c["itm"]
        for s, tfv in (c.get("transfer_fed") or {}).items():
            if s not in me.index:
                continue
            tx = float(me.loc[s, "x_itm"]) / 1000
            ty = float(me.loc[s, "y_itm"]) / 1000
            if tfv.get("kind") == "pumping" and path:
                near = min(path, key=lambda p: (p[0] / 1000 - tx) ** 2
                           + (p[1] / 1000 - ty) ** 2)
                P["connectors"].append({
                    "name": "שאיבה מהנחל (מוצהר)",
                    "color": FAMILIES["pumped"]["color"], "dash": "3 5",
                    "pts": [[near[0] / 1000, near[1] / 1000], [tx, ty]]})
            elif tfv.get("kind") != "pumping":
                P["connectors"].append({
                    "name": "נתיב מתועל (מוצהר, סכמטי)",
                    "color": FAMILIES["piped"]["color"], "dash": "9 4 2 4",
                    "pts": [[sx / 1000, sy / 1000], [tx, ty]]})

    # stations
    gw_tiers = (data["candidates"][0].get("gw_tiers", {})
                if data["candidates"] else {})
    P["stations"] = []
    for s in data["stations"]:
        row = me.loc[s["name"]]
        fk = fam_of.get(s["name"], "other")
        extra = ""
        if fk == "gw" and s["name"] in gw_tiers:
            gt = gw_tiers[s["name"]]
            extra = f"<br>מדרגת-עננה: {gt['tier']}"
            if gt.get("tier_best"):
                extra += f" (מטושטש-שאיבה: עד {gt['tier_best']})"
            wc = gt.get("well_class")
            if wc == "production":
                extra += "<br>קידוח הפקה — ריכוז = חסם-תחתון"
            elif wc == "monitoring":
                extra += "<br>קידוח ניטור"
        P["stations"].append({
            "n": s["name"], "f": fk,
            "x": round(float(row["x_itm"]) / 1000, 4),
            "y": round(float(row["y_itm"]) / 1000, 4),
            "r": (4 if s["below_thr"] else
                  round(max(6, min(17, 6 + 3 * np.log10(
                      s["sigma"] / 0.001 + 1))), 1)),
            "t": (f'<b>{_esc(s["name"])}</b><br>Σ={s["sigma"]:.3f} µg/L'
                  f'<br>{_esc(s["profile"])} ({s["score"]:.0f}%)'
                  f'<br>{FAMILIES[fk]["name_he"]}{extra}')})

    # declared sources, junction flags, key labels
    P["sources"] = [{
        "n": f["properties"]["name_he"].split("—")[0].strip(),
        "full": f["properties"]["name_he"],
        "x": f["properties"]["itm"][0] / 1000,
        "y": f["properties"]["itm"][1] / 1000}
        for f in (data["sources"] or {}).get("features", [])]
    P["junctions"], seen = [], set()
    for c in data["candidates"]:
        for jf in c.get("junction_findings", []):
            seg = tuple(jf.get("segment") or ("", ""))
            if seg in seen or seg[1] not in me.index:
                continue
            seen.add(seg)
            P["junctions"].append({
                "x": round(float(me.loc[seg[1], "x_itm"]) / 1000, 4),
                "y": round(float(me.loc[seg[1], "y_itm"]) / 1000, 4),
                "t": (f'<b>צומת חשוד {jf["km"][0]:.0f}–{jf["km"][1]:.0f} '
                      f'ק"מ</b><br>נמדד ב: {_esc(seg[1])}'
                      f'<br>התחנה הקודמת: {_esc(seg[0])}'
                      f'<br>{_esc("; ".join(jf["signals"]))}')})
    labels, taken = [], [(s["x"], s["y"]) for s in P["sources"]]
    for s in sorted((v for v in P["stations"] if v["r"] > 4),
                    key=lambda v: -v["r"]):
        if any(math.hypot(s["x"] - tx, s["y"] - ty) < 1.5
               for tx, ty in taken):
            continue
        labels.append({"n": s["n"], "x": s["x"], "y": s["y"]})
        taken.append((s["x"], s["y"]))
        if len(labels) >= 6:
            break
    P["labels"] = labels

    # named views for the view bar
    views = {"כל האגן": [P["bbox"][0] - 0.4, P["bbox"][2] + 0.4,
                         P["bbox"][1] - 0.4, P["bbox"][3] + 0.4]}
    for c in data["candidates"]:
        pts = [(c["itm"][0] / 1000, c["itm"][1] / 1000)]
        for s in c.get("site_members", []):
            if s in me.index:
                pts.append((float(me.loc[s, "x_itm"]) / 1000,
                            float(me.loc[s, "y_itm"]) / 1000))
        xs_, ys_ = [p[0] for p in pts], [p[1] for p in pts]
        short = c["name_he"].split("—")[0].strip()
        views[f"מכלול {short}"] = [min(xs_) - 1.8, max(xs_) + 1.8,
                                   min(ys_) - 1.8, max(ys_) + 1.8]
    if P["junctions"]:
        jxs = [j["x"] for j in P["junctions"]]
        jys = [j["y"] for j in P["junctions"]]
        views["מקטע-הצמתים"] = [min(jxs) - 2, max(jxs) + 2,
                                min(jys) - 2, max(jys) + 2]
    P["views"] = views
    return P


_MAP_JS = r"""
(function(){
  var D = window.__mapData;
  // canvas renderer: hundreds of markers stay smooth, and hit-testing is
  // done by Leaflet itself (the SVG renderer's hit region was unreliable
  // inside this RTL document)
  var map = L.map("figmap", {preferCanvas: true, crs: L.CRS.Simple,
    zoomSnap: 0.25,
    zoomDelta: 0.5, wheelPxPerZoomLevel: 90, minZoom: -8, maxZoom: 8,
    attributionControl: false, zoomControl: true});
  var P = function(x, y){ return L.latLng(y, x); };   // ITM-km -> lat/lng
  var B = function(v){ return L.latLngBounds(P(v[0], v[2]), P(v[1], v[3])); };

  function overlay(o, opts){
    var b = o.bounds;
    return L.imageOverlay(o.url, L.latLngBounds(P(b[0], b[1]),
                                                P(b[2], b[3])), opts);
  }
  var satLayer = D.satellite
    ? overlay(D.satellite, {opacity: 1, className: "sat-img"}).addTo(map)
    : null;
  var hsLayer = D.hillshade
    ? overlay(D.hillshade, {opacity: D.satellite ? 0.28 : 0.55,
                            className: "hs-img"})
    : null;
  if (hsLayer && !D.satellite) hsLayer.addTo(map);
  if (D.satellite){
    L.control.attribution({prefix: false})
      .addAttribution(D.satellite.credit).addTo(map);
  }
  function poly(pts, opts){
    return L.polyline(pts.map(function(p){ return P(p[0], p[1]); }), opts);
  }
  var chanMinor = L.layerGroup(D.channels.minor.map(function(l){
    return poly(l, {color:"#6ea0c8", weight:1, opacity:0.5}); })).addTo(map);
  var chanMajor = L.layerGroup(D.channels.major.map(function(l){
    return poly(l, {color:"#3f86bd", weight:2.6, opacity:0.95}); })).addTo(map);
  var pathLayer = L.layerGroup(D.paths.map(function(p){
    return poly(p.pts, {color:p.color, weight:4, opacity:0.9})
             .bindTooltip(p.name, {sticky:true}); })).addTo(map);
  var connLayer = L.layerGroup(D.connectors.map(function(c){
    return poly(c.pts, {color:c.color, weight:2.5, dashArray:c.dash,
                        opacity:0.9}).bindTooltip(c.name, {sticky:true});
  })).addTo(map);

  // stations, grouped per transport family so the family bar can toggle them
  window.__mapLayers = {};
  D.stations.forEach(function(s){
    var g = window.__mapLayers[s.f] ||
            (window.__mapLayers[s.f] = L.layerGroup().addTo(map));
    var quiet = (s.f === "other" || s.f === "below");
    L.circleMarker(P(s.x, s.y), {
      radius: s.r, color: quiet ? "#ffffff00" : "#fff", weight: quiet ? 0 : 1.4,
      fillColor: D.famColors[s.f], fillOpacity: quiet ? 0.45 : 0.9
    }).bindTooltip(s.t, {sticky:true}).bindPopup(s.t).addTo(g);
  });
  var srcLayer = L.layerGroup(D.sources.map(function(s){
    return L.marker(P(s.x, s.y), {icon: L.divIcon({className:"srcicon",
      html:'<div class="srcstar">★</div><div class="srclbl">' + s.n + '</div>',
      iconSize:[10,10]})}).bindTooltip(s.full, {sticky:true});
  })).addTo(map);
  var juncLayer = L.layerGroup(D.junctions.map(function(j){
    return L.marker(P(j.x, j.y), {icon: L.divIcon({className:"juncicon",
      html:'<div class="junctri">▲</div>', iconSize:[16,16]})})
      .bindTooltip(j.t, {sticky:true}).bindPopup(j.t);
  })).addTo(map);
  var lblLayer = L.layerGroup(D.labels.map(function(l){
    return L.marker(P(l.x, l.y), {icon: L.divIcon({className:"stnlblwrap",
      html:'<div class="stnlbl">' + l.n + '</div>', iconSize:[1,1]}),
      interactive:false});
  })).addTo(map);

  var overlays = {};
  if (satLayer) overlays['רקע תצ"א (Sentinel-2)'] = satLayer;
  if (hsLayer) overlays["הצללת-תבליט (DEM)"] = hsLayer;
  overlays["ערוצים ראשיים"] = chanMajor;
  overlays["ערוצים משניים"] = chanMinor;
  overlays["מסלולי נגר"] = pathLayer;
  overlays["נתיבים מוצהרים"] = connLayer;
  overlays["מקורות"] = srcLayer;
  overlays["צמתים חשודים"] = juncLayer;
  overlays["שמות תחנות"] = lblLayer;
  L.control.layers(null, overlays,
    {collapsed: true, position: "topright"}).addTo(map);

  // scale bar in kilometres (CRS.Simple: 1 unit = 1 km)
  var Scale = L.Control.extend({
    options: {position: "bottomleft"},
    onAdd: function(m){
      var d = L.DomUtil.create("div", "kmscale");
      function upd(){
        var p1 = m.latLngToContainerPoint(P(0, 0));
        var p2 = m.latLngToContainerPoint(P(1, 0));
        var pxPerKm = Math.abs(p2.x - p1.x), km = 1;
        while (pxPerKm * km < 60) km *= 2;
        while (pxPerKm * km > 180) km /= 2;
        d.style.width = Math.round(pxPerKm * km) + "px";
        d.innerHTML = '<span>' + (km < 1 ? km.toFixed(1) : km) + ' ק"מ</span>';
      }
      m.on("zoomend", upd); setTimeout(upd, 60);
      return d;
    }
  });
  map.addControl(new Scale());

  window.__mapFit = function(v){ map.fitBounds(B(v)); };
  window.__mapZoom = function(d){ map.zoomIn(d); };
  window.__mapSetFam = function(fk, on){
    var g = window.__mapLayers[fk];
    if (!g) return;
    if (on) { map.addLayer(g); } else { map.removeLayer(g); }
  };
  map.fitBounds(B(D.views["כל האגן"]));
  setTimeout(function(){ map.invalidateSize(); }, 120);
  // print always shows the whole basin with every layer on
  window.addEventListener("beforeprint", function(){
    Object.keys(window.__mapLayers).forEach(function(fk){
      map.addLayer(window.__mapLayers[fk]); });
    map.invalidateSize();
    map.fitBounds(B(D.views["כל האגן"]));
  });
})();
"""




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


def _fig_similarity(sim, lab, fam_of):
    """Figure 3 — numbered heatmap (station names go in a legend table, so the
    axes stay legible even at 25+ stations). Cell values shown. A family
    color strip runs along the right axis: the forensic question is whether
    the CHEMICAL clusters coincide with the TRANSPORT families."""
    n = len(lab)
    pos = list(range(1, n + 1))
    nums = [str(i + 1) for i in range(n)]
    show_text = n <= 30
    fig = go.Figure(go.Heatmap(
        z=sim.values, x=pos, y=pos,
        colorscale=[[0, "#c64a3b"], [0.3, "#d8c84a"], [0.7, "#4ea66b"],
                    [0.9, "#1f7a4d"], [1, "#0d4a2e"]],
        zmin=0, zmax=100, xgap=1, ygap=1,
        colorbar=dict(title="% דמיון"),
        text=sim.values.round(0).astype(int) if show_text else None,
        texttemplate="%{text}" if show_text else None,
        textfont=dict(size=9, color="rgba(20,20,20,0.75)"),
        customdata=[[f"{lab[i]} ↔ {lab[j]}" for j in range(n)] for i in range(n)],
        hovertemplate="%{customdata}<br>%{z:.0f}%<extra></extra>"))
    # family strips along BOTH axes (row strip at x=0.2, column strip at
    # y=0.2 — the reversed y-axis puts it on top), so a crossing can be
    # followed from either direction
    strip_colors = [FAMILIES[fam_of.get(s, "other")]["color"] for s in lab]
    strip_text = [f"{s} — {FAMILIES[fam_of.get(s, 'other')]['name_he']}"
                  for s in lab]
    fig.add_trace(go.Scatter(
        x=[0.2] * n, y=pos, mode="markers",
        marker=dict(symbol="square", size=11, color=strip_colors),
        text=strip_text, hoverinfo="text", showlegend=False))
    fig.add_trace(go.Scatter(
        x=pos, y=[0.2] * n, mode="markers",
        marker=dict(symbol="square", size=11, color=strip_colors),
        text=strip_text, hoverinfo="text", showlegend=False))
    fig.update_layout(
        font=_FONT, template="plotly_white",
        height=max(460, 24 * n + 150),
        xaxis=dict(title="מס' תחנה (ראו מקרא; פסי-הצבע = משפחת-הסעה)",
                   side="bottom", tickvals=pos, ticktext=nums,
                   range=[-0.4, n + 0.6], tickfont=dict(size=10)),
        yaxis=dict(autorange="reversed", tickvals=pos, ticktext=nums,
                   tickfont=dict(size=10)),
        margin=dict(l=40, r=10, t=30, b=50))
    return fig


def _fig_attenuation(data):
    """Figure 4 — attenuation & aging along the runoff path. Excluded
    stations (pumping-fed: pond residence breaks transport decay) are shown
    as grey markers with the exclusion reason on hover — exclusions should
    be visible, not merely declared."""
    me = data["max_event"].set_index("station_name")
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
            ex_x, ex_y, ex_t = [], [], []
            for s, tfv in (c.get("transfer_fed") or {}).items():
                if tfv.get("kind") == "pumping" and \
                        tfv.get("path_distance_m") and s in me.index:
                    sig = float(me.loc[s, "total_concentration"])
                    if sig > 0:
                        ex_x.append(round(tfv["path_distance_m"] / 1000, 2))
                        ex_y.append(sig)
                        ex_t.append(f"{s}<br>מוזנת-שאיבה — מוחרגת מהרגרסיה "
                                    f"(שהות/אידוי בבריכה)")
            if ex_x:
                fig.add_trace(go.Scatter(
                    x=ex_x, y=ex_y, mode="markers",
                    name="מוחרגות מהרגרסיה (מוזנות-שאיבה)",
                    marker=dict(size=10, color="#b9b5ad", symbol="triangle-up",
                                line=dict(width=1, color="#8d8a83")),
                    text=ex_t, hoverinfo="text"))
            fig.update_layout(
                font=_FONT, template="plotly_white", height=420,
                xaxis=dict(title="מרחק-מסלול מהמקור (ק\"מ)"),
                yaxis=dict(title="ΣPFAS (µg/L)", type="log"),
                yaxis2=dict(title="% קדם-חומרים", overlaying="y", side="right",
                            rangemode="tozero"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                            font=dict(size=10)),
                margin=dict(l=60, r=60, t=40, b=50))
            return fig
    return None


def _fig_fingerprints(data, fam_of, max_stations=10):
    """Figure 5 — relative composition of the key stations, ordered by
    transport family (source outward) with family separators, so the eye
    reads the weathering story along the pathways, not just by magnitude."""
    me = data["max_event"].sort_values("total_concentration", ascending=False)
    top = [n for n in me["station_name"]
           if n in data["fingerprint"].index][:max_stations]
    names = [n for fk in FAMILY_ORDER for n in top if fam_of.get(n) == fk]
    fp = data["fingerprint"].loc[names]
    fp = fp[[c for c in fp.columns if fp[c].sum() > 0]]
    fig = go.Figure()
    for comp in fp.columns:
        fig.add_trace(go.Bar(
            name=comp, x=[n[:22] for n in names], y=fp[comp],
            marker_color=COMPOUND_COLORS.get(comp, DEFAULT_COLOR)))
    # family group separators + labels
    bounds, i = [], 0
    while i < len(names):
        fk = fam_of.get(names[i], "other")
        j = i
        while j < len(names) and fam_of.get(names[j], "other") == fk:
            j += 1
        bounds.append((fk, i, j - 1))
        i = j
    for fk, a, b in bounds:
        fig.add_annotation(
            x=(a + b) / 2, y=1.06, yref="paper", showarrow=False,
            text=f'<span style="color:{FAMILIES[fk]["color"]}">'
                 f'{FAMILIES[fk]["short_he"]}</span>',
            font=dict(size=10))
        if b + 1 < len(names):
            fig.add_shape(type="line", x0=b + 0.5, x1=b + 0.5,
                          y0=0, y1=1, yref="paper",
                          line=dict(color="#b9b5ad", width=1, dash="dot"))
    fig.update_layout(
        font=_FONT, template="plotly_white", barmode="stack", height=460,
        yaxis=dict(title="אחוז מההרכב (%)", range=[0, 100]),
        legend=dict(orientation="h", yanchor="bottom", y=1.12, font=dict(size=10)),
        margin=dict(l=50, r=10, t=90, b=80))
    return fig, names


# ─── prose builders ─────────────────────────────────────────────────────────

def _list_he(items, limit=None):
    items = list(items)
    extra = 0
    if limit and len(items) > limit:
        extra = len(items) - limit
        items = items[:limit]
    if not items:
        return ""
    if len(items) == 1:
        s = items[0]
    else:
        # the "ועוד N" tail must stay OUTSIDE the vav-joined list — joining
        # it as a list item produced "וועוד" (caught by QA agent 2026-08-12)
        s = ", ".join(items[:-1]) + " ו" + items[-1]
    return s + (f" ועוד {extra}" if extra else "")


def _findings_overview(data):
    """3.1 — the spatial picture (opening paragraph of the findings)."""
    me = data["max_event"]
    sig = me[me["total_concentration"] >= MIN_SIGNAL_UG_L]
    if sig.empty:
        return "בתחום התיק לא נמצאו תחנות שריכוזן עולה על סף-האות הראייתי."
    ordered = sig.sort_values("total_concentration", ascending=False)
    top = ordered.head(3)
    top_list = _list_he(['"%s" (%s)' % (r.station_name,
                                        format(r.total_concentration, ",.2f"))
                         for r in top.itertuples()])
    orders = np.log10(ordered["total_concentration"].max()
                      / max(ordered["total_concentration"].min(), 1e-6))
    lead = ordered.iloc[0]
    second = ordered.iloc[1] if len(ordered) > 1 else None
    gap = (lead["total_concentration"] / second["total_concentration"]
           if second is not None and second["total_concentration"] > 0 else None)
    para = (f"בתחום התיק {data['n_stations']} תחנות דיגום. "
            f"{len(sig)} מהן מעל סף-האות ({MIN_SIGNAL_UG_L} מיקרוגרם לליטר) — "
            f"הן בסיס הראיות. "
            f"השאר מוצגות במפה אך אינן נספרות: בריכוזים כאלה ההרכב נשלט "
            f"רעש-מדידה. "
            f"הריכוזים משתרעים על פני כ-{orders:.0f} סדרי גודל. "
            f"שלוש התחנות הגבוהות: {top_list}.")
    if gap and gap >= 10:
        para += (f" הפער בין המובילה לבאה אחריה — פי {gap:,.0f} — מאפיין "
                 f"נקודת-מקור, לא רקע מפוזר.")
    excluded = data.get("excluded_stations") or []
    if excluded:
        para += (f" {len(excluded)} תחנות נוספות שבקובץ הנתונים הושמטו מגוף "
                 f"הדוח — מסלול-הנגר שלהן שייך לאגן אחר; הרשימה המלאה "
                 f"בנספח א'.")
    return para + " הפריסה המרחבית מוצגת באיור 1."


def _sig_he(v):
    """Σ formatting that keeps small values distinguishable."""
    return f"{v:,.3f}" if v < 0.1 else f"{v:,.2f}"


def _sigma_range_he(members):
    if not members:
        return ""
    lo, hi = members[-1]["sigma"], members[0]["sigma"]
    if len(members) == 1 or _sig_he(lo) == _sig_he(hi):
        return f"Σ≈{_sig_he(hi)}"
    return f"Σ בין {_sig_he(lo)} ל-{_sig_he(hi)}"


def _card(rows):
    """Compact data card: the numbers live here, the prose tells the story
    (readability decision, 2026-08-12). rows = [(label, value_html)]."""
    body = "".join(f"<tr><th>{_esc(l)}</th><td>{v}</td></tr>"
                   for l, v in rows if v not in (None, ""))
    return f'<table class="datacard">{body}</table>' if body else ""


def _endmember_profiles(data):
    """Empirical end-member signature per candidate: the fingerprint of its
    strongest site member (approved 2026-08-12). Returns
    {candidate_name: (station, fingerprint_row)}."""
    fp = data["fingerprint"]
    me = data["max_event"].set_index("station_name")
    out = {}
    for c in data["candidates"]:
        members = [s for s in c.get("site_members", [])
                   if s in fp.index and s in me.index]
        if not members:
            continue
        top = max(members, key=lambda s: float(me.loc[s, "total_concentration"]))
        out[c["name_he"]] = (top, fp.loc[top])
    return out


def _product_hints():
    p = os.path.join(os.path.dirname(__file__), "domains", "pfas",
                     "source_profiles.json")
    try:
        return json.load(open(p, encoding="utf-8")).get("product_hints_he", {})
    except OSError:
        return {}


def _findings_family_sections(data, fam_of, nar_families):
    """§3 per-family subsections: mechanism → observed → what would decide.
    The status chip is computed from the case data; the mechanism paragraph
    comes from region.json narrative (expert-reviewable data, not code)."""
    S = []
    c = data["candidates"][0] if data["candidates"] else None
    if c is None:
        return S
    me = data["max_event"].set_index("station_name")
    att = c.get("attenuation", {})
    gw_tiers = c.get("gw_tiers", {})
    # Explicit ACT/claim references are hagit's; other cases fall back to
    # generic phrasing pointing at their own action queue (chapter 6).
    if data["region"].get("name") == "hagit":
        decide = {
            "focus": "המוקד מעוגן במדידה ישירה — אינו תלוי בפעולה נוספת.",
            "stream": "יוכרע/יחודד ב: תאריך הסבת בריכה-1500 (ACT-3) ודיגום מזווג עוקב (ACT-4).",
            "pumped": "יוכרע ב: בירור סטטוס השאיבה והיקפה (ACT-5).",
            "piped": "יוכרע ב: דיגום קולחי מט\"ש חוף הכרמל (ACT-1) — תחזית P1: חתימת AFFF בקולחים.",
            "cascade": "יוכרע ב: דיגום מזווג נחל–קידוח באותו חלון-זמן (ACT-4).",
            "gw": "יוכרע ב: קובץ מפלסי תהום (ACT-2) — יחליף את ההנחה בגרדיאנטים מדודים ויכייל את k.",
            "other": "יוכרע ב: אישור/דחיית השערות ההזנה (A2) — אישור יעבירן למורד; דחייה תותיר ראיית-נגד.",
        }
    else:
        decide = {
            "focus": "המוקד מעוגן במדידה ישירה — אינו תלוי בפעולה נוספת.",
            "stream": "יוכרע בדיגום עוקב לאורך המסלול (ראו פרק 6).",
            "pumped": "יוכרע בבירור היקף השאיבה (ראו פרק 6).",
            "piped": "יוכרע בדיגום החוליה המתועלת (ראו פרק 6).",
            "cascade": "יוכרע בדיגום מזווג ערוץ–קידוחים באותו חלון-זמן (ראו פרק 6).",
            "gw": "יוכרע בקובץ מפלסי תהום — יחליף את ההנחה בגרדיאנטים מדודים (ראו פרק 6).",
            "other": "יוכרע באישור/דחיית השערות ההזנה של התיק (ראו לוח-הטענות).",
        }
    ems = _endmember_profiles(data)
    hints = _product_hints()
    from src.source_profiles import PROFILES as _PROFILES
    _key_by_name = {p.name_he: p.key for p in _PROFILES}

    sub = 1
    for key in ["focus", "stream", "pumped", "piped", "cascade", "gw", "other"]:
        members = _fam_members(data, fam_of, key)
        if not members:
            continue
        sub += 1
        f = FAMILIES[key]
        lvl, label = _family_status(key, c)
        S.append(f'<h3><span class="famdot" style="background:{f["color"]}">'
                 f'</span> 3.{sub} {_esc(f["name_he"])} '
                 f'<span class="conf {lvl}">{_esc(label)}</span></h3>')
        nf = (nar_families or {}).get(key, {})
        if nf.get("mechanism_he"):
            S.append(_bdi(f'<p>{_esc(nf["mechanism_he"])}</p>'))

        # Story-first prose; the numbers live in the data card below
        # (readability decision, 2026-08-12). Explicit station names in every
        # pathway card (user feedback 2026-08-12, item 2).
        obs = ""
        card = [("תחנות", str(len(members))),
                ("Σ (µg/L)", _sigma_range_he(members).replace("Σ בין ", "").replace("Σ≈", "≈"))]

        def _names_row(label="שמות התחנות", fmt=None):
            parts = [fmt(m) if fmt else _esc(m["name"]) for m in members]
            card.append((label, " · ".join(parts)))

        if key == "focus":
            # Group the source complexes by site (temporary name rule)
            member_names = {m["name"] for m in members}
            grouped = []
            for cand in data["candidates"]:
                site = [s for s in cand.get("site_members", []) if s in member_names]
                if site:
                    top = max(site, key=lambda s: float(me.loc[s, "total_concentration"]))
                    grouped.append((cand["name_he"], site, top))
            leftover = member_names - {s for _, site, _ in grouped for s in site}
            for cand_name, site, top in grouped:
                t_val = float(me.loc[top, "total_concentration"])
                obs += (f'מכלול "{_esc(cand_name)}" מונה {len(site)} נקודות '
                        f'דיגום, ובראשן "{_esc(top)}" ({_sig_he(t_val)} µg/L). ')
                _short = cand_name.split("—")[0].strip()
                card.append((f"תחנות מכלול {_short}",
                             " · ".join(_esc(s) for s in sorted(site))))
                em = ems.get(cand_name)
                prof_he, score = "", 0.0
                for st in data["stations"]:
                    if st["name"] == top:
                        prof_he, score = st["profile"], st["score"]
                hint = hints.get(_key_by_name.get(prof_he, ""), "")
                card.append((f"חתימת {cand_name.split('—')[0].strip()}",
                             f"{_esc(prof_he)} ({score:.0f}%)"))
                if hint:
                    card.append(("התאמת-מוצר (אינדיקטיבית)", _esc(hint)))
            if leftover:
                obs += (f"עוד {len(leftover)} נקודות מוקד מוצהרות/צמודות-אתר. ")
                card.append(("נקודות מוקד נוספות",
                             " · ".join(_esc(s) for s in sorted(leftover))))
            anchor = c.get("anchor_station")
            if anchor and anchor in me.index:
                obs += ("תחנת-העוגן אושרה כמייצגת אזור-מקור ידוע — "
                        "היא קו-הבסיס שאליו מושוות שאר התחנות. ")
            outfalls = data["region"].get("outfalls") or {}
            if any(o.get("momentary") for o in outfalls.values()):
                obs += ("מדידות-מוצא רגעיות מוצגות אך אינן נכנסות "
                        "לרגרסיות-העומס. ")
            obs += ("הדינמיקה הפנימית של כל מכלול — שונות בין תעלות "
                    "ומוצאים — עניינה של בחינת-אתר נפרדת ואינה נדונה "
                    "ברזולוציה האגנית.")

        elif key == "stream":
            obs += ("התחנות יושבות על מסלול הנגר הנגזר — רציפות הידראולית "
                    "ממשית. ")
            # explicit member names, in downstream order with path-km
            _km = {d["station"]: d["km"] for d in c.get("atten_series", [])}
            members.sort(key=lambda m: _km.get(m["name"], float("inf")))
            _names_row("התחנות (לפי סדר במורד)",
                       lambda m: (f'{_esc(m["name"])} ({_km[m["name"]]:.1f} ק"מ)'
                                  if m["name"] in _km else _esc(m["name"])))
            aging_ok = att.get("r_precursor") is not None and att["r_precursor"] <= -0.4
            r = att.get("r_conc")
            if aging_ok and r is not None and r <= -0.4:
                obs += ("התמונה לאורך הגזע היא הצפויה ממקור נקודתי: הריכוז "
                        "דועך והחתימה מזדקנת ככל שמתרחקים מן המוקד. ")
            elif aging_ok:
                obs += ("החתימה מזדקנת בעקביות עם המרחק; דעיכת הריכוז "
                        "עצמה אינה חד-משמעית בחתך הנוכחי. ")
            elif r is not None and r >= 0.4:
                obs += ("הריכוז דווקא עולה במורד — ראיית-נגד המרמזת על "
                        "מקור נוסף בין הנקודות. ")
            if nf.get("observed_he"):
                obs += _esc(nf["observed_he"]) + " "
            card.append(("דעיכת Σ", f"Spearman r={att.get('r_conc')} "
                         f"(n={att.get('n')}, {att.get('basis','')})"))
            card.append(("הזדקנות (קדם-חומרים)", f"r={att.get('r_precursor')}"))
            # empirical end-member affinity along the stem
            if len(ems) >= 2:
                fp = data["fingerprint"]
                import numpy as _np
                def _cos(a, b):
                    na = float((_np.array(a) ** 2).sum()) ** 0.5
                    nb = float((_np.array(b) ** 2).sum()) ** 0.5
                    return float((_np.array(a) * _np.array(b)).sum()) / (na * nb) if na and nb else 0
                counts = {}
                far_aff = []
                ordered = sorted(members, key=lambda m: -m["sigma"])
                for m in members:
                    if m["name"] not in fp.index:
                        continue
                    row = fp.loc[m["name"]]
                    best = max(ems.items(), key=lambda kv: _cos(row, kv[1][1]))[0]
                    counts[best] = counts.get(best, 0) + 1
                if counts:
                    short = {k.split("—")[0].strip(): v for k, v in counts.items()}
                    card.append(("קרבה לחתימות-המוקד (קצוות אמפיריים)",
                                 " · ".join(f"{_esc(k)}: {v}" for k, v in short.items())))
                    obs += ("השוואת כל תחנת-גזע לחתימות-המוקד האמפיריות של "
                            "התיק מלמדת איזה מוקד קרוב יותר להרכבה — "
                            "ראו כרטיס-הנתונים. ")
            jfs = c.get("junction_findings", [])
            if jfs:
                obs += (f"מבחן הצטרפות-העומס מסמן {len(jfs)} מקטעים שבהם "
                        "דפוס הריכוז או ההרכב אינו מוסבר בהסעה בלבד — "
                        "אינדיקציות-צומת, לא הוכחות; פירוט בכרטיס ובפרק "
                        "המסקנות. ")
                for jf in jfs:
                    # the change is measured AT the downstream station of the
                    # segment — name both ends explicitly (user feedback
                    # 2026-08-12, item 3)
                    seg = jf.get("segment") or ("", "")
                    card.append((
                        f'צומת חשוד {jf["km"][0]:.0f}–{jf["km"][1]:.0f} ק"מ',
                        _esc(f'השינוי נמדד ב"{seg[1]}" (התחנה הקודמת: '
                             f'"{seg[0]}"); ' + "; ".join(jf["signals"]))))

        elif key == "pumped":
            obs += ("התחנות אינן על הערוץ אך יורשות את מי הנחל דרך שאיבה "
                    "מוצהרת; הרכבן עקבי עם ירושה כזו, והן מוחרגות "
                    "מרגרסיית הדעיכה (שהות-בריכה מנתקת ריכוז ממרחק). ")
            _names_row("התחנות (התאמת-פרופיל)",
                       lambda m: f'{_esc(m["name"])} ({m["score"]:.0f}%)')

        elif key == "piped":
            anchor = c.get("anchor_station")
            if anchor and anchor in me.index:
                a_sig = float(me.loc[anchor, "total_concentration"])
                hi = members[0]["sigma"]
                obs += ("שרשרת-המיהול הנצפית עקבית עם נתיב מתועל: ירידה "
                        "של סדרי-גודל בין המוצא למאגרים, ללא תלות במרחק. ")
                card.append(("שרשרת-מיהול",
                             f"{_sig_he(a_sig)} ← {_sig_he(hi)} µg/L "
                             f"(~{np.log10(a_sig / max(hi, 1e-9)):.1f} סדרי-גודל)"))
            obs += ("החוליה האמצעית — הקולחים עצמם — טרם נדגמה; השרשרת "
                    "מוצהרת אך לא סגורה מדידתית.")
            _names_row()

        elif key == "cascade":
            if nf.get("observed_he"):
                obs += _esc(nf["observed_he"]) + " "
            cmeta = c.get("cascade_meta", {})
            if any(cmeta.get(m["name"], {}).get("coarse") for m in members):
                obs += ("בקידוח-הפקה הצמידות נבחנת עד רדיוס אזור-הלכידה "
                        "המוצהר (500 מ', גס) — השאיבה מטשטשת את מיקום "
                        "הדגימה, ולכן הערוץ יכול להזין את הקידוח גם "
                        "כשראש-הבאר רחוק ממנו. ")
            if c.get("n_surface_down", 0) == 0:
                obs += ("בתיק אין דיגום מי-ערוץ על המסלול — "
                        "מבחן-הפרקציונציה ימתין לדיגום המזווג. ")
            obs += "נתיב מועמד: לא ראיה ישירה ולא ראיית-נגד."

            def _casc_fmt(m):
                mm = cmeta.get(m["name"], {})
                if not mm:
                    return _esc(m["name"])
                tag = " — דרך אזור-הלכידה, גס" if mm.get("coarse") else ""
                return (f'{_esc(m["name"])} ({mm.get("offset_m", "?")} מ\' '
                        f'מהערוץ, בק"מ {mm.get("path_km", "?")}{tag})')
            _names_row("הקידוחים (מרחק מהערוץ)", _casc_fmt)

        elif key == "gw":
            comp = {}
            n_prod = 0
            for m in members:
                gt = gw_tiers.get(m["name"], {})
                t = gt.get("tier", "?")
                comp[t] = comp.get(t, 0) + 1
                if gt.get("well_class") == "production":
                    n_prod += 1
            obs += ("שיוך הקידוחים לעננה נשען כולו על כיוון-זרימה מונח, "
                    "ולכן תומך אך אינו מאשש. ")
            if n_prod:
                obs += (f"{n_prod} מהם קידוחי-הפקה — דגימתם משקללת "
                        "אזור-לכידה בלתי-מוגדר, מדרגתם מדווחת כטווח "
                        "וריכוזם חסם-תחתון. ")
            obs += ("כלל 'מדרגה 4 עם זיהום = ממצא' חל על קידוחי-ניטור; "
                    "בקידוח-הפקה הצעד הנגזר הוא חיבוק בקידוחי-ניטור.")
            comp_he = ", ".join(f"מדרגה {t}: {n}" for t, n in
                                sorted(comp.items()) if t != "up")
            if comp.get("up"):
                comp_he += f", במעלה: {comp['up']}"
            card.append((f"פילוח מדרגות (k={GW_PLUME_K})", _esc(comp_he)))
            if n_prod:
                card.append(("קידוחי-הפקה", f"{n_prod} (טווח-מדרגה עד 500 מ')"))

            def _gw_fmt(m):
                gt = gw_tiers.get(m["name"], {})
                t = gt.get("tier", "?")
                t_lbl = "במעלה" if t == "up" else f"מדרגה {t}"
                if gt.get("tier_best") and gt["tier_best"] != t:
                    t_lbl += f" (עד {gt['tier_best']} בטווח-הלכידה)"
                return f'{_esc(m["name"])} ({t_lbl})'
            _names_row("הקידוחים (מדרגת-עננה)", _gw_fmt)

        elif key == "other":
            obs += ("תחנות שאינן משויכות לאף נתיב של המועמדים: פרופיל דומה "
                    "בהן אינו נזקף לזכות איש — הוא נרשם כראיית-נגד או "
                    "כראיית-נגד מותנית, בחלקן תלוי בהשערות שבבדיקה.")
            _names_row()

        S.append(_bdi(f"<p>{obs}</p>"))
        card_html = _card(card)
        if card_html:
            S.append(_bdi(card_html))
        S.append(f'<p class="decide">{_bdi(_esc(decide[key]))}</p>')
    return S


def _discussion_prose(data, narrative=None):
    """Interpretive discussion: weighs the axes, states the competing
    explanations, and closes with the authored synthesis (region.json)."""
    P = []
    for c in data["candidates"]:
        chem = c["chem_share_weighted"] * 100
        axes = []
        if c["n_downgradient"]:
            axes.append("ההידרולוגי")
        if chem >= 30:
            axes.append("הכימי")
        if c["emission_evidence"]:
            axes.append("ראיית-הפליטה")

        para = (f"הערכת האתר \"{c['name_he']}\" נשענת על עקרון ההתלכדות: אף "
                f"ציר ראיה בודד אינו מזהה מקור, ורק צירופם של כמה צירים "
                f"בלתי-תלויים מבסס הערכה. ")
        if len(axes) >= 3:
            para += (f"במקרה זה מתקיימים שלושת הצירים — {_list_he(axes)}. "
                     f"החפיפה הכימית בין החתימות שנמדדו במורד לבין הפרופיל "
                     f"הצפוי מן האתר עומדת על {chem:.0f} אחוזים בשקלול "
                     f"לפי עוצמת האות, כלומר התחנות המרוכזות — אלו שהראיה "
                     f"שלהן אמינה יותר — הן גם התואמות ביותר. ")
        else:
            para += (f"במקרה זה מתקיימים {len(axes)} צירים בלבד "
                     f"({_list_he(axes)}), ולפיכך ההערכה מסויגת מטבעה. ")
        if c.get("anchor_station"):
            para += (f"משקל מיוחד נודע לתחנת-העוגן \"{c['anchor_station']}\", "
                     f"הממוקמת בשטח האתר עצמו: היא קושרת את הזיהום לא רק "
                     f"לאזור אלא לנקודה, ומעגנת את עוצמתו במדידה ישירה. ")
        para += f"סיכומם של אלה מוביל לדירוג <b>{c['tier']}</b>."
        P.append(para)

        if c["evidence_against"]:
            para = ("בחינה מקצועית מחייבת אינה מסתפקת בראיות התומכות, ועל כן "
                    "נבחנו במפורש ההסברים החלופיים והממצאים שאינם מתיישבים "
                    "עם ההערכה. ")
            para += " ".join(c["evidence_against"])
            para += (" משקלן של הסתייגויות אלו אינו מבטל את ההערכה, אך הוא "
                     "מגדיר את גבולותיה: הן מצביעות על כך שתמונת הזיהום "
                     "באזור עשויה שלא להיות מוסברת במלואה על-ידי מקור יחיד, "
                     "ומחייבות בחינת מקורות או נתיבים נוספים.")
            P.append(para)
        elif c.get("would_refute"):
            P.append("לא נמצאו בנתונים הנוכחיים ממצאים הסותרים את ההערכה. "
                     "עם זאת, ומתוך הקפדה על בחינה עצמית, נקבעו מראש "
                     "הבדיקות שתוצאתן הייתה מפריכה אותה: "
                     + _list_he([w for w in c["would_refute"]]) + ".")

    if narrative and narrative.get("synthesis_he"):
        P.append(narrative["synthesis_he"])

    P.append("לבסוף, יש לקרוא את מסקנות הדוח בכפוף למגבלת השפה המחייבת "
             "בתחום זה: התאמת פרופיל כימי, גבוהה ככל שתהיה, משמעה \"עקבי עם\" "
             "ולא \"נגרם על-ידי\"; כיוון זרימה כשלעצמו אינו מזהה מקור; "
             "ומועמד מדורג — ליבה, משני או רקע מקומי — לעולם אינו מוכרז "
             "\"המקור\". הדוח נועד לתעדף חקירה ולכוון משאבי דיגום, לא להכריע "
             "אחריות.")
    return P


# ─── report assembly ────────────────────────────────────────────────────────

# Family filter: chips toggle families; map traces flip visibility, the
# similarity matrix and fingerprint bars are rebuilt from the plain-JSON
# copies in __famData. Print always shows the full (all-on) state.
_FAM_JS = r"""
(function(){
  var D = window.__famData;
  var active = {};
  var chips = document.querySelectorAll(".famchip[data-fam]");
  chips.forEach(function(ch){ active[ch.dataset.fam] = true; });

  function famOf(n){ return D.byStation[n] || "other"; }

  function applyMap(){
    if (!window.__mapSetFam) return;
    Object.keys(active).forEach(function(fk){
      window.__mapSetFam(fk, !!active[fk]);
    });
  }

  function stationChecked(n){
    var box = document.querySelector(
      '.simsel[data-station="' + CSS.escape(n) + '"]');
    return !box || box.checked;
  }

  function applySim(){
    var el = document.getElementById("figsim");
    if (!el) return;
    var idx = [];
    D.simLabels.forEach(function(n, i){
      if (active[famOf(n)] && stationChecked(n)) idx.push(i); });
    var k = idx.length;
    if (k < 2) return;  // a similarity matrix needs at least two stations
    var pos = []; for (var q = 1; q <= k; q++) pos.push(q);
    var nums = idx.map(function(i){ return String(i + 1); });
    var z = idx.map(function(i){
      return idx.map(function(j){ return D.simZ[i][j]; }); });
    var cust = idx.map(function(i){
      return idx.map(function(j){
        return D.simLabels[i] + " ↔ " + D.simLabels[j]; }); });
    var heat = {type:"heatmap", z:z, x:pos, y:pos, zmin:0, zmax:100,
      xgap:1, ygap:1,
      colorscale:[[0,"#c64a3b"],[0.3,"#d8c84a"],[0.7,"#4ea66b"],
                  [0.9,"#1f7a4d"],[1,"#0d4a2e"]],
      colorbar:{title:"% דמיון"},
      texttemplate:(k <= 30 ? "%{z:.0f}" : ""),
      textfont:{size:9, color:"rgba(20,20,20,0.75)"},
      customdata:cust,
      hovertemplate:"%{customdata}<br>%{z:.0f}%<extra></extra>"};
    var cols = idx.map(function(i){ return D.famColors[famOf(D.simLabels[i])]; });
    var txts = idx.map(function(i){
      return D.simLabels[i] + " — " + D.famNames[famOf(D.simLabels[i])]; });
    var stripY = {type:"scatter", mode:"markers",
      x:pos.map(function(){ return 0.2; }), y:pos,
      marker:{symbol:"square", size:11, color:cols},
      text:txts, hoverinfo:"text", showlegend:false};
    var stripX = {type:"scatter", mode:"markers",
      x:pos, y:pos.map(function(){ return 0.2; }),
      marker:{symbol:"square", size:11, color:cols},
      text:txts, hoverinfo:"text", showlegend:false};
    var lay = JSON.parse(JSON.stringify(el.layout || {}));
    lay.xaxis = lay.xaxis || {};  lay.yaxis = lay.yaxis || {};
    lay.xaxis.tickvals = pos; lay.xaxis.ticktext = nums;
    lay.xaxis.range = [-0.4, k + 0.6];
    lay.yaxis.tickvals = pos; lay.yaxis.ticktext = nums;
    lay.yaxis.autorange = "reversed";
    lay.height = Math.max(380, 24 * k + 150);
    Plotly.react("figsim", [heat, stripY, stripX], lay,
      {responsive:true, displayModeBar:false});
  }

  function applyFp(){
    var el = document.getElementById("figfp");
    if (!el) return;
    var keep = [];
    D.fpStations.forEach(function(n, i){ if (active[famOf(n)]) keep.push(i); });
    var xs = keep.map(function(i){ return D.fpStations[i].slice(0, 22); });
    var traces = D.fpCompounds.map(function(c){
      return {type:"bar", name:c, x:xs,
        y:keep.map(function(i){ return D.fpValues[c][i]; }),
        marker:{color:D.fpColors[c]}};
    });
    var lay = JSON.parse(JSON.stringify(el.layout || {}));
    lay.shapes = []; lay.annotations = [];
    // regenerate family separators for the kept subset
    var i = 0, groups = [];
    while (i < keep.length){
      var fk = famOf(D.fpStations[keep[i]]), j = i;
      while (j < keep.length && famOf(D.fpStations[keep[j]]) === fk) j++;
      groups.push([fk, i, j - 1]); i = j;
    }
    groups.forEach(function(g){
      lay.annotations.push({x:(g[1] + g[2]) / 2, y:1.06, yref:"paper",
        showarrow:false, font:{size:10},
        text:'<span style="color:' + D.famColors[g[0]] + '">' +
             D.famShort[g[0]] + "</span>"});
      if (g[2] + 1 < keep.length)
        lay.shapes.push({type:"line", x0:g[2] + 0.5, x1:g[2] + 0.5,
          y0:0, y1:1, yref:"paper",
          line:{color:"#b9b5ad", width:1, dash:"dot"}});
    });
    Plotly.react("figfp", traces, lay,
      {responsive:true, displayModeBar:false});
  }

  function apply(){ applyMap(); applySim(); applyFp(); }

  chips.forEach(function(ch){
    ch.addEventListener("click", function(){
      active[ch.dataset.fam] = !active[ch.dataset.fam];
      ch.classList.toggle("on", active[ch.dataset.fam]);
      apply();
    });
  });
  var allBtn = document.getElementById("famall");
  if (allBtn) allBtn.addEventListener("click", function(){
    chips.forEach(function(ch){
      active[ch.dataset.fam] = true; ch.classList.add("on"); });
    apply();
  });
  // per-station selection (matrix legend checkboxes)
  document.querySelectorAll(".simsel").forEach(function(box){
    box.addEventListener("change", applySim);
  });
  var selAll = document.getElementById("simselall");
  if (selAll) selAll.addEventListener("click", function(){
    document.querySelectorAll(".simsel").forEach(function(b){ b.checked = true; });
    applySim();
  });
  var selNone = document.getElementById("simselnone");
  if (selNone) selNone.addEventListener("click", function(){
    document.querySelectorAll(".simsel").forEach(function(b){ b.checked = false; });
    applySim();
  });
  // group buttons: one click checks/unchecks a whole transport family
  document.querySelectorAll(".simsel-fam").forEach(function(btn){
    btn.addEventListener("click", function(){
      var fam = btn.dataset.fam, boxes = [];
      document.querySelectorAll(".simsel").forEach(function(b){
        if (famOf(b.dataset.station) === fam) boxes.push(b);
      });
      var any = boxes.some(function(b){ return b.checked; });
      boxes.forEach(function(b){ b.checked = !any; });
      btn.classList.toggle("off", any);
      applySim();
    });
  });
  window.addEventListener("beforeprint", function(){
    chips.forEach(function(ch){
      active[ch.dataset.fam] = true; ch.classList.add("on"); });
    document.querySelectorAll(".simsel").forEach(function(b){ b.checked = true; });
    apply();
  });
})();
"""

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
.famdot{display:inline-block;width:10px;height:10px;border-radius:50%;
margin-left:6px;vertical-align:baseline}
.fambar{display:flex;flex-wrap:wrap;gap:7px;align-items:center;
background:#faf8f4;border:1px solid var(--line);border-radius:10px;
padding:10px 14px;margin:12px 0 18px}
.fambar-t{font-size:.85rem;color:var(--ink2);font-weight:600}
.famchip{border:1.5px solid var(--line);background:#fff;color:var(--ink3);
border-radius:100px;padding:4px 12px;font-size:.82rem;cursor:pointer;
font-family:inherit;opacity:.55}
.famchip.on{color:var(--ink);border-color:#b9b5ad;opacity:1}
.famchip.all{opacity:1;font-weight:600}
.decide{font-size:.88rem;color:var(--ink2);background:#faf8f4;
border-right:3px solid var(--warn);padding:7px 12px;margin:6px 0 18px}
table.datacard{width:auto;min-width:55%;border-collapse:collapse;
font-size:.82rem;margin:4px 0 10px;background:#faf8f4;
border:1px solid var(--line);border-radius:6px}
table.datacard th{text-align:right;font-weight:600;color:var(--ink3);
padding:4px 10px;border-bottom:1px solid var(--line);white-space:nowrap;
vertical-align:top;background:transparent}
table.datacard td{padding:4px 10px;border-bottom:1px solid var(--line);
color:var(--ink2)}
table.datacard tr:last-child th,table.datacard tr:last-child td{border-bottom:none}
.provnote{font-size:.78rem;color:var(--ink3);font-style:italic;margin:4px 0 14px}
.simsel-bar{display:flex;gap:8px;align-items:center;margin:8px 0 4px;flex-wrap:wrap}
.simsel-btn{border:1.5px solid var(--line);background:#fff;color:var(--ink2);
border-radius:7px;padding:3px 12px;font-size:.8rem;cursor:pointer;font-family:inherit}
.simsel-btn:hover{border-color:#b9b5ad}
.simsel-fam{display:inline-flex;align-items:center;gap:5px}
.simsel-fam.off{opacity:.45;text-decoration:line-through}
.mapviews{display:flex;flex-wrap:wrap;gap:7px;align-items:center;
  margin:10px 0 6px;padding:9px 12px;background:#fff;
  border:1px solid var(--line);border-radius:10px}
.mapview-btn{border:1.5px solid var(--line);background:#fff;color:var(--ink2);
  border-radius:8px;padding:6px 14px;font-size:.92rem;font-family:inherit;
  cursor:pointer;font-weight:600;min-width:42px}
.mapview-btn:hover{border-color:var(--accent);color:var(--accent)}
.mapview-btn.on{background:var(--accent);border-color:var(--accent);color:#fff}
/* Leaflet map (figure 1) */
#figmap{width:100%;border:1px solid var(--line);border-radius:10px;
  background:#eae6dd;direction:ltr}
#figmap .leaflet-container{font-family:inherit;background:#eae6dd}
#figmap .hs-img{image-rendering:auto;filter:contrast(1.05);
  mix-blend-mode:multiply}
#figmap .sat-img{filter:saturate(1.08) brightness(1.04)}
#figmap .leaflet-control-attribution{direction:rtl;font-size:.72rem;
  background:rgba(255,255,255,.8)}
#figmap .leaflet-control-layers{direction:rtl;font-size:.82rem;
  background:rgba(255,255,255,.92);border:1px solid var(--line);
  box-shadow:none;padding:6px 8px;line-height:1.7}
#figmap .leaflet-control-layers label{font-weight:600;color:var(--ink2)}
#figmap .leaflet-popup-content,#figmap .leaflet-tooltip{direction:rtl;
  text-align:right;font-size:.85rem;line-height:1.55}
/* label wrappers overflow their 1px icon box — without this they swallow
   clicks meant for the station markers underneath */
#figmap .stnlblwrap,#figmap .stnlbl,#figmap .srclbl{pointer-events:none}
#figmap .srcstar,#figmap .junctri{pointer-events:auto}
#figmap .srcicon{background:none;border:none}
#figmap .srcstar{position:absolute;transform:translate(-50%,-55%);
  font-size:26px;color:#f4b942;text-shadow:0 0 3px #5a4200,0 0 1px #5a4200;
  line-height:1}
#figmap .srclbl{position:absolute;transform:translate(-50%,14px);
  white-space:nowrap;font-size:12.5px;font-weight:700;color:#ffdf8a;
  text-shadow:0 0 4px #000,0 0 2px #000,0 1px 2px #000}
#figmap .juncicon{background:none;border:none}
#figmap .junctri{position:absolute;transform:translate(-50%,-150%);
  font-size:15px;color:#d97a2c;text-shadow:0 0 2px #7a3500;line-height:1}
#figmap .stnlblwrap{background:none;border:none}
#figmap .stnlbl{position:absolute;transform:translate(-50%,-24px);
  white-space:nowrap;font-size:11.5px;font-weight:700;color:#fff;
  text-shadow:0 0 4px #000,0 0 2px #000,0 1px 2px #000}
#figmap .kmscale{height:22px;border:2px solid #1c1f24;border-top:none;
  background:rgba(255,255,255,.65);position:relative}
#figmap .kmscale span{position:absolute;bottom:2px;width:100%;
  text-align:center;font-size:11px;font-weight:600;color:#1c1f24}
.simsel-hint{font-size:.75rem;color:var(--ink3)}
.simsel{cursor:pointer}
.csm{padding:6px 2px}
.csm-src{background:#f3ecf7;border:1.5px solid #7a3d9e;border-radius:9px;
padding:10px 14px;font-size:.95rem;text-align:center}
.csm-flow{text-align:center;color:var(--ink3);font-size:.85rem;margin:6px 0}
.csm-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}
.csm-card{border:1px solid var(--line);border-right:4px solid;
border-radius:8px;padding:9px 12px;background:#fff}
.csm-head{display:flex;align-items:center;gap:7px;flex-wrap:wrap;
font-size:.9rem;margin-bottom:5px}
.csm-head .famdot{margin-left:0}
.csm-row{font-size:.8rem;color:var(--ink2);margin:3px 0}
.csm-rec{color:var(--ink3)}
@media print{
  .wrap{box-shadow:none;max-width:100%}body{background:#fff;font-size:12pt}
  h2{page-break-after:avoid}h3{page-break-after:avoid}
  .figure{page-break-inside:avoid}
  .concl{page-break-inside:avoid}table{page-break-inside:avoid}
  .csm-card{page-break-inside:avoid}.decide{page-break-inside:avoid}
  table.datacard{page-break-inside:avoid}
  p{orphans:2;widows:2}
  .draft{display:none}.fambar{display:none}.mapviews{display:none}
  .simsel{display:none}.simsel-bar{display:none}
  #figmap .leaflet-control-zoom{display:none}
  #figmap .leaflet-control-layers{display:none}
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

    fam_of = _classify_families(data)
    map_payload = _map_payload(data, fam_of)
    map_views = map_payload["views"]
    sim_df, sim_lab, sim_clusters, sim_pairs = _similarity(data)
    fig_sim = _fig_similarity(sim_df, sim_lab, fam_of)
    n_sim = len(sim_lab)
    fig_att = _fig_attenuation(data)
    fig_fp, fp_names = _fig_fingerprints(data, fam_of)

    def _plot(fig, div_id, config=None):
        cfg = config or "{responsive:true, displayModeBar:false}"
        return (f'<div id="{div_id}"></div><script>window.__figs=window.__figs||{{}};'
                f'window.__figs["{div_id}"]={fig.to_json()};'
                f'Plotly.newPlot("{div_id}", window.__figs["{div_id}"], '
                f'{{}}, {cfg});'
                f'</script>')

    S = []
    S.append(f"<h1>דוח חקירה סביבתית-הידרולוגית<br>{_esc(region.get('name_he', region_name))}</h1>")
    S.append(f'<div class="meta">השירות ההידרולוגי, רשות המים · מהדורת עבודה '
             f'{region.get("_round","")} · 27 ביולי 2026 · גרסת מתודולוגיה '
             f'<span dir="ltr">{git}</span></div>')
    S.append('<div class="draft">טיוטת תבנית לעיון — מבנה הדוח טרם קובע. '
             'סולם-הוודאות (גבוהה/בינונית/נמוכה + בסיס) מאושר.</div>')
    # Narrative-staleness guard: authored narrative restates interpretation
    # on top of computed facts, and goes stale silently when the claims
    # board moves on (caught by the user 2026-08-11: kesariya's synthesis
    # predated the Or-Akiva pathway finding). Dates compare lexically
    # (ISO). Warn in the report AND on stderr at generation time.
    claims_meta = _load(os.path.join(region["_base"], "claims.json")) or {}
    nar_upd, claims_upd = nar.get("updated"), claims_meta.get("updated")
    if nar_upd and claims_upd and nar_upd < claims_upd:
        warn = (f"הנרטיב המחברי של התיק עודכן לאחרונה ב-{nar_upd}, אך "
                f"לוח-הטענות התעדכן ב-{claims_upd} — פרקי הרקע, העילה "
                f"והסינתזה עשויים שלא לשקף טענות חדשות. נדרש סבב-עדכון "
                f"נרטיב.")
        S.append(f'<div class="draft" style="background:#b5541f">⚠ {warn}</div>')
        print(f"WARNING [{region_name}]: stale narrative — {nar_upd} < "
              f"{claims_upd}", file=sys.stderr)

    # 1 — introduction & background
    S.append("<h2>1. מבוא ורקע</h2>")
    if nar.get("background_he"):
        S.append(_bdi(f"<p>{_esc(nar['background_he'])}</p>"))
    if nar.get("setting_he"):
        S.append("<h3>1.1 המסגרת הגיאו-הידרולוגית</h3>")
        S.append(_bdi(f"<p>{_esc(nar['setting_he'])}</p>"))
    if nar.get("trigger_he"):
        S.append("<h3>1.2 עילת החקירה</h3>")
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

    # 3 — findings (organized by transport family)
    S.append("<h2>3. ממצאים</h2>")
    # family filter bar (interactive HTML only; hidden in print)
    present = [fk for fk in FAMILY_ORDER
               if any(fam_of.get(s["name"]) == fk for s in data["stations"])]
    chips = "".join(
        f'<button class="famchip on" data-fam="{fk}">'
        f'<span class="famdot" style="background:{FAMILIES[fk]["color"]}">'
        f'</span>{_esc(FAMILIES[fk]["name_he"])}</button>'
        for fk in present)
    S.append(f'<div class="fambar"><span class="fambar-t">סינון לפי '
             f'משפחת-הסעה:</span>{chips}'
             f'<button class="famchip all" id="famall">הכל</button></div>')
    S.append(_bdi(f"<p>{_findings_overview(data)}</p>"))
    view_btns = "".join(
        f'<button type="button" class="mapview-btn" data-view="{_esc(k)}">'
        f'{_esc(k)}</button>' for k in map_views)
    S.append(
        f'<div class="mapviews"><span class="fambar-t">תצוגה:</span>'
        f'{view_btns}'
        f'<button type="button" class="mapview-btn" id="mapzin">+</button>'
        f'<button type="button" class="mapview-btn" id="mapzout">−</button>'
        f'</div>')
    # aspect-matched height so the map fills the column
    _bx = map_payload["bbox"]
    _mh = int(min(1100, max(600,
                  820 * (_bx[3] - _bx[1]) / max(_bx[2] - _bx[0], 1e-6) + 60)))
    S.append(f'<div class="figure"><div id="figmap" '
             f'style="height:{_mh}px"></div>'
             f'<div class="figcap">איור 1: מפת התיק על רקע תבליט מוצלל '
             f'(DEM) — תחנות בצבעי משפחות-ההסעה (גודל ∝ Σ), רשת-הערוצים, '
             f'מסלולי הנגר של המועמדים, נתיבים מוצהרים, ומשולשי '
             f'צומת-חשוד. ניווט: כפתורי-התצוגה שמעל · גלגלת = זום · '
             f'גרירה = הזזה · לחיצה על תחנה = פרטים · תיבות-השכבות '
             f'שבפינה מדליקות/מכבות שכבות. קואורדינטות ITM בק"מ.'
             f'</div></div>')
    S.append("<script>window.__mapData=" +
             json.dumps(map_payload, ensure_ascii=False) + ";" + _MAP_JS +
             r"""
(function(){
  document.querySelectorAll(".mapview-btn[data-view]").forEach(function(b){
    b.addEventListener("click", function(){
      window.__mapFit(window.__mapData.views[b.dataset.view]);
      document.querySelectorAll(".mapview-btn[data-view]").forEach(
        function(o){ o.classList.toggle("on", o === b); });
    });
  });
  var zi = document.getElementById("mapzin");
  var zo = document.getElementById("mapzout");
  if (zi) zi.addEventListener("click", function(){ window.__mapZoom(0.5); });
  if (zo) zo.addEventListener("click", function(){ window.__mapZoom(-0.5); });
})();
</script>""")
    # conceptual site model
    nar_families = nar.get("families", {})
    csm = _csm_html(data, fam_of, nar_families)
    if csm:
        S.append(f'<div class="figure">{csm}'
                 f'<div class="figcap">איור 2: מודל-אתר קונספטואלי — '
                 f'נתיבי ההסעה, קצבם, הבליה הצפויה בכל נתיב ומעמדו הראייתי '
                 f'(מחושב מנתוני התיק).</div></div>')
        if nar_families.get("_provenance"):
            S.append(f'<p class="provnote">{_esc(nar_families["_provenance"])}</p>')
    # per-family findings
    S.extend(_findings_family_sections(data, fam_of, nar_families))
    me_idx = data["max_event"].set_index("station_name")
    # one-click group selection for the matrix (user feedback 2026-08-12,
    # item 5): a button per family present toggles all its stations at once
    sim_group_btns = "".join(
        f'<button type="button" class="simsel-btn simsel-fam" data-fam="{k}">'
        f'<span class="famdot" style="background:{FAMILIES[k]["color"]}">'
        f'</span>{_esc(FAMILIES[k]["short_he"])} '
        f'({sum(1 for s in sim_lab if fam_of.get(s, "other") == k)})</button>'
        for k in FAMILY_ORDER
        if any(fam_of.get(s, "other") == k for s in sim_lab))
    legend_rows = "".join(
        f'<tr><td><input type="checkbox" class="simsel" '
        f'data-station="{_esc(s)}" checked></td>'
        f"<td>{i + 1}</td>"
        f'<td><span class="famdot" style="background:'
        f'{FAMILIES[fam_of.get(s, "other")]["color"]}"></span>{_esc(s)}</td>'
        f"<td>{me_idx.loc[s, 'total_concentration']:.3f}</td></tr>"
        for i, s in enumerate(sim_lab))
    S.append(
        f'<div class="figure">{_plot(fig_sim, "figsim")}'
        f'<div class="figcap">איור 3: מטריצת דמיון קוסינוס — {n_sim} '
        f'תחנות מעל סף-האות, ממוספרות ומסודרות באשכולות; פסי-הצבע בשני '
        f'הצירים מסמנים את משפחת-ההסעה. בחירת תחנות בודדות — במקרא למטה; '
        f'סינון לפי משפחה — בסרגל שבראש הפרק.</div>'
        f'<details open style="margin-top:8px"><summary style="cursor:pointer;'
        f'font-size:.85rem;color:#4a4f57">מקרא מספור התחנות ובחירתן</summary>'
        f'<div class="simsel-bar">'
        f'<button type="button" id="simselall" class="simsel-btn">סמן הכל</button>'
        f'<button type="button" id="simselnone" class="simsel-btn">נקה הכל</button>'
        f'{sim_group_btns}'
        f'<span class="simsel-hint">לחיצה על קבוצה מסמנת/מבטלת את כל '
        f'תחנותיה בבת-אחת; כוונון עדין — בתיבות שבטבלה למטה '
        f'(נדרשות לפחות שתיים)</span></div>'
        f'<table style="font-size:.8rem"><tr><th></th><th>#</th><th>תחנה</th>'
        f'<th>Σ (µg/L)</th></tr>{legend_rows}</table></details></div>')
    # cluster interpretation prose — chemistry vs. transport families
    if sim_clusters:
        cl_txt = "; ".join(
            f"אשכול של {len(c)} תחנות ({_list_he([_esc(x) for x in c], 4)})"
            for c in sim_clusters[:3])
        top = sim_pairs[0] if sim_pairs else None
        S.append(_bdi(
            f"<p>מבנה הדמיון (איור 3) מגלה {len(sim_clusters)} אשכולות "
            f"כימיים מובחנים ברמת דמיון של 70% ומעלה: {cl_txt}. "
            + (f"הזוג הדומה ביותר, {_esc(top[1])} ו{_esc(top[2])} "
               f"({top[0]:.0f}%), " if top else "")
            + "השאלה הפורנזית שהמטריצה נועדה לה היא האם האשכולות הכימיים "
            "מתלכדים עם משפחות-ההסעה (פס-הצבע): התלכדות כזו עקבית עם מקור "
            "או נתיב משותף — אך אינה מוכיחה אותו; אי-התלכדות היא רמז "
            "למקור או נתיב שטרם הוסבר.</p>"))
    if fig_att is not None:
        S.append(f'<div class="figure">{_plot(fig_att, "figatt")}'
                 f'<div class="figcap">איור 4: ΣPFAS (ציר שמאלי, לוגריתמי) '
                 f'ונתח קדם-חומרים (ימני) לאורך מסלול הזרימה; באפור — '
                 f'תחנות מוזנות-שאיבה המוחרגות מהרגרסיה.</div></div>')
    S.append(f'<div class="figure">{_plot(fig_fp, "figfp")}'
             f'<div class="figcap">איור 5: הרכב יחסי של {len(fp_names)} '
             f'תחנות המפתח, מקובצות לפי משפחת-הסעה (מהמקור החוצה).</div></div>')
    # family filter script — self-contained, drives map/matrix/fingerprints.
    # Plain-JSON copies of the matrix/fingerprint data are embedded because
    # fig.to_json() binary-encodes arrays (bdata) that page JS cannot slice.
    fp_plain = data["fingerprint"].loc[fp_names]
    fp_plain = fp_plain[[c for c in fp_plain.columns if fp_plain[c].sum() > 0]]
    fam_js_data = {
        "byStation": fam_of,
        "famColors": {k: v["color"] for k, v in FAMILIES.items()},
        "famNames": {k: v["name_he"] for k, v in FAMILIES.items()},
        "famShort": {k: v["short_he"] for k, v in FAMILIES.items()},
        "simLabels": sim_lab,
        "simZ": [[round(float(v), 1) for v in row] for row in sim_df.values],
        "fpStations": fp_names,
        "fpCompounds": list(fp_plain.columns),
        "fpColors": {c: COMPOUND_COLORS.get(c, DEFAULT_COLOR)
                     for c in fp_plain.columns},
        "fpValues": {c: [round(float(v), 2) for v in fp_plain[c]]
                     for c in fp_plain.columns},
    }
    S.append("<script>window.__famData=" +
             json.dumps(fam_js_data, ensure_ascii=False) + ";" + _FAM_JS +
             "</script>")

    # 4 — discussion
    S.append("<h2>4. דיון</h2>")
    for p in _discussion_prose(data, nar):
        S.append(_bdi(f"<p>{p}</p>"))

    # 5 — conclusions
    S.append("<h2>5. מסקנות</h2>")
    S.append("<p>המסקנות מנוסחות להלן בסולם ודאות מוצהר, שבו כל קביעה נושאת "
             "את בסיסה הראייתי. סולם זה נועד לאפשר לקורא לשקול כל מסקנה "
             "לגופה, ולזהות היכן נדרשת עבודה נוספת לפני הסתמכות.</p>")
    n_c = 0
    for c in data["candidates"]:
        n_c += 1
        lvl = "גבוהה" if "ליבה" in c["tier"] else "בינונית"
        transfers = len(c.get("transfer_fed", {}))
        body = (f"<b>{n_c}. דירוג האתר.</b> האתר \"{_esc(c['name_he'])}\" "
                f"מדורג <b>{_esc(c['tier'])}</b> ביחס לזיהום ה-PFAS שבתחום "
                f"התיק. הדירוג נשען על התלכדות עצמאית של ראיות: "
                f"{c['n_downgradient']} תחנות פגועות במורד האתר"
                + (f" ועוד {transfers} המוזנות בנתיבים מוצהרים" if transfers else "")
                + f", התאמה כימית משוקללת של {c['chem_share_weighted']*100:.0f} "
                f"אחוזים בין החתימות שבמורד לפרופיל הצפוי מן האתר, וראיית "
                f"פליטה עצמאית. ")
        if "ליבה" in c["tier"]:
            body += ("יש להדגיש כי אף אחת מן הראיות הנספרות אינה נשענת על "
                     "הנחת כיוון זרימת התהום — כולן נגזרות ממודל הגבהים, "
                     "מנתיבים מוצהרים או ממדידה ישירה באתר — ולפיכך אין "
                     "תחולה לתקרת-ההנחה החלה כאשר הראיות תלויות בהנחה.")
        else:
            body += ("הדירוג נותר מסויג כל עוד משטר הזרימה נלמד מהנחה או "
                     "מקריאת מפה ולא ממדידות מפלס.")
        S.append(f'<div class="concl"><p>{_bdi(body)} '
                 f'{_conf(lvl, "התלכדות צירי הראיה; ראו פרק 4")}</p></div>')

        att = c["attenuation"]
        if att.get("r_precursor") is not None and att["r_precursor"] <= -0.4:
            n_c += 1
            S.append(f'<div class="concl"><p>{_bdi(f"<b>{n_c}. עדות ההזדקנות.</b> החתימה הכימית מזדקנת בעקביות עם ההתרחקות מן האתר: נתח קדם-החומרים הלא-יציבים יורד באופן מונוטוני לאורך המסלול. זוהי עדות תומכת עצמאית, שאינה נשענת על גיאומטריה או על הנחות זרימה אלא על תהליך כימי מוכר, ולפיכך משקלה ניכר.")} '
                     f'{_conf("בינונית", "חתך יחיד, לא בו-זמני")}</p></div>')
        # Cascade pathway is a picture-changing finding — it must surface in
        # the conclusions, not only in the findings chapter (user-caught
        # omission, 2026-08-11: kesariya's conclusions had no trace of the
        # Or-Akiva channel pathway).
        # Junction-load indications are picture-changing: they bound how
        # much of the downstream picture the single candidate explains.
        if c.get("junction_findings"):
            n_c += 1
            segs = "; ".join(
                f'"{_esc(jf["segment"][0])}"←"{_esc(jf["segment"][1])}" '
                f'({jf["km"][0]:.1f}–{jf["km"][1]:.1f} ק"מ)'
                for jf in c["junction_findings"])
            body = (f"<b>{n_c}. אינדיקציות הצטרפות-עומס.</b> מבחן-הצמתים "
                    f"מסמן מקטעים שבהם דפוס הריכוז או ההרכב אינו מוסבר "
                    f"בהסעה מן המוקד בלבד: {segs}. אלו אינדיקציות ולא "
                    f"הוכחות — בחתך לא בו-זמני חלקן עשוי לשקף מועדי-דיגום "
                    f"שונים — אך הן תוחמות את מה שהמועמד היחיד מסביר, "
                    f"וההכרעה בהן היא דיגום-צמתים מזווג: מעל ומתחת לכל "
                    f"ענף מצטרף באותו חלון-זמן.")
            S.append(f'<div class="concl"><p>{_bdi(body)} '
                     f'{_conf("נמוכה", "מבחן-מקטעים על חתך לא בו-זמני")}'
                     f'</p></div>')
        if c.get("cascade_candidates"):
            n_c += 1
            casc_names = _list_he(
                [f'"{x}"' for x in c["cascade_candidates"]], 3)
            body = (f"<b>{n_c}. נתיב-שרשרת מועמד.</b> {casc_names} — "
                    f"קידוחים הצמודים למסלול-הנגר הנגזר מן האתר ושאינם "
                    f"מוסברים בעננת-התהום המשוערת. הצירוף עקבי עם נתיב "
                    f"דו-שלבי נגר←חלחול-ערוץ←תהום רדודה. על-פי הכלל, "
                    f"נתיב-שרשרת אינו נספר כראיה ישירה ואינו ראיית-נגד — "
                    f"אך הוא משנה את תמונת הרצפטורים ואת תוכנית הדיגום: "
                    f"ההכרעה בדיגום מזווג ערוץ–קידוחים באותו חלון-זמן.")
            S.append(f'<div class="concl"><p>{_bdi(body)} '
                     f'{_conf("נמוכה", "השערת-מנגנון — טרם בוצע דיגום מזווג")}'
                     f'</p></div>')
    for q in (region.get("open_questions") or []):
        n_c += 1
        q_title = _esc(q["title_he"])
        q_body = _esc(q.get("stakes_he", q["statement_he"]))
        S.append(f'<div class="concl"><p>'
                 f'{_bdi(f"<b>{n_c}. {q_title}.</b> {q_body}")} '
                 f'{_conf("נמוכה", "שאלה פתוחה")}</p></div>')

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

    # appendix: declared out-of-basin omissions (user feedback 2026-08-12,
    # item 6) — dropped from the report body, never silently
    excluded = data.get("excluded_stations") or []
    if excluded:
        screen = region.get("basin_screen", {})
        S.append("<h2>נספח א' — תחנות שהושמטו מגוף הדוח (מסנן-אגן מוצהר)</h2>")
        S.append(_bdi(
            f"<p>{len(excluded)} תחנות מופיעות בקובץ הנתונים ובתחום מלבן-התיק, "
            f"אך בבירור אינן שייכות לאגן הנחקר: מסלול-הנגר שלהן, כפי שנגזר "
            f"ממודל הגבהים, אינו מתלכד עם גזע-הזרימה של התיק. הן הושמטו מכל "
            f"איור, מנייה וניתוח בגוף הדוח, ומפורטות כאן במלואן. הכלל מוצהר "
            f"וניתן לעקיפה בהצהרת-מומחה (overrides).</p>"))
        note = (screen.get("provenance") or {}).get("note_he", "")
        if note:
            S.append(_bdi(f'<p class="provnote">{_esc(note)}</p>'))
        S.append('<table><tr><th>תחנה</th><th>סוג</th><th>Σ (µg/L)</th>'
                 '<th>סיבת ההשמטה</th></tr>')
        for e in excluded:
            S.append(f"<tr><td>{_esc(e['name'])}</td>"
                     f"<td>{_esc(e['source_type'])}</td>"
                     f"<td>{_sig_he(e['sigma'])}</td>"
                     f"<td>{_esc(e['reason_he'])}</td></tr>")
        S.append("</table>")

    S.append("<h2>נספח ב' — מניפסט מתודולוגי</h2>" if excluded
             else "<h2>נספח — מניפסט מתודולוגי</h2>")
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
                f'<script>{_LEAFLET_JS}</script>'
                f'<style>{_LEAFLET_CSS}</style>'
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
