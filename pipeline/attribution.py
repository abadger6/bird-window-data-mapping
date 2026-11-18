"""Attribute collision records to building footprints.

Carried over from the modeling repo's validation notebook: each record is
snapped to the nearest building footprint within ``SNAP_MAX_M`` metres.
25 m sits just above the 75th percentile of the self-reported
"distance from point" values in the CBCM records — far enough to absorb
GPS / map-click error, tight enough not to jump across a street.

Records with no building inside the cap keep ``bid = -1`` and still appear in
the point layer; they are just not counted toward any building.
"""
from __future__ import annotations

import geopandas as gpd

SNAP_MAX_M = 25.0


def snap_to_buildings(points: gpd.GeoDataFrame, bldgs: gpd.GeoDataFrame,
                      projected_crs: str, max_m: float = SNAP_MAX_M) -> gpd.GeoDataFrame:
    """Return ``points`` with ``bid`` (row index into ``bldgs``) and ``snap_m``.

    Points inside a footprint get distance 0. Ties (equidistant footprints)
    resolve to the first match, so each record counts toward one building.
    """
    p = points.to_crs(projected_crs)
    b = bldgs.to_crs(projected_crs)[["geometry"]].copy()
    b["bid"] = range(len(b))
    j = gpd.sjoin_nearest(p, b, how="left", max_distance=max_m, distance_col="snap_m")
    j = j[~j.index.duplicated(keep="first")]
    out = points.copy()
    out["bid"] = j["bid"].fillna(-1).astype(int).reindex(points.index).values
    out["snap_m"] = j["snap_m"].round(1).reindex(points.index).values
    return out
