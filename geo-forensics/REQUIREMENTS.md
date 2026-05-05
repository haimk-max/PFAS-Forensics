# REQUIREMENTS.md — GeoForensics Dashboard (app.py)

## Surface: app.py ONLY (generate_report.py is frozen)

---

## 1. Data & Analytics (do NOT change)

- [x] PCA: sklearn.decomposition.PCA on fingerprint_nonzero
- [x] MDS: sklearn.manifold.MDS(metric="precomputed") on cosine distance
- [x] Cosine Similarity: unit-vector dot product (0-100%)
- [x] Fingerprint: normalized to 100% per station
- [x] Hierarchical Clustering: ordering for heatmap
- [x] Total Concentration: sum of all compounds per station (max event)
- [x] Findings: auto-generated Hebrew summary via generate_findings_summary()

---

## 2. Compound Classification (PFAS)

- [x] S group (sulfonates): PFOS, PFBS, PFHxS, 6:2FT, PFPeS, PFHpS — blue palette, stacked at bottom
- [x] A group (acids): PFOA, PFHxA, PFHpA, PFNA, PFDA, PFDoA, PFBA, PFPeA, PFESA, ADONA, PFTDA, PFUnA, PFUnDA, GenX — orange palette, stacked on top
- [x] Unknown compounds: appended after A group
- [x] Colors defined in config.py COMPOUND_COLORS

---

## 3. Zero-Station Filtering

- [x] Stations with total_concentration == 0 (or all below LOD) are EXCLUDED from:
  - Section 2 (total concentration bar chart)
  - Section 4 (cosine similarity matrix) ← uses sim_matrix_nonzero
  - Section 5 (PCA)
  - Section 6 (MDS)
- [x] These stations are KEPT in:
  - Section 3 (fingerprint stacked bars)
  - Section 7 (findings summary)
  - Map (shown as gray, small, non-permanent tooltip)

---

## 4. Map

- [x] All stations shown (selected highlighted, unselected faded)
- [x] Drawing tools: polygon, circle, rectangle — select stations inside
- [x] Drawing triggers immediate rerun (analytics update without page reload)
- [x] Labels: appear ONLY at zoom >= 11
- [x] Labels: NO background box (transparent, no border, no shadow)
- [x] Labels: white text-shadow halo for readability
- [x] Labels: greedy anti-overlap (hide if colliding with placed labels)
- [x] Labels: pointer-events: none
- [x] Circle marker size: proportional to log(total_concentration)
- [x] Color by source_type (SOURCE_COLORS in config.py)
- [x] Popup: station name, source type, total concentration, date

---

## 5. Analysis — Holistic

- [x] ALL analysis is done on all data together — NO splitting by time period
- [x] ALL analysis is done on all data together — NO splitting by source type
- [x] The only filtering is: station selection (sidebar multiselect or map drawing)

---

## 6. UI / Layout

- [x] RTL (Hebrew)
- [x] Font stack: 'Assistant', 'Noto Sans Hebrew', 'Arial', system-ui, sans-serif
- [x] KPI cards (4): stations, rows, compounds, date range
- [x] Date fallback: if year < 1980 or NaN → show "לא זוהה בקובץ"
- [x] Quick Insights Row (5 cards): max station, detection rate, dominant compound, most similar pair, pairs >= 90%
- [x] Sidebar success banner on data load
- [x] Softer multiselect tag styling
- [x] Chart-card wrapper (white bg, shadow, rounded)
- [x] Caveat notes under each section (muted italic with "i" prefix)
- [x] Section descriptions (section-desc class)

---

## 7. Section Titles (current)

1. מפת נקודות הדיגום
2. ריכוז סכומי של תרכובות {group.name} בנקודות הדיגום
3. שינוי בהרכב היחסי של תרכובות {group.name}
4. דמיון בין חתימות {group.name} בנקודות הדיגום
5. PCA — ניתוח רכיבים ראשיים
6. MDS — מיפוי מרחק כימי
7. סיכום ממצאים והערות זהירות
8. נתונים גולמיים (expander)

---

## 8. Section-Specific

### Section 2 (Total Concentration)
- [x] Insight banner above chart (top station + value)
- [x] Station names truncated to 18 chars (full in hover)
- [x] Smart Σ format: >=1000→0dp, >=100→1dp, >=10→2dp, else 3dp
- [x] Log Y axis

### Section 3 (Fingerprint)
- [x] Σ label above each bar (using smart format)
- [x] Station names truncated (full in hover)
- [x] S/A color ordering

### Section 4 (Cosine Similarity)
- [x] Textual color legend (4 pills: 0-30 red, 30-70 yellow, 70-90 light green, 90-100 dark green)
- [x] Heatmap ordered by hierarchical clustering
- [x] Top-pairs table: pairs with >= 70% similarity, columns: station A, station B, %, note
- [x] Uses sim_matrix_nonzero (excludes zero stations)

### Sections 5-6 (PCA / MDS)
- [x] Scatter plot colored by source_type
- [x] PCA shows % variance on axis labels
- [x] Uses fingerprint_nonzero / sim_matrix_nonzero
- [x] Professional caveats

### Section 7 (Findings)
- [x] Auto-generated findings
- [x] Final professional disclaimer banner

---

## 9. Methodology Expanders (per section)

- [x] Each analytics section has a collapsible expander with:
  - Principle
  - Formula (in code block)
  - Strengths
  - Weaknesses

---

## 10. Regression Checks (grep before commit)

```bash
# Zero filtering: section 4 must NOT use bare sim_matrix
grep -n "sim_matrix\." app.py | grep -v "sim_matrix_nonzero" | grep -v "sim_matrix ="

# Map labels: must have transparent background
grep -n "background.*transparent" app.py

# S/A ordering: fingerprint columns reordered for PFAS
grep -n "PFAS_COMPOUND_ORDER" app.py
```

---

## 11. כללי מימוש UI (מתודולוגיה — Streamlit)

### טעינת פונטים
- [x] לא להשתמש ב-`@import url(...)` בתוך `<style>` — לא אמין ב-Streamlit
- [x] להשתמש ב-`st.html()` עם `<link rel="stylesheet">` לטעינת Google Fonts
- [x] להגדיר `font = "sans serif"` ב-`.streamlit/config.toml`

### כרטיסים (Cards)
- [x] לא להשתמש ב-`st.markdown('<div class="card">...')` — Streamlit עוטף כל markdown ב-container משלו ושובר את ההיררכיה
- [x] להשתמש ב-`st.container(border=True)` לכרטיסים אמיתיים
- [x] להשתמש ב-`st.metric()` לכרטיסי KPI פשוטים

### CSS במפת Folium (iframe)
- [x] לא להשתמש בסלקטור ID (`#map_{id}`) — ה-ID עשוי לא להתאים בזמן ריצה
- [x] להשתמש בסלקטורי class של Leaflet: `.leaflet-tooltip.leaflet-tooltip-permanent`
- [x] לכסות את כל הכיוונים: `::before`, `-top::before`, `-bottom::before`, `-left::before`, `-right::before`
- [x] הסלקטור הגלובלי בטוח כי ה-CSS חי ב-iframe מבודד

### Multiselect Chips (BaseWeb)
- [x] לכסות את כל האלמנטים המקוננים: `[data-baseweb="tag"]`, span, svg, `[role="presentation"]`
- [x] להוסיף hover states (למשל: X הופך אדום בהצבעה)
- [x] למקד ל-sidebar: `section[data-testid="stSidebar"]` כ-prefix

### ערכת נושא (Theme) — config.toml
- [x] להגדיר `base`, `primaryColor`, `backgroundColor`, `secondaryBackgroundColor`, `textColor`, `font`
- [x] ערכים אלה משפיעים על כל הרכיבים המקוריים של Streamlit (כפתורים, sliders, כותרות)
