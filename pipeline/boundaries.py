"""US + Canada country outlines from Overture Maps ``division_area``.

We use the *maritime* outline (land + territorial sea) rather than the land
outline so buildings on the shoreline — piers, waterfront towers on fill —
are never clipped out.

Overture filters by bounding-box intersection, so querying a tiny ocean bbox
that both countries' bboxes overlap returns only a handful of large
polygons instead of every county and locality in North America.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

COUNTRIES = ("US", "CA")
# Tiny probe bboxes: Atlantic off Nova Scotia (hits CA + US), Gulf of
# Alaska (hits US). Together they return both maritime outlines.
_PROBES = [(-60.0, 44.0, -59.99, 44.01), (-150.0, 60.0, -149.99, 60.01)]


def fetch(cache_path: str | Path) -> gpd.GeoDataFrame:
    cache_path = Path(cache_path)
    if cache_path.exists():
        return gpd.read_file(cache_path)

    import overturemaps

    parts = []
    for bbox in _PROBES:
        g = overturemaps.geodataframe("division_area", bbox=bbox)
        parts.append(g[(g["subtype"] == "country") & (g["class"] == "maritime")
                       & g["country"].isin(COUNTRIES)])
    gdf = pd.concat(parts).drop_duplicates(subset="id")[["id", "country", "geometry"]]
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326")
    missing = set(COUNTRIES) - set(gdf["country"])
    if missing:
        raise RuntimeError(f"Overture returned no maritime outline for {missing}")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(cache_path, driver="GPKG")
    return gdf
