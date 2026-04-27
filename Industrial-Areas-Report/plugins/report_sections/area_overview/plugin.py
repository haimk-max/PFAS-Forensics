"""Area-overview report section: Leaflet map with boreholes and flow direction."""

from __future__ import annotations

import json
import math
import uuid
from typing import Dict, List

from core.contracts import ReportContext
from core.registry import register_plugin


def _color_for_index(idx: int) -> str:
    if idx <= 2:
        return "#28a745"
    if idx <= 4:
        return "#ffc107"
    if idx <= 6:
        return "#fd7e14"
    return "#dc3545"


def _max_index_per_well(ctx: ReportContext) -> Dict[str, int]:
    """Per borehole, the max ``family_report.max_index`` it appears in."""
    out: Dict[str, int] = {}
    for fr in ctx.family_reports:
        for well in fr.wells_affected:
            prev = out.get(well, -1)
            if fr.max_index > prev:
                out[well] = fr.max_index
    return out


def _dominant_family_per_well(ctx: ReportContext) -> Dict[str, str]:
    out: Dict[str, str] = {}
    best_idx: Dict[str, int] = {}
    for fr in ctx.family_reports:
        for well in fr.wells_affected:
            if fr.max_index > best_idx.get(well, -1):
                best_idx[well] = fr.max_index
                out[well] = fr.family
    return out


@register_plugin("report_section", name="area_overview")
class AreaOverviewSection:
    """Leaflet map: boreholes (colored by index) + flow direction + sources."""

    section_id: str = "area_overview"
    order: int = 1

    def render(self, ctx: ReportContext) -> str:
        map_id = f"map-{uuid.uuid4().hex[:8]}"
        center_lat, center_lon = ctx.map_center
        well_max = _max_index_per_well(ctx)
        well_family = _dominant_family_per_well(ctx)

        markers: List[Dict] = []
        for bh in ctx.boreholes:
            wid = bh.get("id", "")
            idx = well_max.get(wid, 0)
            markers.append({
                "id": wid,
                "name": bh.get("name_hebrew", wid),
                "lat": bh.get("lat"),
                "lon": bh.get("lon"),
                "index": idx,
                "family": well_family.get(wid, "—"),
                "color": _color_for_index(idx),
            })

        # Flow direction: short polyline from center
        flow_lines = []
        if ctx.flow_direction_deg is not None:
            rad = math.radians(ctx.flow_direction_deg)
            # ~300m arrow: 0.003° in lat ≈ 333m; project onto direction
            length = 0.004
            tip_lat = center_lat + length * math.cos(rad)
            tip_lon = center_lon + length * math.sin(rad)
            flow_lines.append({
                "from": [center_lat, center_lon],
                "to": [tip_lat, tip_lon],
                "deg": ctx.flow_direction_deg,
            })

        # Attribution markers (optional, only if facility has lat/lon evidence)
        facility_markers = []
        for attr in ctx.attributions[:8]:
            ev = attr.evidence or {}
            if "lat" in ev and "lon" in ev:
                facility_markers.append({
                    "name": attr.facility_name,
                    "lat": ev["lat"],
                    "lon": ev["lon"],
                    "phrase": attr.cautious_phrase,
                    "tier": attr.tier,
                })

        markers_json = json.dumps(markers, ensure_ascii=False)
        flow_json = json.dumps(flow_lines, ensure_ascii=False)
        facilities_json = json.dumps(facility_markers, ensure_ascii=False)

        n_wells = len(markers)
        max_idx = max(well_max.values()) if well_max else 0

        html = f"""
<section class="card">
  <h2>סקירה אזורית — {ctx.area_hebrew}</h2>
  <p>שנת דיווח: <strong>{ctx.year}</strong> · קידוחי ניטור: <strong>{n_wells}</strong>
     · אינדקס מרבי באזור: <span class="idx-badge idx-{max_idx}">{max_idx}</span>
     · כיוון זרימת מי תהום: <strong>{int(ctx.flow_direction_deg) if ctx.flow_direction_deg is not None else "—"}°</strong></p>

  <div id="{map_id}" class="map-area"></div>
  <p class="note">אינדקס זיהום: 0–2 רקע · 3–4 חריגה · 5–6 חמור · 7–8 קיצוני/קריטי. החץ הכחול מציין את כיוון זרימת מי תהום הכללי.</p>

<script>
(function() {{
  const center = [{center_lat}, {center_lon}];
  const markers = {markers_json};
  const flow = {flow_json};
  const facilities = {facilities_json};
  const map = L.map("{map_id}").setView(center, 15);
  L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
    maxZoom: 19,
    attribution: '© OpenStreetMap'
  }}).addTo(map);

  // Borehole markers
  markers.forEach(m => {{
    if (m.lat == null || m.lon == null) return;
    const circle = L.circleMarker([m.lat, m.lon], {{
      radius: 11,
      fillColor: m.color,
      color: "#222",
      weight: 1.5,
      fillOpacity: 0.85
    }}).addTo(map);
    circle.bindPopup(
      "<strong>" + m.name + "</strong><br>" +
      "אינדקס מרבי: <b>" + m.index + "</b><br>" +
      "קבוצה דומיננטית: " + m.family
    );
  }});

  // Flow direction arrows
  flow.forEach(f => {{
    L.polyline([f.from, f.to], {{
      color: "#1565c0",
      weight: 4,
      opacity: 0.85
    }}).addTo(map);
    // Arrow tip marker
    L.circleMarker(f.to, {{
      radius: 6, fillColor: "#1565c0", color: "#0d47a1",
      weight: 2, fillOpacity: 1
    }}).addTo(map).bindTooltip("כיוון זרימה: " + f.deg + "°", {{permanent: false}});
  }});

  // Facility (attribution) markers
  facilities.forEach(fc => {{
    L.circleMarker([fc.lat, fc.lon], {{
      radius: 8, fillColor: "#7b1fa2", color: "#4a148c",
      weight: 1.5, fillOpacity: 0.8
    }}).addTo(map).bindPopup(
      "<strong>" + fc.name + "</strong><br>" +
      "סיווג: " + fc.phrase + "<br>" +
      "דרג: " + fc.tier
    );
  }});

  // Legend
  const legend = L.control({{position: 'bottomleft'}});
  legend.onAdd = function() {{
    const div = L.DomUtil.create('div', 'map-legend');
    div.innerHTML =
      '<strong>אינדקס זיהום</strong><br>' +
      '<span class="swatch" style="background:#28a745"></span> 0–2 רקע<br>' +
      '<span class="swatch" style="background:#ffc107"></span> 3–4 חריגה<br>' +
      '<span class="swatch" style="background:#fd7e14"></span> 5–6 חמור<br>' +
      '<span class="swatch" style="background:#dc3545"></span> 7–8 קיצוני';
    return div;
  }};
  legend.addTo(map);
}})();
</script>
</section>
"""
        return html
