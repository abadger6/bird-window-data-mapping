# To do

Items deliberately left for after launch.

## Data source

- [ ] **Confirm attribution wording with FLAP / the Global Bird Collision Mapper.**
  The [download page](https://www.birdmapper.org/pages/download-the-data) and FAQ
  state no licence, terms or citation string (checked 2026-11-18). The site
  currently credits "Global Bird Collision Mapper (FLAP Canada and partner
  monitoring groups)" with a link. Update if they give preferred wording.

## Data coverage

- [ ] **Add fuller Chicago data.** The Global Bird Collision Mapper export has
  only 2018–2022 Chicago Bird Collision Monitors records and 130 reports near
  McCormick Place. The Field Museum's long-term McCormick survey and Chicago
  Bird Collision Monitors' full archive would show Chicago's true scale. Both
  need permission and a second loader in `pipeline/collisions.py` (dedupe
  against the export on date + location + species).

## Clean-up

- [ ] **Retire the kepler.gl viewer (`web/`).** Before deleting:
  `scripts/03_build_web_data.py` writes its intermediate bundle to
  `web/public/data/`, which `scripts/04_export_geoparquet.py` reads. Move that
  output to `data/processed/` and point step 04 at it. Then delete `web/` and
  remove its entries from `.gitignore` and the README.
- [ ] **Custom domain (optional).** Add a `CNAME` record at the DNS provider,
  set the domain under **Settings → Pages**, and rebuild with that address. The
  workflow already takes the address from Pages.
- [ ] **Self-hosted GeoLibre viewer (optional).** The explorer opens in the
  hosted `web.geolibre.app`, which runs Google Analytics and updates on its own
  schedule (we tested on 3.9.0). To self-host, build GeoLibre for the site and
  set `EXPLORER_VIEWER` in `.github/workflows/pages.yml`. See
  [docs/geolibre-evaluation.md](geolibre-evaluation.md).

## Polish

- [ ] **Story footer link contrast in GeoLibre.** In the explorer's in-app
  story, the "Global Bird Collision Mapper" footer link draws dark blue on
  the dark panel. GeoLibre styles that link; try a light inline colour in the
  footer HTML in `pipeline/geolibre_project.py`, or the light story theme.

## Keeping the data current

- [ ] **Document and/or automate the refresh.** Today it is manual:
  1. Download a new CSV from the Global Bird Collision Mapper into
     `data/raw/flap_gbcm_export.csv`.
  2. Run `scripts/01` to `04`. Step 02 reuses its building cache and only
     fetches new areas.
  3. Run `uv run pytest`.
  4. Commit `site/data/` and push; Pages redeploys.

  Options: a written runbook, or a scheduled job. A scheduled job would need
  an automated way to get the export, which the download page doesn't offer
  (it is a manual CSV download).

## Explorer bugs

- [x] **3D tilt after leaving the story (reported 2026-11-18; worked around).**
  After Exit the map lay flat (pitch 0), and GeoLibre has no tilt control
  except right-drag / Ctrl-drag / Shift+↑. Keyboard tilt was confirmed working
  after Exit; mouse tilt couldn't be tested from automation, since synthetic
  drags don't reach MapLibre even on a map without a story. Fix: the
  overview views are tilted 45° (zooming in keeps the pitch, checked to zoom
  13), and the last chapter and landing page explain how to tilt.
  - [ ] If a real right-drag / Ctrl-drag still fails after Exit, report it
    to opengeos/GeoLibre (suspect `suspendNavigation` restore).
