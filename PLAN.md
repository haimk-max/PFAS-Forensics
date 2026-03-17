# Geo-Forensics PFAS - Work Plan & Architecture
## Version 1.0 | March 2026

---

## 1. Project Overview

A Streamlit-based analytical tool for Israel Water Authority staff to investigate
PFAS contamination data through geographic filtering, chemical fingerprinting,
and statistical analysis (PCA, Cosine Similarity).

---

## 2. Proposed Folder Structure

```
geo-forensics-pfas/
├── app.py                      # Streamlit entry point
├── requirements.txt            # Python dependencies
├── config.py                   # App configuration & constants
├── README.md                   # Project documentation
│
├── data/                       # Data directory
│   ├── sample/                 # Sample/synthetic data for development
│   │   └── sample_pfas.csv
│   └── uploads/                # User uploaded files (gitignored)
│
├── src/                        # Core application modules
│   ├── __init__.py
│   ├── data_loader.py          # CSV/Excel parsing & validation
│   ├── data_model.py           # Data schemas & transformations
│   ├── geo_utils.py            # Coordinate conversion (ITM ↔ WGS84)
│   ├── filtering.py            # Geo-filtering & hydraulic filtering logic
│   ├── analytics.py            # PCA, Cosine Similarity, Attenuation
│   └── export.py               # HTML & CSV export engine
│
├── ui/                         # Streamlit UI components
│   ├── __init__.py
│   ├── sidebar.py              # Sidebar controls & navigation
│   ├── step1_overview.py       # Macro Overview - Heatmap/Clusters
│   ├── step2_geofilter.py      # Geo-Filtering (text, search, lasso)
│   ├── step3_layers.py         # Layer management & hydraulic filters
│   └── step4_dashboard.py      # Analytics Dashboard
│
├── maps/                       # Map-related components
│   ├── __init__.py
│   ├── base_map.py             # Folium base map of Israel
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

## 3. Tech Stack (Detail)

| Component           | Technology               | Purpose                                  |
|---------------------|--------------------------|------------------------------------------|
| Language            | Python 3.11+             | Core development                         |
| UI Framework        | Streamlit >= 1.31        | Web application                          |
| Data Processing     | pandas, numpy            | DataFrames & computation                 |
| ML/Statistics       | scikit-learn             | PCA & Cosine Similarity                  |
| Coordinate Convert  | pyproj                   | ITM ↔ WGS84 conversion                  |
| Mapping             | Folium + streamlit-folium| Interactive maps with Leaflet            |
| Drawing on Map      | folium.plugins.Draw      | Lasso/Polygon/Circle selection           |
| Charts              | Plotly                   | Interactive charts (bar, scatter, heatmap)|
| Export              | Plotly + Jinja2          | Standalone HTML report generation        |
| Testing             | pytest                   | Unit & integration tests                 |

---

## 4. Data Model

### 4.1 Input Schema (Required Columns)

| Column (Hebrew)     | Internal Name     | Type     | Description                    |
|---------------------|-------------------|----------|--------------------------------|
| שם תחנה             | station_name      | string   | Monitoring station name        |
| X (ITM)             | x_itm             | float    | ITM Easting coordinate         |
| Y (ITM)             | y_itm             | float    | ITM Northing coordinate        |
| תאריך דיגום         | sample_date       | date     | Sampling date                  |
| סוג מקור            | source_type       | string   | Water source type              |
| סמל תרכובת          | compound          | string   | PFAS compound symbol           |
| ריכוז (µg/L)       | concentration     | float    | Measured concentration         |

### 4.2 Derived Fields (Computed)

| Field              | Type    | Description                               |
|--------------------|---------|-------------------------------------------|
| lat, lon           | float   | WGS84 coordinates (converted from ITM)    |
| total_pfas         | float   | ΣPFAS per station per date                |
| pca_x, pca_y       | float   | PCA projection coordinates                |
| cosine_sim         | float   | Cosine similarity score vs reference      |

---

## 5. Module Specifications

### 5.1 data_loader.py
- `load_file(file) -> pd.DataFrame` - Parse CSV/Excel, detect encoding (UTF-8/CP1255)
- `validate_schema(df) -> (bool, list[str])` - Verify required columns exist
- `normalize_columns(df) -> pd.DataFrame` - Map Hebrew column names to internal names
- Support flexible column name matching (fuzzy match for Hebrew variants)

### 5.2 geo_utils.py
- `itm_to_wgs84(x, y) -> (lat, lon)` - Single point conversion
- `batch_convert(df) -> df` - Vectorized conversion for entire DataFrame
- `calc_distance(p1, p2) -> float` - Haversine distance in meters
- `point_in_polygon(point, polygon) -> bool` - Spatial containment check

### 5.3 filtering.py
- `filter_by_bbox(df, bounds) -> df` - Bounding box filter
- `filter_by_polygon(df, polygon) -> df` - Polygon/Lasso filter
- `filter_by_radius(df, center, radius_km) -> df` - Radius filter
- `filter_by_source_type(df, types) -> df` - Medium classification filter
- `filter_by_threshold(df, min_conc, max_conc) -> df` - Concentration threshold

### 5.4 analytics.py
- `calc_total_pfas(df) -> df` - Compute ΣPFAS per station
- `build_fingerprint_matrix(df) -> df` - Pivot: stations × compounds (relative %)
- `run_pca(matrix, n_components=2) -> (scores, loadings, explained_var)`
- `calc_cosine_similarity(matrix) -> similarity_matrix` - Station-to-station similarity
- `calc_attenuation(df, source_station) -> df` - Distance vs concentration decay

### 5.5 export.py
- `generate_html_report(figures, tables, metadata) -> str` - Self-contained HTML
- `export_csv(df) -> bytes` - Filtered & processed data export
- HTML report uses embedded Plotly JSON + inline CSS (no external dependencies)

---

## 6. Implementation Phases

### Phase 1: Foundation (Sprint 1)
**Goal: Project skeleton + data loading + coordinate conversion**

- [ ] Initialize project structure and dependencies
- [ ] Implement `data_loader.py` - CSV/Excel parsing with Hebrew support
- [ ] Implement `geo_utils.py` - ITM ↔ WGS84 conversion
- [ ] Create `data_model.py` - Validation and normalization
- [ ] Generate synthetic sample dataset for development
- [ ] Basic Streamlit app with file upload
- [ ] Unit tests for data loading and geo conversion

### Phase 2: Map & Geo-Filtering (Sprint 2)
**Goal: Interactive map with all 3 filtering methods**

- [ ] Base map of Israel with Folium
- [ ] Heatmap/Cluster layer for ΣPFAS (Step 1 - Overview)
- [ ] Text/dropdown filtering by metadata fields
- [ ] Free text search for stations/locations
- [ ] Lasso/Polygon drawing tool on map (Step 2 - Geo-Filter)
- [ ] Visual feedback: selected stations highlighted on map

### Phase 3: Hydraulic Filtering & Analytics (Sprint 3)
**Goal: Layer management + full analytics dashboard**

- [ ] Medium classification filter (groundwater/surface/reservoir)
- [ ] Concentration threshold slider
- [ ] Source station selection ("reference point")
- [ ] Attenuation chart (logarithmic bar chart)
- [ ] Chemical Fingerprint chart (100% stacked bar)
- [ ] PCA scatter plot with clustering
- [ ] Cosine Similarity heatmap matrix

### Phase 4: Export & Polish (Sprint 4)
**Goal: Production-ready MVP with export capabilities**

- [ ] Standalone HTML report export
- [ ] CSV export of processed data
- [ ] UI polish: Hebrew RTL support, responsive layout
- [ ] Error handling & edge cases
- [ ] Performance optimization for large datasets
- [ ] End-to-end testing with realistic data
- [ ] Documentation

---

## 7. Synthetic Data Specification

For development without real data, we'll generate a synthetic dataset simulating:

- **Area:** Kishon Basin (Haifa Bay industrial area)
- **Stations:** ~50 monitoring wells + 10 surface water points
- **Compounds:** PFOS, PFOA, PFHxS, PFNA, PFDA, PFUnDA, PFBS, GenX (8 compounds)
- **Pattern:**
  - Industrial source (high PFOS/PFOA ratio) near "Soltam" area
  - Regional plume with decreasing concentration downstream
  - Background stations with different chemical fingerprint
- **Coordinates:** Realistic ITM coordinates in the Kishon basin area

---

## 8. Key Technical Decisions & Trade-offs

### Streamlit - Pros & Cons
**Pros:**
- Fast prototyping, Python-only (matches team skills)
- Built-in file upload, widgets, caching
- Good for internal tools

**Cons:**
- Limited interactivity for complex map interactions
- Reruns entire script on each interaction (state management challenges)
- Lasso/drawing tool integration requires custom component or workaround

**Mitigation:** Use `st.session_state` extensively. For map drawing, use
`streamlit-folium` with `st_folium()` return values to capture drawn shapes.

### Alternative Considered: Dash (Plotly)
- More flexible for complex interactions
- Better callback system (no full reruns)
- But: steeper learning curve, more boilerplate code
- **Decision:** Start with Streamlit for MVP, migrate to Dash if interactivity
  limitations become blocking.

### Map Drawing (Lasso Tool)
- `folium.plugins.Draw` supports polygon/circle/rectangle drawing
- `streamlit-folium` captures drawn geometries via `st_folium()` return value
- Known limitation: drawing resets on Streamlit rerun
- **Mitigation:** Store drawn geometry in `session_state` immediately after capture

---

## 9. Risks & Mitigations

| Risk                                          | Impact | Mitigation                                    |
|-----------------------------------------------|--------|-----------------------------------------------|
| Map drawing resets on Streamlit rerun          | High   | Persist geometry in session_state              |
| Hebrew text rendering issues                  | Medium | CSS RTL direction + proper font configuration |
| Large dataset performance (>10K rows)         | Medium | pandas optimization + Streamlit caching        |
| ITM coordinate edge cases                     | Low    | Validate coordinate ranges before conversion   |
| Standalone HTML file size (with embedded maps) | Medium | Optimize Plotly JSON, compress assets          |

---

## 10. Open Questions for Discussion

1. **Column Name Flexibility:** Should we support automatic detection of column
   names from various Water Authority export formats, or require a strict template?

2. **Map Tile Provider:** Use OpenStreetMap (free) or Israel-specific tiles
   (e.g., govmap.gov.il) for better Hebrew labels?

3. **Authentication:** Is there a need for user login even for internal use,
   or is network-level access control sufficient?

4. **Deployment:** Where will the MVP be hosted? Local machine, internal server,
   or cloud (e.g., Streamlit Cloud)?

5. **Real-time Updates:** For Phase 2 (DB integration), what database technology
   does the Water Authority use? (SQL Server, Oracle, PostgreSQL?)
