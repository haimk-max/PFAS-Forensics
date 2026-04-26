# Industrial Areas Groundwater Monitoring — Report Generator

Automated system for generating periodic regulatory reports on groundwater contamination
in Israeli industrial areas above the Coastal Aquifer (אקויפר החוף).

---

## What It Does

1. **Ingests** groundwater quality measurements from multiple sources (Water Authority,
   PRTR registry, local water corporations, Excel consolidation files).
2. **Analyzes** contamination by family, fingerprint, and trend — using a logarithmic
   Pollution Index (0–8) aligned with Water Authority regulatory language.
3. **Identifies** probable pollution sources with cautious, legally-safe attribution phrasing.
4. **Generates** 3-layer HTML/PDF reports: area overview → per-well cards → analytical appendix.
5. **Accumulates** approved reports as context layers that inform subsequent years.

---

## Architecture — Plugin-Based

All analytical capabilities are **plugins** that implement stable interfaces defined in `core/`.
Adding a new capability (e.g., PFAS forensics, LSTM trend detector) requires only
creating a new folder under `plugins/` — zero changes to core orchestration code.

```
core/
├── interfaces.py       ← 6 Protocols: DataSource, ForensicsModule, TrendDetector...
├── contracts.py        ← Typed dataclasses: FingerprintResult, TrendResult, Attribution...
├── registry.py         ← @register_plugin + auto-discovery
└── pipeline.py         ← Orchestrator — chains registered plugins in order

plugins/
├── data_sources/       water_authority / prtr / mei_raanana / excel
├── forensics/          chlorinated / fuels / metals / pfas (stub, future)
├── trend_detection/    mann_kendall / changepoint / linear
├── source_attribution/ tier_based
└── report_sections/    area_overview / borehole_card / appendix / checklist

knowledge/              Cumulative context store (approved reports)
areas/                  GeoJSON polygons per industrial area
config.py               Per-area pipeline activation (data, not code)
```

### Adding a New Plugin

```
plugins/forensics/pfas/
├── __init__.py
├── plugin.py          ← implements ForensicsModule + @register_plugin("forensics", name="pfas")
├── contaminants.yaml  ← PFAS compounds handled
├── tests/
└── README.md          ← contract: input/output/dependencies
```

Activate per area in `config.py → PIPELINE_CONFIG`.

---

## Key Domain Concepts

| Concept | Description |
|---|---|
| **Pollution Index 0–8** | Logarithmic scale: ratio of measured concentration to drinking water standard |
| **7 Contaminant Families** | Chlorinated solvents, fuels, metals, inorganic/salinity, PFAS, emerging, sewage markers |
| **7 Trend Types** | Rising, falling, stable, volatile, pulse, re-escalation, new appearance |
| **Chemical Fingerprint** | Leading contaminant + secondaries + degradation chain + intra-group ratios per well |
| **Dual-Path Well Selection** | Historical report wells ∪ polygon-based wells (Shapely point-in-polygon) |
| **Cautious Attribution** | "מועמד ליבה" / "מועמד משני" — legally critical, never "the source" |
| **Cumulative Knowledge** | Each approved report → context layer for next year |
| **Flow Direction Caution** | Flow alone does not identify a source; requires chemical + spatial + emission evidence |

---

## Quick Start

```bash
pip install -r requirements.txt
python demo/raanana_demo.py
```

Outputs in `reports/raanana/{year}/`:
- `report_raanana_{year}.html` — interactive RTL report with Leaflet map
- `report_raanana_{year}.pdf`  — official signed version
- `report_raanana_{year}.json` — machine-readable
- `map_raanana_{year}.html`    — standalone Leaflet map
- `context_raanana_{year}.json`— cumulative context for next year

---

## Data Sources

| Source | Data | Status |
|---|---|---|
| Israel Water Authority (data.gov.il) | Borehole quality history | Live API connector |
| PRTR / מפל"ס | Industrial emissions registry | Placeholder — scraper needed |
| Mei Raanana | Industrial wastewater monitoring | Placeholder — scraper needed |
| Excel consolidation | Historical measurements | Working importer |

---

## Pilot: Raanana Industrial Zone

Three independent contamination foci identified:
- **West/Center focus** — TCE/Boron (Index 6–8, chlorinated solvents pathway)
- **East focus** — PFAS at gas turbine station (Index 5, separate system)
- **Background risk** — oil/metals from auto-service shops (future infiltration risk)

See `demo/raanana_demo.py` for full pipeline demonstration.

---

## Tests

```bash
pytest tests/ -v
pytest tests/test_plugin_isolation.py -v   # plugin contract tests
```

---

## Extending to New Areas

1. Add polygon to `areas/{area_name}.geojson`
2. Add area entry to `config.py → INDUSTRIAL_AREAS`
3. Set plugin selection in `config.py → PIPELINE_CONFIG["{area_name}"]`
4. Add historical report data to `knowledge/baselines/{area_name}/`
