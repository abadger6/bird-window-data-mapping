"""Exclude reports that are likely at private homes.

The product focuses on larger urban buildings, and publishing reports at
single-family homes would expose where individual reporters live. Records
are first snapped to the nearest footprint (so a report at a house lands on
the house, not on a neighbouring office), then removed when:

1. the footprint is a house-type building in Overture (``class`` in
   ``HOUSE_CLASSES``, or a generic ``residential`` building under
   ``SMALL_M2``),
2. the footprint has no Overture type at all and is small and low
   (< ``SMALL_M2`` and ≤ ``LOW_M``): in practice houses, garages and sheds, or
3. no footprint lies within the snap distance, so only raw coordinates
   exist, which could be anywhere including a home.

Apartments, dormitories, offices, campuses and other non-house buildings are
kept regardless of size.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

HOUSE_CLASSES = {
    "house", "detached", "semidetached_house", "terrace", "bungalow",
    "cabin", "static_caravan", "garage", "farm",
}
SMALL_M2 = 400.0
LOW_M = 12.0


def is_private_home(bldgs: gpd.GeoDataFrame) -> pd.Series:
    """Boolean per building. Expects a metric CRS and columns
    ``class``, ``subtype``, ``height_m``."""
    if bldgs.crs is None or bldgs.crs.is_geographic:
        raise ValueError("is_private_home needs a projected (metric) CRS")
    m2 = bldgs.geometry.area
    cls = bldgs["class"].astype("object")
    sub = bldgs["subtype"].astype("object")
    small = m2 < SMALL_M2
    house_type = cls.isin(HOUSE_CLASSES) | ((cls == "residential") & small)
    untyped_small = sub.isna() & cls.isna() & small & (bldgs["height_m"] <= LOW_M)
    return (house_type | untyped_small).fillna(False).astype(bool)
