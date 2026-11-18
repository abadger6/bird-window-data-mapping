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
# The default place to explore: the project on share.geolibre.app (uploaded by
# hand from site/bird-collisions.geolibre; see README "Updating the share").
DEFAULT_SHARE_URL = "https://share.geolibre.app/abadgett/bird-window-collisions-us-canada"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-url", required=True, help="public URL of site/, e.g. https://user.github.io/repo/")
    ap.add_argument("--viewer", default=DEFAULT_VIEWER,
                    help="GeoLibre web app that opens the project (hosted, or a self-hosted copy)")
    ap.add_argument("--share-url", default=DEFAULT_SHARE_URL,
                    help="share.geolibre.app page the site sends readers to explore")
    args = ap.parse_args()
    site_url = args.site_url.rstrip("/") + "/"

    meta = json.loads((SITE / "data/meta.json").read_text())
    bldgs = gpd.read_parquet(SITE / "data/buildings.parquet")
    reports = gpd.read_parquet(SITE / "data/reports.parquet")
    chapters = story.build_chapters(bldgs, reports, meta)

    proj = geolibre_project.build(site_url + "data/", chapters, meta)
    authoring.save_project(SITE / PROJECT_NAME, proj)

    project_url = site_url + PROJECT_NAME
    viewer = f"{args.viewer.rstrip('/')}/?url={quote(project_url, safe='')}&layout=viewer"
    # Opens the share's project in GeoLibre with the Layers panel collapsed and
    # in compact view (site/explorer-settings.json, applied for this visit only).
    explorer = (f"{args.viewer.rstrip('/')}/?url={quote(args.share_url + '.geolibre.json', safe='')}"
                f"&panels=collapsed&settingsUrl={quote(site_url + 'explorer-settings.json', safe='')}")

    (SITE / "story").mkdir(exist_ok=True)
    (SITE / "story/chapters.json").write_text(json.dumps({
        "title": "Bird–Window Collisions in the US & Canada",
        "subtitle": f"{meta['date_min'][:4]}–{meta['date_max'][:4]} · reports attributed to buildings",
        "bins": [[v, c, lab] for v, c, lab in geolibre_project.BIRD_STOPS],
        "explore_url": explorer,
        "chapters": [c.to_dict() for c in chapters],
    }, indent=2, ensure_ascii=False))

    (SITE / "config.json").write_text(json.dumps({
        "explorer_url": explorer,
        "share_url": args.share_url,
        "viewer_url": viewer,
        "project_url": project_url,
        "meta": {k: meta[k] for k in ("date_min", "date_max", "birds", "buildings_with_records",
                                      "records", "excluded", "overture_release", "generated")},
    }, indent=2))

    print(f"wrote {PROJECT_NAME} ({(SITE / PROJECT_NAME).stat().st_size / 1e3:.0f} kB), "
          f"{len(chapters)} chapters")
    print("explorer:", explorer)
    print("share page:", args.share_url)
    print("read-only viewer:", viewer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
