# GeoForensics - Contaminant Source Investigation Platform
## Version 2.0 | March 2026

---

## 1. Project Overview

**A local-first, Streamlit-based geo-forensic platform for investigating contaminant sources in water, soil, and wastewater.**

The tool enables geohydrologists to load sampling data, identify contamination hotspots on a map, select a suspect source, and run analytical tools that test the connection between source and contamination points.

### Key Principles:
- **Generic** - supports any contaminant group (PFAS, fuels, chlorinated solvents, heavy metals, nitrates, etc.)
- **Multi-layer** - integrates water sampling, wastewater treatment plants (WWTP), industrial discharge points, and (future) soil analysis data
- **Local-first** - runs entirely on the user's machine; no data leaves the computer (only map tiles are loaded from the internet)
- **Export-ready** - generates standalone HTML reports that can be attached to expert opinions

### Target Users:
Small team of technical experts (geohydrologists) at the Israel Water Authority.

---

## 2. Investigation Funnel (User Flow)

```
┌─────────────────────────────────────────────────────┐
│  Step 1: OVERVIEW                                    │
│  "Where is there a problem?"                         │
│  → National heatmap of total contaminant levels      │
├─────────────────────────────────────────────────────┤
│  Step 2: GEO-FILTER                                  │
│  "What area interests me?"                           │
│  → Draw on map / select basin / free text search     │
├─────────────────────────────────────────────────────┤
│  Step 3: LAYER & THRESHOLD FILTER                    │
│  "What exactly am I looking at?"                     │
│  → Filter by water type, concentration threshold,    │
│    select suspect source point                       │
├─────────────────────────────────────────────────────┤
│  Step 4: FORENSIC ANALYSIS                           │
│  "What is the evidence?"                             │
│  → 4 analytical tools:                               │
│    1. Attenuation (distance vs concentration)        │
│    2. Chemical Fingerprint (stacked bar)             │
│    3. PCA (statistical clustering)                   │
│    4. Cosine Similarity (% similarity matrix)        │
├─────────────────────────────────────────────────────┤
│  Step 5: EXPORT                                      │
│  → Standalone HTML report for attachment to opinions │
└─────────────────────────────────────────────────────┘
```

---

## 3. Proposed Folder Structure

```
geo-forensics/
├── app.py                      # Streamlit entry point
├── requirements.txt            # Python dependencies
├── config.py                   # App configuration & constants
├── README.md                   # Project documentation
│
├── data/                       # Data directory
│   ├── sample/                 # Sample/synthetic data for development
│   │   └── sample_pfas.xlsx
│   └── uploads/                # User uploaded files (gitignored)
│
├── src/                        # Core application modules
│   ├── __init__.py
│   ├── data_loader.py          # Excel/CSV parsing & validation
│   ├── data_model.py           # Data schemas & transformations
│   ├── contaminant_groups.py   # Contaminant group definitions & thresholds
│   ├── geo_utils.py            # Coordinate conversion (ITM ↔ WGS84)
│   ├── filtering.py            # Geo-filtering & layer filtering logic
│   ├── analytics.py            # PCA, Cosine Similarity, Attenuation
│   └── export.py               # HTML & CSV export engine
│
├── ui/                         # Streamlit UI components
│   ├── __init__.py
│   ├── sidebar.py              # Sidebar controls & navigation
│   ├── step1_overview.py       # Macro Overview - Heatmap/Clusters
│   ├── step2_geofilter.py      # Geo-Filtering (text, search, lasso)
│   ├── step3_layers.py         # Layer management & threshold filters
│   ├── step4_dashboard.py      # Analytics Dashboard (4 forensic tools)
│   └── step5_export.py         # Export controls & preview
│
├── maps/                       # Map-related components
│   ├── __init__.py
│   ├── base_map.py             # Folium base map (OSM + satellite toggle)
│   └── drawing_tools.py        # Lasso/Bounding Box tools
│
├── assets/                     # Static assets
│   ├── israel_boundary.geojson # Israel boundary for base map
│   └── style.css               # Custom CSS for Streamlit
│
└── tests/                      # Unit tests
    ├── test_data_loader.py
    ├── test_geo_utils.py
    ├── test_analytics.py
    └── test_filtering.py
```

---

## 4. Tech Stack

| Component           | Technology               | Purpose                                  |
|---------------------|--------------------------|------------------------------------------|
| Language            | Python 3.11+             | Core development                         |
| UI Framework        | Streamlit >= 1.31        | Local web application                    |
| Data Processing     | pandas, openpyxl         | DataFrames & Excel reading               |
| ML/Statistics       | scikit-learn             | PCA & Cosine Similarity                  |
| Coordinate Convert  | pyproj                   | ITM ↔ WGS84 conversion                  |
| Mapping             | Folium + streamlit-folium| Interactive maps (OSM + satellite tiles) |
| Drawing on Map      | folium.plugins.Draw      | Lasso/Polygon/Circle selection           |
| Charts              | Plotly                   | Interactive charts (bar, scatter, heatmap)|
| Export              | Plotly + Jinja2          | Standalone HTML report generation        |
| Testing             | pytest                   | Unit & integration tests                 |

**Deployment:** Runs locally via `streamlit run app.py` (localhost:8501).
No cloud, no external server. Only map tile images are fetched from the internet.

---

## 5. Data Model

### 5.1 Data Layers (Input Sources)

| Layer | Description | Input Format | Phase |
|-------|-------------|--------------|-------|
| **Water Sampling** | Boreholes, streams, reservoirs | Excel (Water Authority format) | MVP |
| **WWTP (מט"שים)** | Wastewater treatment plant locations & discharge data | Excel | MVP / Phase 2 |
| **Industrial Discharge** | Licensed industrial discharge points | Excel | Phase 2 |
| **Soil Analysis** | Contaminant analysis at contaminated sites | Excel | Future |

Each layer can serve as **evidence points** (sampling results) or **suspect sources** (potential contamination origin).

### 5.2 Contaminant Groups

The system is generic and supports any contaminant group. Each group defines:

```python
contaminant_group = {
    "name": "PFAS",                          # Display name
    "compounds": ["PFOS", "PFOA", "PFHxS", "PFNA", ...],  # Compound list
    "thresholds": {"PFOS": 0.1, "PFOA": 0.1, ...},        # Regulatory limits (µg/L)
    "sum_field": "total_pfas",               # Name of the sum field
    "unit": "µg/L",                          # Concentration unit
}
```

**Pre-configured groups (can be extended):**
- PFAS (PFOS, PFOA, PFHxS, PFNA, PFDA, PFUnDA, PFBS, GenX)
- Fuels (Benzene, Toluene, Ethylbenzene, Xylenes - BTEX)
- Chlorinated Solvents (TCE, PCE, DCE, Vinyl Chloride)
- Heavy Metals (Pb, Cd, Cr, As, Hg, Ni, Zn)
- Nitrates (NO3, NO2, NH4)

### 5.3 Core Input Schema (Water Sampling)

| Column (Hebrew)     | Internal Name     | Type     | Description                    |
|---------------------|-------------------|----------|--------------------------------|
| שם תחנה             | station_name      | string   | Monitoring station name        |
| X (ITM)             | x_itm             | float    | ITM Easting coordinate         |
| Y (ITM)             | y_itm             | float    | ITM Northing coordinate        |
| תאריך דיגום         | sample_date       | date     | Sampling date                  |
| סוג מקור            | source_type       | string   | Water source type              |
| סמל תרכובת          | compound          | string   | Compound symbol                |
| ריכוז               | concentration     | float    | Measured concentration         |
| יחידה               | unit              | string   | Unit (µg/L, mg/L, etc.)       |

### 5.4 Derived Fields (Computed)

| Field              | Type    | Description                               |
|--------------------|---------|-------------------------------------------|
| lat, lon           | float   | WGS84 coordinates (converted from ITM)    |
| total_concentration| float   | Σ compounds per station per date          |
| pca_x, pca_y       | float   | PCA projection coordinates                |
| cosine_sim         | float   | Cosine similarity score vs reference      |

---

## 6. Module Specifications

### 6.1 data_loader.py
- `load_file(file) -> pd.DataFrame` - Parse Excel/CSV, detect encoding (UTF-8/CP1255)
- `validate_schema(df, group) -> (bool, list[str])` - Verify required columns
- `normalize_columns(df) -> pd.DataFrame` - Map Hebrew column names to internal names
- Support flexible column name matching (fuzzy match for Hebrew variants)

### 6.2 contaminant_groups.py
- `get_group(name) -> ContaminantGroup` - Load predefined contaminant group
- `list_groups() -> list[str]` - List available groups
- `detect_group(df) -> str` - Auto-detect contaminant group from compound names
- Allow user-defined custom groups

### 6.3 geo_utils.py
- `itm_to_wgs84(x, y) -> (lat, lon)` - Single point conversion
- `batch_convert(df) -> df` - Vectorized conversion for entire DataFrame
- `calc_distance(p1, p2) -> float` - Haversine distance in meters
- `point_in_polygon(point, polygon) -> bool` - Spatial containment check

### 6.4 filtering.py
- `filter_by_bbox(df, bounds) -> df` - Bounding box filter
- `filter_by_polygon(df, polygon) -> df` - Polygon/Lasso filter
- `filter_by_radius(df, center, radius_km) -> df` - Radius filter
- `filter_by_source_type(df, types) -> df` - Source type filter
- `filter_by_threshold(df, min_conc, max_conc) -> df` - Concentration threshold
- `filter_by_layer(df, layer_type) -> df` - Filter by data layer

### 6.5 analytics.py
- `calc_total_concentration(df, group) -> df` - Compute Σ compounds per station
- `build_fingerprint_matrix(df, group) -> df` - Pivot: stations × compounds (relative %)
- `run_pca(matrix, n_components=2) -> (scores, loadings, explained_var)`
- `calc_cosine_similarity(matrix) -> similarity_matrix` - Station-to-station similarity
- `calc_attenuation(df, source_station) -> df` - Distance vs concentration decay

### 6.6 export.py
- `generate_html_report(figures, tables, metadata) -> str` - Self-contained HTML
- `export_csv(df) -> bytes` - Filtered & processed data export
- HTML report uses embedded Plotly JSON + inline CSS (no external dependencies)

---

## 7. Implementation Phases

### Phase 1: Foundation (Sprint 1)
**Goal: Project skeleton + data loading + coordinate conversion**

- [ ] Initialize project structure and dependencies
- [ ] Implement `contaminant_groups.py` - Group definitions (PFAS first)
- [ ] Implement `data_loader.py` - Excel parsing with Hebrew support
- [ ] Implement `geo_utils.py` - ITM ↔ WGS84 conversion
- [ ] Create `data_model.py` - Validation and normalization
- [ ] Generate synthetic sample dataset for development
- [ ] Basic Streamlit app with file upload + contaminant group selector
- [ ] Unit tests for data loading and geo conversion

### Phase 2: Map & Geo-Filtering (Sprint 2)
**Goal: Interactive map with filtering and multiple tile layers**

- [ ] Base map of Israel with Folium (OSM + satellite tile toggle)
- [ ] Heatmap/Cluster layer for Σ concentrations (Step 1 - Overview)
- [ ] Text/dropdown filtering by metadata fields
- [ ] Free text search for stations/locations
- [ ] Lasso/Polygon drawing tool on map (Step 2 - Geo-Filter)
- [ ] Visual feedback: selected stations highlighted on map
- [ ] Layer icons: different markers for boreholes, WWTP, industrial

### Phase 3: Forensic Analytics (Sprint 3)
**Goal: Layer management + full analytics dashboard**

- [ ] Source type filter (groundwater/surface/reservoir/WWTP)
- [ ] Concentration threshold slider
- [ ] Source station selection ("suspect point")
- [ ] Attenuation chart (distance vs concentration, logarithmic)
- [ ] Chemical Fingerprint chart (100% stacked bar)
- [ ] PCA scatter plot with clustering
- [ ] Cosine Similarity heatmap matrix

### Phase 4: Export & Polish (Sprint 4)
**Goal: Production-ready MVP with export capabilities**

- [ ] Standalone HTML report export (maps + charts + tables)
- [ ] CSV export of processed data
- [ ] UI polish: Hebrew RTL support, responsive layout
- [ ] Error handling & edge cases
- [ ] Performance optimization for large datasets
- [ ] End-to-end testing with realistic data

### Phase 5: Multi-Layer Integration (Future)
**Goal: Additional data sources**

- [ ] Industrial discharge points layer
- [ ] Soil contamination data layer
- [ ] Database connectivity (replace Excel input)
- [ ] Cross-layer correlation analysis

---

## 8. Synthetic Data Specification

For development without real data, we'll generate a synthetic dataset simulating:

- **Area:** Kishon Basin (Haifa Bay industrial area)
- **Stations:** ~50 monitoring wells + 10 surface water points + 3 WWTP
- **Contaminant Group:** PFAS (first use case)
- **Compounds:** PFOS, PFOA, PFHxS, PFNA, PFDA, PFUnDA, PFBS, GenX (8 compounds)
- **Pattern:**
  - Industrial source (high PFOS/PFOA ratio) near industrial area
  - Regional plume with decreasing concentration downstream
  - Background stations with different chemical fingerprint
  - WWTP with distinct signature
- **Coordinates:** Realistic ITM coordinates in the Kishon basin area

---

## 9. Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | Streamlit | Simplest for Python team, fast prototyping, good for internal tools |
| Deployment | Local only | Security requirement - no data leaves the machine |
| Map tiles | OSM + satellite (online) | Only images downloaded, no data uploaded |
| Map library | Folium | Best Leaflet integration for Python, good drawing tools |
| Charts | Plotly | Interactive, embeddable in HTML export |
| Input format | Excel (Phase 1) → DB (future) | Matches current workflow |
| Contaminant groups | Generic with presets | Future-proof, not locked to PFAS |
| Export | HTML + CSV | HTML for reports, CSV for further analysis |

---

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Map drawing resets on Streamlit rerun | High | Persist geometry in session_state |
| Hebrew text rendering issues | Medium | CSS RTL direction + proper font config |
| Large dataset performance (>10K rows) | Medium | pandas optimization + Streamlit caching |
| ITM coordinate edge cases | Low | Validate coordinate ranges before conversion |
| HTML report file size (embedded maps) | Medium | Optimize Plotly JSON, compress assets |
| Multiple contaminant group support complexity | Medium | Start with PFAS, generalize incrementally |

---

## 11. Open Questions

1. **Column Name Flexibility:** Support auto-detection of column names from various Water Authority export formats, or require a strict template?

2. **Map Tile Provider:** Use OpenStreetMap (free, global) or Israel-specific tiles (govmap.gov.il) for better Hebrew labels?

3. **Database Type:** For future DB integration - what database does the team use? (SQL Server, PostgreSQL, SQLite?)

4. **WWTP Data Format:** What format does the WWTP discharge data come in? Same Excel structure or different?
