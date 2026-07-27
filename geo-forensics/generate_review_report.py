"""generate_review_report.py — Self-contained HTML expert-review report.

Assembles the regional attribution into one shareable HTML page: an
interactive map (stations by concentration & profile match, DEM channels,
the candidate's runoff path, declared/hypothesized transfers, claim pins),
attenuation charts, per-candidate evidence, the numbered claims board, and a
copy-ready answer sheet. Static HTML cannot capture answers — the expert
decides via the claims IDs in chat (see the answer sheet at the end).

Reuses the existing analysis modules (no duplicated logic) and the region's
derived DEM layers. Run offline; commit the output under the region.

Usage (from geo-forensics/):
    python generate_review_report.py hagit -o regions/hagit/review_hagit.html
"""

import argparse
import html
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np

from config import MIN_SIGNAL_UG_L
from src.attribution import evaluate_candidates, load_region
from src.data_model import (
    build_fingerprint_matrix,
    calc_total_concentration,
    process_file,
)
from src.source_profiles import PROFILES, match_profiles

_PROFILE_HE = {p.key: p.name_he for p in PROFILES}


def _esc(s):
    return html.escape(str(s))


def _prepare(region_name):
    region = load_region(region_name)
    mf = os.path.join(os.path.dirname(__file__), region["measurement_file"])
    df, group = process_file(mf, group_name="PFAS")
    fp = build_fingerprint_matrix(df, group)
    tot = calc_total_concentration(df, group)
    me = tot.loc[tot.groupby("station_name")["total_concentration"].idxmax()]
    matches = match_profiles(fp, top_n=1).set_index("station")
    candidates = evaluate_candidates(df, fp, me, region)

    stations = []
    for _, r in me.iterrows():
        if np.isnan(r.get("lat", np.nan)) or np.isnan(r.get("lon", np.nan)):
            continue
        name = r["station_name"]
        top = matches.loc[name] if name in matches.index else None
        stations.append({
            "name": name, "lat": float(r["lat"]), "lon": float(r["lon"]),
            "sigma": float(r["total_concentration"]),
            "source_type": str(r.get("source_type", "")),
            "profile": (top["profile_he"] if top is not None else "—"),
            "score": (float(top["score"]) if top is not None else 0.0),
            "below_thr": float(r["total_concentration"]) < MIN_SIGNAL_UG_L,
        })

    # derived DEM layers (optional)
    base = region["_base"]
    channels = _load_json(os.path.join(base, "derived", "channels.geojson"))
    flow = _load_json(os.path.join(base, "derived", "flow_paths.json"))
    claims = _load_json(os.path.join(base, "claims.json"))
    sources = _load_json(os.path.join(base, "sources.geojson"))

    # attenuation series per candidate (path distance vs Σ, precursor share)
    for c in candidates:
        c["atten_series"] = _atten_series(c, flow, me, fp)
    return {
        "region": region, "stations": stations, "candidates": candidates,
        "channels": channels, "flow": flow, "claims": claims, "sources": sources,
        "n_stations": int(me["station_name"].nunique()),
        "n_signal": int((me["total_concentration"] >= MIN_SIGNAL_UG_L).sum()),
        "date_span": region.get("dataset_semantics", {}).get("date_span", ""),
    }


def _load_json(path):
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _atten_series(candidate, flow, me, fp):
    """Path-distance vs Σ (and precursor share) for the candidate's on-path
    surface stations — the visual behind the attenuation r."""
    if not flow:
        return []
    src_id = candidate["id"]
    rels = {r["to"]: r["path_distance_m"] for r in flow.get("relations", [])
            if r["from"] == src_id}
    me_idx = me.set_index("station_name")
    from src.source_profiles import PRECURSORS
    prec = [c for c in fp.columns if c.upper() in {p.upper() for p in PRECURSORS}]
    out = []
    for stn, dist in rels.items():
        if stn in me_idx.index and stn in fp.index:
            sig = float(me_idx.loc[stn, "total_concentration"])
            if sig <= 0:
                continue
            out.append({"station": stn, "km": round(dist / 1000, 2),
                        "sigma": sig,
                        "precursor": round(float(fp.loc[stn, prec].sum()), 1)})
    return sorted(out, key=lambda d: d["km"])


# ---------------------------------------------------------------------------

_TEMPLATE = r"""<!doctype html>
<html lang="he" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>דוח ביקורת — __TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
:root{--bg:#f5f3ee;--surface:#fff;--ink:#1c1f24;--ink2:#4a4f57;--ink3:#7d8189;
--line:#e2ddd2;--accent:#2a9d8f;--warn:#d97a2c;--ok:#2d8b5e;--high:#7a3d9e;--bad:#c64a3b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);direction:rtl;
font-family:Assistant,"Segoe UI",system-ui,sans-serif;line-height:1.6}
.wrap{max-width:1100px;margin:0 auto;padding:24px}
h1{font-size:1.7rem;margin:.2em 0}h2{font-size:1.25rem;border-bottom:2px solid var(--accent);
padding-bottom:6px;margin-top:1.6em}h3{font-size:1.05rem;margin:.8em 0 .3em}
.sub{color:var(--ink3);font-size:.92rem}
.card{background:var(--surface);border:1px solid var(--line);border-radius:8px;
padding:16px 20px;margin:14px 0;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.banner{background:#fdf6ec;border:1px solid #e8d9bf;border-radius:6px;padding:10px 14px;
font-size:.9rem;color:#6d5f3a;margin:10px 0}
.banner.warn{background:#fbeee6;border-color:#e6c3a8}
#map{height:480px;border-radius:8px;border:1px solid var(--line)}
.legend{font-size:.82rem;background:#fff;padding:8px 10px;border-radius:6px;line-height:1.8}
.legend i{display:inline-block;width:12px;height:12px;border-radius:50%;margin-left:6px;vertical-align:middle}
table{width:100%;border-collapse:collapse;font-size:.88rem}
th,td{text-align:right;padding:7px 9px;border-bottom:1px solid var(--line)}
th{color:var(--ink2);font-weight:600}
.tier{display:inline-block;background:#f0eaf6;color:var(--high);border-radius:100px;
padding:2px 12px;font-weight:600;font-size:.9rem}
.ev{list-style:none;padding:0;margin:6px 0}.ev li{padding:5px 0;border-bottom:1px dashed var(--line)}
.for::before{content:"➕ ";color:var(--ok)}.against::before{content:"➖ ";color:var(--warn)}
.ref::before{content:"❓ ";color:var(--ink3)}
.claim{border-right:4px solid var(--ink3);padding:8px 14px;margin:8px 0;background:#faf8f4;border-radius:4px}
.claim.under_investigation,.claim.open{border-right-color:var(--warn)}
.claim.pending,.claim.pending_verification{border-right-color:var(--high)}
.claim.standing,.claim.partially_resolved{border-right-color:var(--ok)}
.cid{font-family:ui-monospace,monospace;font-weight:700;background:var(--ink);color:#fff;
border-radius:4px;padding:1px 7px;margin-left:6px;font-size:.85rem}
.chip{font-size:.75rem;color:var(--ink3);border:1px solid var(--line);border-radius:100px;padding:1px 8px}
.answer{background:#1c1f24;color:#e8e8e8;border-radius:8px;padding:16px 20px;font-family:ui-monospace,monospace;
font-size:.85rem;white-space:pre-wrap;line-height:1.9}
.chart{height:320px}
.foot{color:var(--ink3);font-size:.8rem;margin-top:24px;text-align:center}
</style></head><body><div class="wrap">

<h1>🔬 דוח ביקורת מומחה — __REGION_HE__</h1>
<div class="sub">ניתוח גיאו-פורנזי PFAS · __N_STATIONS__ תחנות (__N_SIGNAL__ מעל סף-אות) · טווח __DATE_SPAN__</div>
<div class="banner warn">⚠ <b>מעמד המסמך:</b> כלי סינון לתעדוף חקירה — <b>לא</b> קביעת מקור. כל התאמה היא "עקבי עם".
שפת דירוג: מועמד ליבה / משני / רקע מקומי — לעולם לא "המקור". הכרעות המומחה נמסרות דרך מזהי-הטענות (ראו גיליון בסוף).</div>
__SEMANTICS__

<h2>1 · מפת הממצאים</h2>
<div class="card"><div id="map"></div>
<div class="sub" style="margin-top:8px">גודל הסמן ∝ log(Σ) · צבע = התאמת-פרופיל מובילה · קו כחול = ערוצי DEM · קו כתום מקווקו = מסלול הנגר של המועמד · 📍 = טענה לביקורת</div></div>

<h2>2 · המועמדים</h2>
__CANDIDATES__

<h2>3 · דעיכה לאורך מסלול הזרימה</h2>
<div class="card"><div id="attenChart" class="chart"></div>
<div class="sub">Σ (סקאלה לוגריתמית) ונתח קדם-חומרים מול מרחק-מסלול מהמקור. דעיכה + ירידת קדם-חומרים = עקבי עם מקור באתר.</div></div>

<h2>4 · לוח הטענות לביקורת</h2>
<div class="sub">רק פריטים שהכרעתם משנה מסקנה. לכל טענה: הסטטוס הנוכחי ומה משתנה אם תידחה/תתוקן.</div>
__CLAIMS__

<h2>5 · גיליון תשובות (העתק לצ'אט)</h2>
<div class="sub">ערוך את השורות והדבק חזרה. פורמט: <code>מזהה ✓/✗/תיקון: הערה</code></div>
<div class="answer">__ANSWER_SHEET__</div>

<div class="foot">נוצר מ-generate_review_report.py · נתונים: __MEASUREMENT_FILE__ · DEM: Copernicus GLO-30</div>
</div>
<script>
var DATA = __DATA_JSON__;
(function(){
 var map=L.map('map',{scrollWheelZoom:false});
 L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
   {attribution:'© OpenStreetMap',maxZoom:17}).addTo(map);
 var pts=[];
 function col(s,below){if(below)return'#c8c4bc';if(s.indexOf('AFFF')>=0)return'#c64a3b';
   if(s.indexOf('מט')>=0)return'#2a9d8f';if(s.indexOf('מטמנה')>=0)return'#d97a2c';
   if(s.indexOf('תעשיית')>=0)return'#7a3d9e';return'#4a90a4';}
 // DEM channels
 if(DATA.channels){DATA.channels.features.forEach(function(f){
   var ll=f.geometry.coordinates.map(function(c){return[c[1],c[0]];});
   L.polyline(ll,{color:'#2a6f97',weight:2,opacity:.5}).addTo(map);});}
 // candidate runoff path
 (DATA.candidates||[]).forEach(function(c){
   if(c.path_wgs){L.polyline(c.path_wgs.map(function(p){return[p[1],p[0]];}),
     {color:'#d97a2c',weight:3,dashArray:'8 6',opacity:.8}).addTo(map);}});
 // stations
 DATA.stations.forEach(function(s){
   var r=s.below_thr?4:Math.max(5,Math.min(20,6+3*Math.log10(s.sigma/0.001+1)));
   var m=L.circleMarker([s.lat,s.lon],{radius:r,color:col(s.profile,s.below_thr),
     fillColor:col(s.profile,s.below_thr),fillOpacity:s.below_thr?.3:.8,weight:1});
   m.bindPopup('<div dir=rtl style="min-width:190px"><b>'+s.name+'</b><br>Σ='+
     s.sigma.toFixed(3)+' µg/L'+(s.below_thr?' (מתחת לסף)':'')+'<br>'+s.source_type+
     '<br>התאמה: '+s.profile+' ('+s.score.toFixed(0)+'%)</div>');
   m.addTo(map);pts.push([s.lat,s.lon]);});
 // claim pins
 (DATA.claims&&DATA.claims.claims||[]).forEach(function(c){
   if(!c.location_wgs)return;
   var icon=L.divIcon({className:'',html:'<div style="background:#1c1f24;color:#fff;border-radius:50%;'+
     'width:26px;height:26px;display:flex;align-items:center;justify-content:center;'+
     'font-weight:700;font-size:11px;border:2px solid #fff">'+c.id+'</div>',iconSize:[26,26]});
   L.marker([c.location_wgs[1],c.location_wgs[0]],{icon:icon}).addTo(map)
     .bindPopup('<div dir=rtl style="min-width:220px"><b>'+c.id+' · '+c.title_he+'</b><br>'+
     c.statement_he+'<br><i>'+c.status_he+'</i></div>');});
 if(pts.length)map.fitBounds(pts,{padding:[30,30]});
 // attenuation chart
 var c0=(DATA.candidates||[])[0];
 if(c0&&c0.atten_series&&c0.atten_series.length){
   var xs=c0.atten_series.map(function(d){return d.km;});
   Plotly.newPlot('attenChart',[
     {x:xs,y:c0.atten_series.map(function(d){return d.sigma;}),name:'Σ µg/L',
      mode:'lines+markers',line:{color:'#c64a3b'},yaxis:'y'},
     {x:xs,y:c0.atten_series.map(function(d){return d.precursor;}),name:'% קדם-חומרים',
      mode:'lines+markers',line:{color:'#2a9d8f'},yaxis:'y2'}],
     {margin:{t:20,r:50,l:50,b:40},font:{family:'Assistant'},
      xaxis:{title:'מרחק-מסלול (ק"מ)'},yaxis:{title:'Σ',type:'log'},
      yaxis2:{title:'% קדם-חומרים',overlaying:'y',side:'right'},
      legend:{orientation:'h'}},{responsive:true,displayModeBar:false});
 } else {document.getElementById('attenChart').innerHTML=
   '<div class=sub style="padding:30px;text-align:center">אין מספיק תחנות על-מסלול לגרף דעיכה.</div>';}
})();
</script></body></html>"""


def _wgs(itm):
    from src.geo_utils import itm_to_wgs84
    lat, lon = itm_to_wgs84(itm[0], itm[1])
    return [lon, lat]


def _render(data):
    region = data["region"]
    # candidate cards + attach WGS path/coords for the map
    cand_html, answer_lines = [], []
    for c in data["candidates"]:
        c["path_wgs"] = None
        pt = data["flow"]["points"].get(c["id"]) if data["flow"] else None
        if pt and pt.get("path_itm"):
            c["path_wgs"] = [_wgs(p) for p in pt["path_itm"][::3]]
        rows = "".join(f'<li class="for">{_esc(e)}</li>' for e in c["evidence_for"])
        rows += "".join(f'<li class="against">{_esc(e)}</li>' for e in c["evidence_against"])
        rows += "".join(f'<li class="ref">{_esc(e)}</li>' for e in c["would_refute"])
        cand_html.append(f"""<div class="card">
<h3>{_esc(c['name_he'])} <span class="tier">{_esc(c['tier'])}</span></h3>
<div class="sub">{_esc(c['flow_caveat'])}</div>
<p>תחנות במורד: <b>{c['n_downgradient']}</b> (עילי-DEM {c['n_surface_down']} · תהום-הנחה {c['n_gw_down']})
· התאמה כימית משוקללת: <b>{c['chem_share_weighted']*100:.0f}%</b>
· דעיכה r={c['attenuation']['r_conc']} ({_esc(c['attenuation']['note_he'])})</div>
<ul class="ev">{rows}</ul></div>""")

    # claims + WGS pin coords + answer sheet
    claim_html = []
    for cl in (data["claims"]["claims"] if data["claims"] else []):
        cl["location_wgs"] = _wgs(cl["location_itm"]) if cl.get("location_itm") else None
        claim_html.append(f"""<div class="claim {cl['status']}">
<span class="cid">{cl['id']}</span> <b>{_esc(cl['title_he'])}</b>
<span class="chip">{_esc(cl['status_he'])}</span>
<div style="margin-top:4px">{_esc(cl['statement_he'])}</div>
<div class="sub" style="margin-top:4px"><b>אם יידחה/יתוקן:</b> {_esc(cl['impact_he'])}</div></div>""")
        answer_lines.append(f"{cl['id']}  ( ✓ / ✗ / תיקון ) : ")

    sem = region.get("dataset_semantics")
    sem_html = (f'<div class="banner">📋 <b>סמנטיקת החתך:</b> {_esc(sem["snapshot_rule"])} · '
                f'לא בו-זמני · הנחת steady-state.</div>') if sem else ""

    payload = {"stations": data["stations"], "channels": data["channels"],
               "flow": {"points": {k: {"path_itm": v.get("path_itm", [])}
                                   for k, v in (data["flow"]["points"].items() if data["flow"] else [])}},
               "candidates": [{"id": c["id"], "path_wgs": c["path_wgs"],
                               "atten_series": c["atten_series"]} for c in data["candidates"]],
               "claims": data["claims"]}

    return (_TEMPLATE
            .replace("__TITLE__", _esc(region.get("name_he", region["name"])))
            .replace("__REGION_HE__", _esc(region.get("name_he", region["name"])))
            .replace("__N_STATIONS__", str(data["n_stations"]))
            .replace("__N_SIGNAL__", str(data["n_signal"]))
            .replace("__DATE_SPAN__", _esc(data["date_span"]))
            .replace("__SEMANTICS__", sem_html)
            .replace("__CANDIDATES__", "\n".join(cand_html))
            .replace("__CLAIMS__", "\n".join(claim_html))
            .replace("__ANSWER_SHEET__", _esc("\n".join(answer_lines)))
            .replace("__MEASUREMENT_FILE__", _esc(os.path.basename(region["measurement_file"])))
            .replace("__DATA_JSON__", json.dumps(payload, ensure_ascii=False)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("region")
    ap.add_argument("-o", "--output", default=None)
    args = ap.parse_args()
    data = _prepare(args.region)
    html_out = _render(data)
    out = args.output or f"regions/{args.region}/review_{args.region}.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"wrote {out} ({len(html_out)//1024} KB)")
    print(f"  stations={data['n_stations']} signal={data['n_signal']} "
          f"candidates={len(data['candidates'])} "
          f"claims={len(data['claims']['claims']) if data['claims'] else 0}")


if __name__ == "__main__":
    main()
