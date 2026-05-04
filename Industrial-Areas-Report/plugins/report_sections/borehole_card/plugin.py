"""Borehole-card report section: 3 interactive Plotly.js charts.

A — single well, multiple compounds (with drinking-water standard lines)
B — single compound, multiple wells (with standard line)
C — single contaminant family, stacked bar across wells (visual comparison)
"""

from __future__ import annotations

import json
import uuid
from typing import Dict, List

from core.contaminant_grouper import CONTAMINANT_GROUPS, ContaminantGrouper
from core.contracts import ReportContext
from core.registry import register_plugin

try:
    from config import DRINKING_WATER_STANDARDS
except ImportError:  # defensive — plugins should not crash if config moves
    DRINKING_WATER_STANDARDS = {}


def _build_family_membership() -> Dict[str, Dict]:
    """Return {family_name: {hebrew, members[]}} from CONTAMINANT_GROUPS."""
    out: Dict[str, Dict] = {}
    for fam, info in CONTAMINANT_GROUPS.items():
        out[fam] = {
            "hebrew": info.get("hebrew", fam),
            "members": sorted(info.get("members", [])),
        }
    return out


@register_plugin("report_section", name="borehole_card")
class BoreholeCardSection:
    """Three interactive Plotly.js charts driven by raw measurements."""

    section_id: str = "borehole_card"
    order: int = 2

    def render(self, ctx: ReportContext) -> str:
        prev = ctx.previous_context or {}
        raw: List[Dict] = prev.get("raw_data", [])

        # Normalize raw data — only keep what charts need
        clean: List[Dict] = []
        for row in raw:
            try:
                clean.append({
                    "date": str(row["date"]),
                    "borehole_id": str(row["borehole_id"]),
                    "parameter": str(row["parameter"]),
                    "value": float(row["value"]),
                })
            except (KeyError, TypeError, ValueError):
                continue

        # Derived option lists for the dropdowns
        wells = sorted({r["borehole_id"] for r in clean})
        params_present = sorted({r["parameter"] for r in clean})

        grouper = ContaminantGrouper()
        # Build {family: [param,...]} restricted to params actually present
        families_present: Dict[str, List[str]] = {}
        family_hebrew: Dict[str, str] = {}
        for p in params_present:
            fam = grouper.classify(p) or "unclassified"
            families_present.setdefault(fam, []).append(p)
        for fam in families_present:
            heb = CONTAMINANT_GROUPS.get(fam, {}).get("hebrew", fam)
            family_hebrew[fam] = heb

        well_borehole_hebrew: Dict[str, str] = {}
        for bh in ctx.boreholes:
            well_borehole_hebrew[bh.get("id", "")] = bh.get(
                "name_hebrew", bh.get("id", "")
            )

        # Standards filtered to compounds we have
        standards = {
            p: float(DRINKING_WATER_STANDARDS[p])
            for p in params_present
            if p in DRINKING_WATER_STANDARDS
        }

        # Build dropdown <option> lists
        well_options = "".join(
            f'<option value="{w}">{well_borehole_hebrew.get(w, w)}</option>'
            for w in wells
        )

        compound_optgroups_parts: List[str] = []
        for fam in sorted(families_present.keys()):
            heb = family_hebrew[fam]
            opts = "".join(
                f'<option value="{p}">{p}</option>'
                for p in sorted(families_present[fam])
            )
            compound_optgroups_parts.append(
                f'<optgroup label="{heb}">{opts}</optgroup>'
            )
        compound_options = "".join(compound_optgroups_parts)

        group_options = "".join(
            f'<option value="{fam}">{family_hebrew[fam]}</option>'
            for fam in sorted(families_present.keys())
            if fam != "unclassified"
        )

        # JSON payloads for client-side
        data_json = json.dumps(clean, ensure_ascii=False)
        standards_json = json.dumps(standards, ensure_ascii=False)
        families_json = json.dumps(families_present, ensure_ascii=False)
        family_hebrew_json = json.dumps(family_hebrew, ensure_ascii=False)
        well_hebrew_json = json.dumps(well_borehole_hebrew, ensure_ascii=False)

        suffix = uuid.uuid4().hex[:6]
        chart_a = f"chartA_{suffix}"
        chart_b = f"chartB_{suffix}"
        chart_c = f"chartC_{suffix}"
        sel_a = f"wellSelA_{suffix}"
        sel_b = f"compSelB_{suffix}"
        sel_c = f"groupSelC_{suffix}"

        html = f"""
<section class="card">
  <h2>גרפים אינטראקטיביים — שינוי ריכוזים בזמן והשוואת קידוחים</h2>

  <h3>א. ריכוזים בזמן — קידוח בודד, כל המזהמים</h3>
  <div class="chart-controls">
    <label for="{sel_a}">בחר קידוח:</label>
    <select id="{sel_a}">{well_options}</select>
  </div>
  <div id="{chart_a}" class="plot-area"></div>
  <p class="note">קווים מקווקווים מציינים את תקן מי השתייה לכל מזהם.</p>

  <h3>ב. ריכוזים בזמן — מזהם בודד, השוואה בין קידוחים</h3>
  <div class="chart-controls">
    <label for="{sel_b}">בחר מזהם (מקובץ לפי קבוצה):</label>
    <select id="{sel_b}">{compound_options}</select>
  </div>
  <div id="{chart_b}" class="plot-area"></div>

  <h3>ג. גרף עמודות מוערם — התפלגות מזהמי הקבוצה בקידוחים השונים</h3>
  <div class="chart-controls">
    <label for="{sel_c}">בחר קבוצת מזהמים:</label>
    <select id="{sel_c}">{group_options}</select>
  </div>
  <div id="{chart_c}" class="plot-area"></div>
  <p class="note">כל עמודה מציגה את הריכוז המרבי שנמדד עבור כל מזהם בכל קידוח. הצורה דומה בין קידוחים = רמז להרכב מזהמים דומה.</p>

<script>
(function() {{
  const RAW = {data_json};
  const STANDARDS = {standards_json};
  const FAMILIES = {families_json};
  const FAMILY_HEBREW = {family_hebrew_json};
  const WELL_HEBREW = {well_hebrew_json};

  const sortByDate = (a,b) => a.date < b.date ? -1 : (a.date > b.date ? 1 : 0);
  const RTL_LAYOUT = {{
    margin: {{t: 30, r: 30, b: 60, l: 60}},
    legend: {{orientation: 'h', y: -0.2}},
    xaxis: {{title: 'תאריך', type: 'date'}},
    yaxis: {{title: 'ריכוז'}},
    font: {{family: 'Segoe UI, Heebo, Arial', size: 13}}
  }};
  const CONFIG = {{responsive: true, displaylogo: false, locale: 'he'}};

  // ----- Chart A: single well, all compounds ------------------------
  function plotA(well) {{
    const subset = RAW.filter(r => r.borehole_id === well).sort(sortByDate);
    const byParam = {{}};
    subset.forEach(r => {{
      (byParam[r.parameter] = byParam[r.parameter] || []).push(r);
    }});
    const traces = Object.keys(byParam).sort().map(p => ({{
      x: byParam[p].map(r => r.date),
      y: byParam[p].map(r => r.value),
      mode: 'lines+markers',
      name: p,
      type: 'scatter'
    }}));
    // Standard reference lines as horizontal shapes per visible compound
    const shapes = [];
    Object.keys(byParam).forEach(p => {{
      if (STANDARDS[p] != null) {{
        shapes.push({{
          type: 'line', xref: 'paper', x0: 0, x1: 1,
          y0: STANDARDS[p], y1: STANDARDS[p],
          line: {{dash: 'dash', color: '#dc3545', width: 1}}
        }});
      }}
    }});
    const layout = Object.assign({{}}, RTL_LAYOUT, {{
      title: 'קידוח: ' + (WELL_HEBREW[well] || well),
      shapes: shapes
    }});
    Plotly.react('{chart_a}', traces, layout, CONFIG);
  }}

  // ----- Chart B: single compound, all wells ------------------------
  function plotB(compound) {{
    const subset = RAW.filter(r => r.parameter === compound).sort(sortByDate);
    const byWell = {{}};
    subset.forEach(r => {{
      (byWell[r.borehole_id] = byWell[r.borehole_id] || []).push(r);
    }});
    const traces = Object.keys(byWell).sort().map(w => ({{
      x: byWell[w].map(r => r.date),
      y: byWell[w].map(r => r.value),
      mode: 'lines+markers',
      name: WELL_HEBREW[w] || w,
      type: 'scatter'
    }}));
    const shapes = [];
    if (STANDARDS[compound] != null) {{
      shapes.push({{
        type: 'line', xref: 'paper', x0: 0, x1: 1,
        y0: STANDARDS[compound], y1: STANDARDS[compound],
        line: {{dash: 'dash', color: '#dc3545', width: 2}}
      }});
    }}
    const layout = Object.assign({{}}, RTL_LAYOUT, {{
      title: 'מזהם: ' + compound + (STANDARDS[compound] != null ? ' (תקן: ' + STANDARDS[compound] + ')' : ''),
      shapes: shapes
    }});
    Plotly.react('{chart_b}', traces, layout, CONFIG);
  }}

  // ----- Chart C: stacked bar of group across wells -----------------
  function plotC(family) {{
    const members = (FAMILIES[family] || []).slice().sort();
    const wells = Array.from(new Set(RAW.map(r => r.borehole_id))).sort();
    // For each member compound, max value per well
    const traces = members.map(comp => {{
      const ys = wells.map(w => {{
        const vals = RAW.filter(r => r.borehole_id === w && r.parameter === comp)
                        .map(r => r.value);
        return vals.length ? Math.max.apply(null, vals) : 0;
      }});
      return {{
        x: wells.map(w => WELL_HEBREW[w] || w),
        y: ys,
        name: comp,
        type: 'bar'
      }};
    }});
    const layout = Object.assign({{}}, RTL_LAYOUT, {{
      title: 'התפלגות ' + (FAMILY_HEBREW[family] || family) + ' בקידוחים',
      barmode: 'stack',
      xaxis: {{title: 'קידוח'}},
      yaxis: {{title: 'ריכוז מרבי'}}
    }});
    Plotly.react('{chart_c}', traces, layout, CONFIG);
  }}

  // Wire up dropdowns
  const selA = document.getElementById('{sel_a}');
  const selB = document.getElementById('{sel_b}');
  const selC = document.getElementById('{sel_c}');
  if (selA) {{ selA.addEventListener('change', e => plotA(e.target.value)); }}
  if (selB) {{ selB.addEventListener('change', e => plotB(e.target.value)); }}
  if (selC) {{ selC.addEventListener('change', e => plotC(e.target.value)); }}

  // Initial draw
  if (selA && selA.value) plotA(selA.value);
  if (selB && selB.value) plotB(selB.value);
  if (selC && selC.value) plotC(selC.value);
}})();
</script>
</section>
"""
        return html
