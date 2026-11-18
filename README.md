# Bird–Window Collisions Map (US + Canada)

Reported bird–window collisions, each attributed to the building where the
bird was found and shown in 3D at the building's real height. Made for
decision-makers and scientists.

**Live:** https://abadger6.github.io/bird-window-data-mapping/ · [story](https://abadger6.github.io/bird-window-data-mapping/story/) · [explorer](https://web.geolibre.app/?url=https%3A%2F%2Fabadger6.github.io%2Fbird-window-data-mapping%2Fbird-collisions.geolibre&layout=viewer)

The public site (`site/`) has three parts:

| Part | What it is |
|---|---|
| **Landing page** (`site/index.html`) | Headline numbers, links, data downloads, caveats. |
| **Story** (`site/story/`) | A scroll-driven story map (MapLibre) of where collisions are reported, the worst buildings, fall migration and species. |
| **Explorer** (`site/bird-collisions.geolibre`) | A [GeoLibre](https://geolibre.app) project, opened in GeoLibre's read-only viewer: 3D buildings, every report as a point, quick filters, city bookmarks, and the same story as an in-app presentation. |

**Privacy:** reports at private homes are excluded to protect reporters
(5.6% of birds). See the data notes.

**Scope:** this is a *descriptive* product; it shows what has been reported.
It contains no predictive or risk modelling, which lives in the sibling
`bird-window-collision-modeling` repo.

**Further reading:**
- Data decisions and caveats: [docs/data-notes.md](docs/data-notes.md).
- Why GeoLibre and what it can't do: [docs/geolibre-evaluation.md](docs/geolibre-evaluation.md).

## The explorer

| Layers | What they show |
|---|---|
| Buildings (4 views) | All years / fall migration / spring migration / last 5 years. Height = building height; colour = birds reported in that view. Only "all years" starts on. Filters: country, height. |
| Reports (3 eras) | 1996–2013, 2014–2020, 2021–2026, one point per report coloured by outcome. Only the latest era starts on. Filters: species (text match), outcome, season, year, monitoring group. |

Two GeoLibre limits shape this design:
- **Filters can't re-total buildings.** Each building view is a precomputed
  column in `buildings.parquet`.
- **Layers over 50,000 features switch to tiles**, and a tiled layer's filters
  only see the area on screen. The reports are therefore split into eras that
  each stay under the limit; `scripts/04` fails if an era grows past it.

## Rebuilding

Requires [uv](https://docs.astral.sh/uv/). No API keys needed: Overture data
is read anonymously from its public S3 bucket.

```bash
uv sync
```

1. Put the FLAP Global Bird Collision Mapper CSV export at `data/raw/flap_gbcm_export.csv`.

2. Clean the records, strip personal fields, and clip to US + Canada:

```bash
uv run python scripts/01_clean_collisions.py
```

3. Fetch Overture footprints around every collision site. This takes about 45 minutes and can be resumed if interrupted:

```bash
uv run python scripts/02_fetch_buildings.py
```

4. Snap reports to buildings, raise tower heights from Overture building parts, remove likely private homes, and write the intermediate bundle in `web/public/data/`:

```bash
uv run python scripts/03_build_web_data.py
```

5. Write the public data in `site/data/` (GeoParquet, building views, report eras, story GeoJSON):

```bash
uv run python scripts/04_export_geoparquet.py
```

6. Build the GeoLibre project, story chapters and links for a given site address. CI runs this with the GitHub Pages address:

```bash
uv run python scripts/05_build_site.py --site-url https://<user>.github.io/<repo>/
```

7. Run the tests:

```bash
uv run pytest
```

## Publishing

Pushing to `main` runs [.github/workflows/pages.yml](.github/workflows/pages.yml). It rebuilds
the project for the Pages address and publishes `site/`. In the repo settings,
set **Pages → Source → GitHub Actions** once.

The explorer opens in GeoLibre's hosted web app (`EXPLORER_VIEWER` in the
workflow). To avoid the hosted app's Google Analytics, point it at a
self-hosted GeoLibre build instead.

To preview locally, serve the repo root (any static server works) and open
`/site/`:

```bash
python3 -m http.server 8000
```

The explorer link needs a GeoLibre app that can reach the files. Rebuild with
`--site-url http://localhost:8000/site/` and a local GeoLibre build passed as
`--viewer`.

## Layout

```
pipeline/
  collisions.py        cleaning rules, PII stripping, US+CA clip
  boundaries.py        US + Canada maritime outlines (Overture divisions)
  buildings.py         Overture fetch near points, cleaning, heights (incl. building parts)
  attribution.py       snap reports to nearest footprint ≤ 25 m
  privacy.py           exclude reports at likely private homes / unmatched points
  story.py             story chapters (numbers computed from the data)
  geolibre_project.py  GeoLibre explorer project (layers, filters, bookmarks, story)
scripts/               01–05 pipeline entry points
tests/                 pytest
site/                  the public site (GitHub Pages)
  data/                published, PII-free GeoParquet + GeoJSON
  story/               scroll-driven story page
web/                   previous kepler.gl viewer (to be retired)
docs/                  data notes, GeoLibre evaluation
```

## Data & licensing

- **Collision reports:** [Global Bird Collision Mapper](https://www.birdmapper.org/pages/download-the-data)
  (FLAP Canada and partner monitoring groups), from its public download. The
  site states no licence or citation wording; see [docs/TODO.md](docs/TODO.md).
- **Buildings & boundaries:** © Overture Maps Foundation, **ODbL**:
  attribution required (shown on every page).
- **Basemap:** OpenFreeMap, © OpenMapTiles, © OpenStreetMap contributors.
- **Explorer:** [GeoLibre](https://github.com/opengeos/GeoLibre) (MIT).
