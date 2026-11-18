# GeoLibre evaluation (2026-11-18)

**Goal:** replace kepler.gl with [GeoLibre](https://github.com/opengeos/GeoLibre)
for hosting and visualizing the map, adding a story map alongside an
interactive explorer.

**How it was tested:**
- GeoLibre v3.9.0 (MIT license) was built from source.
- It was served from the same local address as our data, so the browser's
  cross-site (CORS) rules didn't apply. This is the setup GeoLibre's own
  self-hosting guide recommends.
- It loaded the privacy-filtered GeoParquet files produced by
  `scripts/04_export_geoparquet.py`: `buildings.parquet` (6,892 buildings)
  and `reports.parquet` (114,386 reports).

## Results

| Need | Result | Notes |
|---|---|---|
| Load our data | ✅ | Both files load straight from a URL (`?data=` or **Add data → Vector layer**). No conversion needed. |
| 3D buildings at real height | ✅ | **Style → 3D extrusion**, with **Height property** set to `height_m`. You must click **Apply 3D extrusion**; the style-type **Apply** button resets the height field. |
| Colour by birds with our bins | ✅ | **Graduated** with a **Manual** scheme, six stops (1, 2, 5, 10, 25, 100), and our palette. It combines with extrusion. |
| Performance | ✅ | Downtown Toronto stayed smooth while tilting and zooming. The 114k report points load as client-side vector tiles. |
| Filters on buildings | ✅ | **Quick filters** (checkboxes, ranges, text) work on the buildings layer and stay available in the read-only viewer. |
| Filters on report points | ⚠️ | The 114k-point layer streams as tiles. Its quick-filter panel reported "no features loaded" at national zoom, so species/date/outcome filters on points are unproven. Possible fixes: a smaller points file, or loading without streaming. |
| Building totals that change with filters | ❌ | Quick filters hide features but never re-count them. Our kepler sidebar re-totals each building by species, years, season and outcome; GeoLibre's viewer can't. Workaround: ready-made building layers per slice (e.g. Fall, Spring, last 5 years, dead only) that users switch between. |
| Story map | ✅ | **Project → Story map** gives chapters with camera fly-to, per-chapter layer fades, autoplay, a pause-and-explore mode, and export to standalone HTML or a PDF handout. Tested with one chapter over our data. |
| Read-only public viewer | ✅ (docs) | `?url=<project>.geolibre&layout=viewer` shows layers, search, identify and quick filters with editing hidden. `maponly` gives a bare map for embedding. |
| Hosting | ✅ (docs) | GeoLibre doesn't host data. It reads our files plus a `.geolibre` project file by URL. Options are GeoLibre's hosted viewer pointing at our GitHub Pages files, or our own copy of the GeoLibre build on our domain. |

## What changes for users

- **Gained:**
  - A proper story map.
  - SQL, charts and attribute tables for scientists.
  - A standard project file that anyone can open in GeoLibre, desktop or web.
  - An MIT-licensed, actively maintained base.
- **Lost:**
  - Live re-totalling of buildings under filters.
  - Our custom sidebar: summary numbers, top-10 buildings with fly-to, and
    the privacy disclosure line. Some of this can come back through
    GeoLibre's dashboard widgets and bookmarks, which still needs testing.
- **Same:** the data and the privacy rules. Every view reads the same
  filtered bundle.

## Proposed migration

1. **Data:** publish `buildings.parquet` and `reports.parquet`, plus
   ready-made per-slice building layers, from step 4 of the pipeline.
2. **Explorer project** (`site/bird-collisions.geolibre`):
   - the buildings layer in 3D with our bins,
   - the slice layers, the points, and quick filters,
   - bookmarks for the city jump-links,
   - a dashboard with headline numbers.
   Opened at `?url=…&layout=viewer`.
3. **Story map:** 5–7 chapters in the same project, exported to standalone
   HTML for the landing page.
4. **Hosting:** GitHub Pages serves the data, the project file and the story
   HTML. Choose between GeoLibre's hosted viewer (zero maintenance, but
   Google Analytics on their site) and our own GeoLibre build on Pages (no
   analytics, but a ~200 MB build to keep updated).
5. **Retire** the kepler `web/` app once the GeoLibre explorer covers what
   decision-makers need.

## Migration status (2026-11-18)

Built so far:
- **Data:** `scripts/04_export_geoparquet.py` writes `site/data/`:
  - buildings with all-years, fall, spring and last-5-years columns,
  - reports split into three eras, each under 50k,
  - GeoJSON for the story page.
- **Explorer project:** `scripts/05_build_site.py` writes it using the
  `geolibre` Python package (3.9.0).
- **Story and landing pages:** `site/story/` and `site/index.html`.
- **Deploy:** `.github/workflows/pages.yml` publishes `site/`.

Lessons from building the project file:
- **Don't pass `data_format="parquet"`.** It routes the file through GDAL,
  which rejects it; let GeoLibre auto-detect.
- **`geolibre.project.vector_layer` sets `controlOwnsPaint: True`.** That
  blocks GeoLibre's own colours and extrusion, so we set it to `False` (our
  layers are all in memory).
- **Checkbox filters list at most 200 distinct values.** Species uses a text
  match instead.
- **Filter value lists are computed only while the page is drawing.** In a
  hidden browser tab they stay empty; with the page visible they fill in
  within seconds. This affects headless testing only, not real viewers.

Checked visually on 2026-11-18 in the local GeoLibre 3.9.0 viewer
(`layout=viewer`):
- 3D buildings at real height in our six colour classes.
- Report points in outcome colours.
- Filters listing every value with counts (e.g. 2021–2026: 35,817 dead,
  8,787 alive).
- The species text filter narrowing the points.
- The story presentation flying between chapters.

The standalone story page was checked too: the continental dots, the 3D
chapters, and the fall chapter switching the map and legend. Both site
pages fit a 375 px phone with no sideways scrolling.
