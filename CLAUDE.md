# CLAUDE.md — Industrial Areas Groundwater Monitoring System

## Project Purpose

Automated platform for analyzing groundwater contamination in Israeli industrial areas
and generating periodic regulatory reports for the Water Authority and Ministry of
Environmental Protection. Raanana industrial zone is the pilot case study.

---
1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them - don't pick silently.
If a simpler approach exists, say so. Push back when warranted.
If something is unclear, stop. Name what's confusing. Ask.
2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

No features beyond what was asked.
No abstractions for single-use code.
No "flexibility" or "configurability" that wasn't requested.
No error handling for impossible scenarios.
If you write 200 lines and it could be 50, rewrite it.
Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

3. Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:

Don't "improve" adjacent code, comments, or formatting.
Don't refactor things that aren't broken.
Match existing style, even if you'd do it differently.
If you notice unrelated dead code, mention it - don't delete it.
When your changes create orphans:

Remove imports/variables/functions that YOUR changes made unused.
Don't remove pre-existing dead code unless asked.
The test: Every changed line should trace directly to the user's request.

4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

"Add validation" → "Write tests for invalid inputs, then make them pass"
"Fix the bug" → "Write a test that reproduces it, then make it pass"
"Refactor X" → "Ensure tests pass before and after"
For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

## Architecture Principles

### Plugin-First Design

The system is built on an **Open-Closed** principle: the core orchestration layer is
closed to modification, while every analysis capability is a plugin that can be added,
replaced, or disabled without touching core code.

```
core/            ← stable contracts + orchestration (rarely changes)
plugins/         ← all capabilities as drop-in packages (grows freely)
knowledge/       ← cumulative context store (approved reports feed next year)
areas/           ← GeoJSON polygons per industrial area
config.py        ← pipeline activation per area (data, not code)
```

**Rule:** adding a new analysis module (e.g., PFAS forensics, LSTM trend detector)
= create a new folder under `plugins/`, implement the relevant Protocol from
`core/interfaces.py`, decorate with `@register_plugin`. Zero changes to core.

### Six Extension Points (core/interfaces.py)

| Protocol | Where | Purpose |
|---|---|---|
| `DataSource` | `plugins/data_sources/` | Fetch raw measurements |
| `ContaminantFamilyAnalyzer` | `plugins/forensics/` | Per-family group analysis |
| `ForensicsModule` | `plugins/forensics/` | Chemical fingerprinting per well |
| `TrendDetector` | `plugins/trend_detection/` | Detect trend types in time series |
| `SourceAttributor` | `plugins/source_attribution/` | Rank pollution candidates |
| `ReportSection` | `plugins/report_sections/` | Render one HTML section |

### Typed Data Contracts (core/contracts.py)

All inter-module data flows through typed dataclasses — never raw `dict`.
Key types: `BoreholeReading`, `FamilyReport`, `FingerprintResult`,
`TrendResult`, `Attribution`, `ReportContext`.

---

## Key Domain Concepts

- **Pollution Index 0-8**: logarithmic scale (ratio to drinking water standard).
  Index = `f(concentration / standard)`. Group index = `max(member indices)`.
- **7 Contaminant Families**: chlorinated solvents, fuels, metals, inorganic/salinity,
  PFAS, emerging, sewage markers.
- **7 Trend Types**: rising, falling, stable, volatile, pulse/event,
  re-escalation (changepoint after decline), new appearance.
- **Chemical Fingerprint**: leading contaminant + secondaries + degradation products
  + intra-group ratios. Used to distinguish separate plumes and link wells.
- **Dual-path Borehole Selection**: union of (historical report wells) ∪
  (polygon-based wells via Shapely point-in-polygon).
- **Cautious Attribution Phrasing**: legally critical in Israel. Vocabulary:
  "מועמד ליבה" / "מועמד משני" / "רקע מקומי" — never "the source".
- **Cumulative Knowledge**: each approved annual report becomes a formal context
  layer for the next year (stored under `knowledge/contexts/{area}/{year}.json`).
- **Flow Direction Caution**: flow direction alone never identifies a source —
  must combine with chemical fingerprint + spatial position + emission evidence.

---

## Adding a New Plugin (Quick Guide)

```
plugins/forensics/pfas/
├── __init__.py          # exposes PFASForensics class
├── plugin.py            # implements ForensicsModule Protocol, @register_plugin
├── contaminants.yaml    # PFAS compounds handled (PFOA, PFOS, GenX…)
├── tests/
│   └── test_plugin.py   # isolated unit tests
└── README.md            # contract: input schema, output schema, dependencies
```

```python
# plugin.py skeleton
from core.interfaces import ForensicsModule
from core.registry import register_plugin
from core.contracts import FingerprintResult

@register_plugin("forensics", name="pfas")
class PFASForensics:
    family = "pfas"
    version = "1.0"

    def fingerprint(self, well_data) -> FingerprintResult:
        ...
```

Activate for a specific area in `config.py`:
```python
PIPELINE_CONFIG["emek_hefer"]["forensics"].append("pfas")
```

---

## Running the System

```bash
cd Industrial-Areas-Report
pip install -r requirements.txt
python demo/raanana_demo.py          # full pipeline, Raanana pilot
pytest tests/ -v                     # unit + plugin isolation tests
```

Expected outputs in `reports/raanana/{year}/`:
- `report_raanana_{year}.html` — interactive RTL report with Leaflet map
- `report_raanana_{year}.pdf`  — official signed version
- `report_raanana_{year}.json` — machine-readable
- `map_raanana_{year}.html`    — standalone Leaflet map
- `context_raanana_{year}.json`— feeds next year's cumulative context

---

## Data Sources

| Source | Type | Status |
|---|---|---|
| Israel Water Authority (data.gov.il) | CKAN API | Working connector |
| PRTR / מפל"ס registry | Web / GIS | Placeholder → real scraper needed |
| Mei Raanana wastewater monitoring | Web reports | Placeholder → real scraper needed |
| Water Authority Excel consolidation | Excel | Working importer |
| Historical reports 2008 + 2021 | JSON loaders | Planned |

---

## Coordinate System

All spatial operations use **Israel New Grid ITM (EPSG:2039)**  internally.
Conversion to WGS84 (EPSG:4326) for Leaflet maps via `pyproj` in
`plugins/data_sources/coordinate_engine/`.

---

## Testing Guidelines

- Each plugin must have isolated unit tests that do **not** import core pipeline.
- Plugin contract tests in `tests/test_plugin_isolation.py` verify:
  - New plugin registers correctly via `discover_plugins()`
  - Pipeline runs with plugin disabled without error
  - Data contracts (FingerprintResult etc.) validate correctly
- Domain logic tests in `tests/test_analysis.py`.

---

## Branch

Active development: `claude/add-monitoring-report-link-nZBO4`
