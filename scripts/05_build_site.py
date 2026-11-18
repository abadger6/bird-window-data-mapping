"""Step 5 — build the GeoLibre project and story for the public site.

    uv run python scripts/05_build_site.py --site-url https://<user>.github.io/<repo>/

Reads  site/data/{buildings.parquet,reports.parquet,meta.json}
Writes site/bird-collisions.geolibre   GeoLibre project: explorer layers, bookmarks, story map
       site/story/chapters.json        the same story chapters, for site/story/index.html
       site/config.json                URLs the landing page links to

``--site-url`` is where site/ is served. GeoLibre layers load data by absolute
URL, so the project must be rebuilt if the site moves.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import geopandas as gpd  # noqa: E402
from geolibre import authoring  # noqa: E402

from pipeline import geolibre_project, story  # noqa: E402

SITE = ROOT / "site"
PROJECT_NAME = "bird-collisions.geolibre"
DEFAULT_VIEWER = "https://web.geolibre.app/"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-url", required=True, help="public URL of site/, e.g. https://user.github.io/repo/")
    ap.add_argument("--viewer", default=DEFAULT_VIEWER,
                    help="GeoLibre web app that opens the project (hosted, or a self-hosted copy)")
    args = ap.parse_args()
    site_url = args.site_url.rstrip("/") + "/"

    meta = json.loads((SITE / "data/meta.json").read_text())
    bldgs = gpd.read_parquet(SITE / "data/buildings.parquet")
    reports = gpd.read_parquet(SITE / "data/reports.parquet")
    chapters = story.build_chapters(bldgs, reports, meta)

    proj = geolibre_project.build(site_url + "data/", chapters, meta)
    authoring.save_project(SITE / PROJECT_NAME, proj)

    (SITE / "story").mkdir(exist_ok=True)
    (SITE / "story/chapters.json").write_text(json.dumps({
        "title": "Bird–Window Collisions in the US & Canada",
        "subtitle": f"{meta['date_min'][:4]}–{meta['date_max'][:4]} · reports attributed to buildings",
        "bins": [[v, c, lab] for v, c, lab in geolibre_project.BIRD_STOPS],
        "chapters": [c.to_dict() for c in chapters],
    }, indent=2, ensure_ascii=False))

    project_url = site_url + PROJECT_NAME
    explorer = f"{args.viewer.rstrip('/')}/?url={quote(project_url, safe='')}&layout=viewer"
    (SITE / "config.json").write_text(json.dumps({
        "explorer_url": explorer,
        "project_url": project_url,
        "meta": {k: meta[k] for k in ("date_min", "date_max", "birds", "buildings_with_records",
                                      "records", "excluded", "overture_release", "generated")},
    }, indent=2))

    print(f"wrote {PROJECT_NAME} ({(SITE / PROJECT_NAME).stat().st_size / 1e3:.0f} kB), "
          f"{len(chapters)} chapters")
    print("explorer:", explorer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
